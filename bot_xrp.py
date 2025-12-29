#!/usr/bin/env python3
"""
BOT XRP - Trading Polymarket dédié Ripple
1 bot = 1 pair = meilleur timing = plus de profits
"""

import sys
import time
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

try:
    import ccxt
except ImportError:
    print("pip install ccxt")
    sys.exit(1)

from src.config import get_config
from src.telegram_bot import TelegramNotifier
from src.polymarket_client import PolymarketClient

# CONFIG XRP OPTIMISÉE (backtest 2025: 54.4% WR)
SYMBOL = 'XRP/USDT'
BASE = 'XRP'
CONFIG = {
    'rsi_period': 7,
    'rsi_oversold': 35,
    'rsi_overbought': 65,
    'stoch_period': 5,
    'stoch_oversold': 30,
    'stoch_overbought': 70,
    'consec_threshold': 1,
    'blocked_hours': [],  # Aucune - maximise trades
}

MAX_PRICE = 0.52  # 52¢

# Logging
logger = logging.getLogger(f'bot_{BASE.lower()}')
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(f'%(asctime)s | {BASE} | %(levelname)s | %(message)s')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    Path('logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler(f'logs/bot_{BASE.lower()}.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False


class BotXRP:
    def __init__(self, shares: int = 5, is_live: bool = False):
        self.shares = shares
        self.is_live = is_live
        self.config = get_config()
        self.telegram = TelegramNotifier()
        self.exchange = ccxt.binance({'enableRateLimit': True})

        if is_live:
            self.polymarket = PolymarketClient()
        else:
            self.polymarket = None

        self.last_trade_time = None
        Path('logs').mkdir(exist_ok=True)

    def get_candles(self) -> pd.DataFrame:
        try:
            ohlcv = self.exchange.fetch_ohlcv(SYMBOL, '15m', limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except Exception as e:
            logger.error(f"Erreur données: {e}")
            return None

    def calculate_rsi(self, closes: pd.Series) -> float:
        period = CONFIG['rsi_period']
        delta = closes.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def calculate_stochastic(self, df: pd.DataFrame) -> float:
        period = CONFIG['stoch_period']
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        stoch = 100 * (df['close'] - low_min) / (high_max - low_min)
        return stoch.iloc[-1]

    def count_consecutive(self, df: pd.DataFrame) -> tuple:
        is_up = (df['close'] > df['open']).astype(int)
        is_down = (df['close'] < df['open']).astype(int)
        consec_up = 0
        consec_down = 0
        for i in range(len(df) - 1, -1, -1):
            if is_up.iloc[i]:
                if consec_down == 0:
                    consec_up += 1
                else:
                    break
            elif is_down.iloc[i]:
                if consec_up == 0:
                    consec_down += 1
                else:
                    break
            else:
                break
        return consec_up, consec_down

    def get_signal(self, df: pd.DataFrame) -> str:
        if df is None or len(df) < 20:
            return None

        # Filtre heures faibles
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in CONFIG['blocked_hours']:
            logger.info(f"Heure {current_hour}h bloquée")
            return None

        closes = df['close']
        rsi = self.calculate_rsi(closes)
        stoch = self.calculate_stochastic(df)
        consec_up, consec_down = self.count_consecutive(df)

        # Signal UP
        if rsi < CONFIG['rsi_oversold'] and stoch < CONFIG['stoch_oversold']:
            logger.info(f"Signal UP | RSI={rsi:.1f} | Stoch={stoch:.1f}")
            return 'UP'

        # Signal DOWN
        if rsi > CONFIG['rsi_overbought'] and stoch > CONFIG['stoch_overbought']:
            logger.info(f"Signal DOWN | RSI={rsi:.1f} | Stoch={stoch:.1f}")
            return 'DOWN'

        return None

    def execute_trade(self, signal: str, current_price: float):
        # Cooldown 15 min
        if self.last_trade_time:
            elapsed = (datetime.now(timezone.utc) - self.last_trade_time).seconds
            if elapsed < 900:
                logger.info(f"Cooldown actif ({900 - elapsed}s restants)")
                return

        entry_price = MAX_PRICE
        bet_cost = self.shares * entry_price
        potential_win = self.shares - bet_cost

        logger.info(f"TRADE | {BASE} {signal} | {self.shares} shares @ {entry_price*100:.0f}¢")
        logger.info(f"BET: ${bet_cost:.2f} | TO WIN: ${potential_win:.2f}")

        if self.is_live:
            try:
                order = self.polymarket.place_order(
                    symbol=BASE,
                    direction='BUY',
                    outcome=signal,
                    amount=self.shares,
                    price=MAX_PRICE
                )
                if order:
                    order_id = order.get('order_id', 'N/A')
                    logger.info(f"ORDRE PLACÉ | ID: {order_id}")

                    price_fmt = f"${current_price:.4f}"
                    self.telegram.send_message(f"""
🎯 <b>TRADE {BASE}</b>

🪙 <b>Marché:</b> {BASE} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {BASE}:</b> {price_fmt}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")
                else:
                    logger.warning(f"Ordre non exécuté (prix > {MAX_PRICE*100:.0f}¢)")
            except Exception as e:
                logger.error(f"Erreur: {e}")
                self.telegram.notify_error(f"Erreur {BASE}: {e}")
        else:
            logger.info(f"[SIMULATION] Trade non exécuté")
            price_fmt = f"${current_price:.4f}"
            self.telegram.send_message(f"""
🔵 <b>SIGNAL {BASE}</b> (Simulation)

🪙 <b>Marché:</b> {BASE} {signal}
💰 <b>BET:</b> ${bet_cost:.2f}
💵 <b>Prix:</b> {price_fmt}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")

        self.last_trade_time = datetime.now(timezone.utc)

    def wait_for_candle(self) -> int:
        now = datetime.now(timezone.utc)
        minutes = now.minute
        seconds = now.second
        next_min = ((minutes // 15) + 1) * 15
        if next_min >= 60:
            next_min = 0
            wait = (60 - minutes - 1) * 60 + (60 - seconds)
        else:
            wait = (next_min - minutes - 1) * 60 + (60 - seconds)
        return max(0, wait - 20)  # -20 sec comme Adnane

    def run(self):
        mode = "LIVE" if self.is_live else "SIMULATION"

        logger.info("=" * 50)
        logger.info(f"BOT {BASE} DÉMARRÉ - {mode}")
        logger.info(f"Entry: {MAX_PRICE*100:.0f}¢ | Shares: {self.shares}")
        logger.info(f"Blacklist: {CONFIG['blocked_hours']}")
        logger.info("=" * 50)

        self.telegram.send_message(f"""
🤖 <b>BOT {BASE}</b> - {mode}

💰 Mise: {self.shares} shares (~${self.shares * MAX_PRICE:.2f})
📊 Entry: {MAX_PRICE*100:.0f}¢
⏰ Blacklist: {CONFIG['blocked_hours']}

{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        try:
            while True:
                wait = self.wait_for_candle()
                logger.info(f"Prochaine analyse dans {wait}s...")
                time.sleep(wait)

                logger.info("-" * 30)
                df = self.get_candles()
                if df is None:
                    continue

                signal = self.get_signal(df)
                if signal:
                    self.execute_trade(signal, df['close'].iloc[-1])
                else:
                    logger.info("Pas de signal")

                time.sleep(15)

        except KeyboardInterrupt:
            logger.info("Arrêt demandé")
            self.telegram.send_message(f"🛑 <b>BOT {BASE} ARRÊTÉ</b>")


def main():
    parser = argparse.ArgumentParser(description=f'Bot {BASE} Polymarket')
    parser.add_argument('--live', action='store_true', help='Mode live')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser.add_argument('--shares', type=int, default=5, help='Shares par trade')
    args = parser.parse_args()

    if args.live and not args.yes:
        print(f"\n⚠️  MODE LIVE - {BASE} - Argent réel!")
        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annulé.")
            return

    bot = BotXRP(shares=args.shares, is_live=args.live)
    bot.run()


if __name__ == "__main__":
    main()
