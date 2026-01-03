#!/usr/bin/env python3
"""
BOT V10 - ETH
Strategy optimale: 67 trades/jour, $23k/mois, 0 mois < $10k

Parametres:
- RSI(7): 42/62
- Stochastic(5): 38/68
- FTFC Threshold: 2.0

Usage:
    python bot_v10_eth.py              # Mode simulation
    python bot_v10_eth.py --live       # Mode production
"""

import sys
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import ccxt

from src.config import get_config
from src.telegram_bot import TelegramNotifier
from src.polymarket_client import PolymarketClient
import trade_tracker

# Configuration
SYMBOL = 'ETH/USDT'
BASE = 'ETH'

# Strategy Parameters - V10
RSI_PERIOD = 7
RSI_OVERSOLD = 42
RSI_OVERBOUGHT = 62
STOCH_PERIOD = 5
STOCH_OVERSOLD = 38
STOCH_OVERBOUGHT = 68
FTFC_THRESHOLD = 2.0

# Trading Parameters
MAX_PRICE = 0.55
ENTRY_PRICE = 0.525

# Logging
logger = logging.getLogger(f'bot_v10_{BASE.lower()}')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(f'%(asctime)s | {BASE} | %(levelname)s | %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    Path('logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler(f'logs/bot_v10_{BASE.lower()}.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False


class BotV10:
    def __init__(self, shares: int = 10, is_live: bool = False):
        self.symbol = SYMBOL
        self.base = BASE
        self.shares = shares
        self.is_live = is_live

        self.config = get_config()
        self.telegram = TelegramNotifier()
        self.exchange = ccxt.binance({'enableRateLimit': True})

        if is_live:
            self.polymarket = PolymarketClient()
        else:
            self.polymarket = None

        # Cache for HTF data
        self.df_1h = None
        self.df_4h = None
        self.last_htf_update = None

        Path('logs').mkdir(exist_ok=True)
        trade_tracker.init_db()

    def fetch_ohlcv(self, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV data from Binance"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Erreur fetch {timeframe}: {e}")
            return None

    def update_htf_data(self):
        """Update 1H and 4H data (every hour)"""
        now = datetime.now(timezone.utc)

        # Update HTF data every hour
        if self.last_htf_update is None or (now - self.last_htf_update).seconds >= 3600:
            logger.info("Updating HTF data (1H/4H)...")
            self.df_1h = self.fetch_ohlcv('1h', 50)
            self.df_4h = self.fetch_ohlcv('4h', 50)
            self.last_htf_update = now
            logger.info(f"  1H: {len(self.df_1h) if self.df_1h is not None else 0} candles")
            logger.info(f"  4H: {len(self.df_4h) if self.df_4h is not None else 0} candles")

    def calculate_rsi(self, prices: pd.Series, period: int = 7) -> float:
        """Calculate RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    def calculate_stochastic(self, df: pd.DataFrame, period: int = 5) -> float:
        """Calculate Stochastic %K"""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        stoch = 100 * (df['close'] - low_min) / (high_max - low_min)
        return float(stoch.iloc[-1]) if not pd.isna(stoch.iloc[-1]) else 50.0

    def get_ftfc_score(self, timestamp) -> float:
        """
        Calculate FTFC Score from 1H and 4H timeframes

        Score components:
        - 1H trend > 0.1%: +1, < -0.1%: -1
        - 4H trend > 0.2%: +1, < -0.2%: -1
        - 1H RSI > 55: +0.5, < 45: -0.5
        - 4H RSI > 55: +0.5, < 45: -0.5
        """
        if self.df_1h is None or self.df_4h is None:
            return 0.0

        ts = pd.Timestamp(timestamp)

        # 1H analysis
        h1_data = self.df_1h[self.df_1h.index <= ts].tail(5)
        if len(h1_data) >= 3:
            h1_trend = (h1_data['close'].iloc[-1] - h1_data['close'].iloc[0]) / h1_data['close'].iloc[0] * 100
            h1_rsi = self.calculate_rsi(self.df_1h['close'], 14)
        else:
            h1_trend, h1_rsi = 0, 50

        # 4H analysis
        h4_data = self.df_4h[self.df_4h.index <= ts].tail(5)
        if len(h4_data) >= 3:
            h4_trend = (h4_data['close'].iloc[-1] - h4_data['close'].iloc[0]) / h4_data['close'].iloc[0] * 100
            h4_rsi = self.calculate_rsi(self.df_4h['close'], 14)
        else:
            h4_trend, h4_rsi = 0, 50

        # Calculate FTFC Score
        ftfc_score = 0
        if h1_trend > 0.1: ftfc_score += 1
        elif h1_trend < -0.1: ftfc_score -= 1
        if h4_trend > 0.2: ftfc_score += 1
        elif h4_trend < -0.2: ftfc_score -= 1
        if h1_rsi > 55: ftfc_score += 0.5
        elif h1_rsi < 45: ftfc_score -= 0.5
        if h4_rsi > 55: ftfc_score += 0.5
        elif h4_rsi < 45: ftfc_score -= 0.5

        return ftfc_score

    def get_signal(self, df: pd.DataFrame) -> tuple:
        """
        V10 Signal Generation

        UP Signal:
          RSI(7) < 42 AND Stoch(5) < 38 AND FTFC > -2.0

        DOWN Signal:
          RSI(7) > 62 AND Stoch(5) > 68 AND FTFC < 2.0

        Returns: (signal, rsi, stoch, ftfc_score)
        """
        if df is None or len(df) < 10:
            return None, 0, 0, 0

        # Use the current candle (closes in ~20 sec)
        current = df.iloc[-1]

        # Calculate indicators
        rsi = self.calculate_rsi(df['close'], RSI_PERIOD)
        stoch = self.calculate_stochastic(df, STOCH_PERIOD)
        ftfc_score = self.get_ftfc_score(current.name)

        signal = None

        # UP Signal
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            if ftfc_score > -FTFC_THRESHOLD:  # Not strongly bearish
                signal = 'UP'
                logger.info(f"Signal UP | RSI={rsi:.1f}<{RSI_OVERSOLD} | Stoch={stoch:.1f}<{STOCH_OVERSOLD} | FTFC={ftfc_score:.1f}>-{FTFC_THRESHOLD}")

        # DOWN Signal
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            if ftfc_score < FTFC_THRESHOLD:  # Not strongly bullish
                signal = 'DOWN'
                logger.info(f"Signal DOWN | RSI={rsi:.1f}>{RSI_OVERBOUGHT} | Stoch={stoch:.1f}>{STOCH_OVERBOUGHT} | FTFC={ftfc_score:.1f}<{FTFC_THRESHOLD}")

        return signal, rsi, stoch, ftfc_score

    def wait_for_candle(self) -> int:
        """Wait until 20 seconds BEFORE next 15min candle closes"""
        now = datetime.now(timezone.utc)
        minutes = now.minute
        seconds = now.second

        next_candle = ((minutes // 15) + 1) * 15
        if next_candle >= 60:
            next_candle = 0
            wait_minutes = 60 - minutes - 1
        else:
            wait_minutes = next_candle - minutes - 1

        # Wait until 20 sec BEFORE candle close
        wait_seconds = (wait_minutes * 60) + (60 - seconds) - 20
        return max(0, wait_seconds)

    def execute_trade(self, signal: str, current_price: float, rsi: float, stoch: float, ftfc: float):
        """Execute trade on Polymarket"""
        bet_cost = self.shares * ENTRY_PRICE
        potential_win = self.shares * (1 - ENTRY_PRICE)

        logger.info(f"TRADE | {self.base} {signal} | {self.shares} shares @ {ENTRY_PRICE*100:.0f}c")
        logger.info(f"BET: ${bet_cost:.2f} | TO WIN: ${potential_win:.2f}")

        if self.is_live:
            try:
                order = self.polymarket.place_order(
                    symbol=self.base,
                    direction="BUY",
                    outcome=signal,
                    amount=self.shares,
                    price=MAX_PRICE
                )

                if order:
                    order_id = order.get('order_id', 'N/A')
                    actual_price = order.get('price', ENTRY_PRICE)
                    logger.info(f"ORDRE PLACE | ID: {order_id} | Prix: {actual_price*100:.0f}c")

                    trade_tracker.log_trade(
                        symbol=self.symbol,
                        direction=signal,
                        shares=self.shares,
                        entry_price=actual_price * 100,
                        order_id=order_id,
                        rsi=rsi,
                        stochastic=stoch,
                        ftfc_score=ftfc,
                        btc_price=current_price,
                        strategy_version='V10'
                    )

                    price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
                    self.telegram.send_message(f"""
🎯 <b>TRADE V10 - {self.base}</b>

🪙 <b>Marche:</b> {self.base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {self.base}:</b> {price_fmt}

📊 <b>Indicateurs:</b>
  RSI(7): {rsi:.1f}
  Stoch(5): {stoch:.1f}
  FTFC: {ftfc:.1f}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")
                else:
                    logger.warning("Ordre non execute")

            except Exception as e:
                logger.error(f"Erreur: {e}")
                self.telegram.notify_error(f"Erreur trade {self.base}: {e}")
        else:
            # Paper trading
            logger.info("[PAPER] Trade simule")

            trade_tracker.log_trade(
                symbol=self.symbol,
                direction=signal,
                shares=self.shares,
                entry_price=52.5,
                order_id=f"PAPER_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                rsi=rsi,
                stochastic=stoch,
                ftfc_score=ftfc,
                btc_price=current_price,
                strategy_version='V10'
            )

            price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
            self.telegram.send_message(f"""
🔵 <b>PAPER V10 - {self.base}</b>

🪙 <b>Marche:</b> {self.base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {self.base}:</b> {price_fmt}

📊 <b>Indicateurs:</b>
  RSI(7): {rsi:.1f}
  Stoch(5): {stoch:.1f}
  FTFC: {ftfc:.1f}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")

    def run(self):
        """Main loop"""
        mode = "LIVE" if self.is_live else "PAPER"

        logger.info("=" * 60)
        logger.info(f"BOT V10 - {self.base} - {mode}")
        logger.info("=" * 60)
        logger.info(f"RSI(7): {RSI_OVERSOLD}/{RSI_OVERBOUGHT}")
        logger.info(f"Stoch(5): {STOCH_OVERSOLD}/{STOCH_OVERBOUGHT}")
        logger.info(f"FTFC Threshold: {FTFC_THRESHOLD}")
        logger.info(f"Shares: {self.shares} (~${self.shares * ENTRY_PRICE:.2f})")
        logger.info("=" * 60)

        mode_emoji = "🔴" if self.is_live else "🔵"
        self.telegram.send_message(f"""
{mode_emoji} <b>BOT V10 - {self.base}</b> - {mode}

📊 <b>Strategie V10:</b>
  RSI(7): {RSI_OVERSOLD}/{RSI_OVERBOUGHT}
  Stoch(5): {STOCH_OVERSOLD}/{STOCH_OVERBOUGHT}
  FTFC: ±{FTFC_THRESHOLD}

💰 <b>Mise:</b> {self.shares} shares (~${self.shares * ENTRY_PRICE:.2f})

📈 <b>Attendu:</b> ~22 trades/jour | 59% WR
💵 <b>PnL estime:</b> ~$8,100/mois

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        try:
            while True:
                # Update HTF data
                self.update_htf_data()

                wait = self.wait_for_candle()
                logger.info(f"Analyse dans {wait}s (20s avant fermeture)...")
                time.sleep(wait)

                logger.info("-" * 40)
                logger.info(f"ANALYSE | {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

                df = self.fetch_ohlcv('15m', 50)
                if df is None:
                    continue

                signal, rsi, stoch, ftfc = self.get_signal(df)

                if signal:
                    current_price = df.iloc[-1]['close']
                    self.execute_trade(signal, current_price, rsi, stoch, ftfc)
                else:
                    logger.info(f"Pas de signal | RSI={rsi:.1f} | Stoch={stoch:.1f} | FTFC={ftfc:.1f}")

        except KeyboardInterrupt:
            logger.info("Arret demande")
            self.telegram.send_message(f"🛑 <b>BOT V10 {self.base} ARRETE</b>")


def main():
    parser = argparse.ArgumentParser(description=f'Bot V10 {BASE}')
    parser.add_argument('--live', action='store_true', help='Mode live')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser.add_argument('--shares', type=int, default=10, help='Shares par trade')

    args = parser.parse_args()

    if args.live and not args.yes:
        print(f"\n⚠️  MODE LIVE - {BASE} - Argent reel!")
        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annule.")
            return

    bot = BotV10(shares=args.shares, is_live=args.live)
    bot.run()


if __name__ == "__main__":
    main()
