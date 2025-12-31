#!/usr/bin/env python3
"""
BOT V2 SIMPLE - Stratégie 3 Candles Consécutives
Règle: 3 candles UP -> DOWN | 3 candles DOWN -> UP
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

# Logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    Path('logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler('logs/bot_v2.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False

# Config
MAX_PRICE = 0.55  # Max 55¢ entry
CONSECUTIVE_CANDLES = 3  # Nombre de candles consécutives


class BotV2Simple:
    def __init__(self, symbols: list, shares: int = 5, is_live: bool = False):
        self.symbols = symbols
        self.shares = shares
        self.is_live = is_live

        self.config = get_config()
        self.telegram = TelegramNotifier()
        self.exchange = ccxt.binance({'enableRateLimit': True})

        if is_live:
            self.polymarket = PolymarketClient()
        else:
            self.polymarket = None

        Path('logs').mkdir(exist_ok=True)
        trade_tracker.init_db()

    def get_candles(self, symbol: str, limit: int = 10) -> pd.DataFrame:
        """Récupère les dernières candles"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except Exception as e:
            logger.error(f"Erreur données {symbol}: {e}")
            return None

    def get_direction(self, row) -> str:
        """Retourne UP ou DOWN pour une candle"""
        return "UP" if row['close'] > row['open'] else "DOWN"

    def get_signal(self, df: pd.DataFrame, symbol: str) -> str:
        """
        Stratégie V2 Simple:
        - 3 candles DOWN consécutives -> Signal UP
        - 3 candles UP consécutives -> Signal DOWN
        """
        if df is None or len(df) < CONSECUTIVE_CANDLES + 1:
            return None

        # Dernières 3 candles fermées (exclure la candle en cours)
        closed_candles = df.iloc[-(CONSECUTIVE_CANDLES + 1):-1]

        directions = [self.get_direction(row) for _, row in closed_candles.iterrows()]

        # Log des directions
        base = symbol.split('/')[0]
        logger.info(f"   {base}: {' -> '.join(directions)}")

        # 3 DOWN -> UP
        if all(d == "DOWN" for d in directions):
            logger.info(f"   Signal UP (3 DOWN consécutives)")
            return "UP"

        # 3 UP -> DOWN
        if all(d == "UP" for d in directions):
            logger.info(f"   Signal DOWN (3 UP consécutives)")
            return "DOWN"

        return None

    def wait_for_candle(self) -> int:
        """Attend le début de la prochaine candle 15min"""
        now = datetime.now(timezone.utc)
        minutes = now.minute
        seconds = now.second

        # Prochaine candle à :00, :15, :30, :45
        next_candle = ((minutes // 15) + 1) * 15
        if next_candle >= 60:
            next_candle = 0
            wait_minutes = 60 - minutes - 1
        else:
            wait_minutes = next_candle - minutes - 1

        wait_seconds = (wait_minutes * 60) + (60 - seconds)
        return max(0, wait_seconds)

    def execute_trade(self, symbol: str, signal: str, current_price: float):
        """Exécute ou simule un trade"""
        base = symbol.split('/')[0]
        entry_price = 0.525  # 52.5¢

        bet_cost = self.shares * entry_price
        potential_win = self.shares * (1 - entry_price)

        logger.info(f"🎯 TRADE | {base} {signal} | {self.shares} shares @ {entry_price*100:.0f}¢")
        logger.info(f"💰 BET: ${bet_cost:.2f} | TO WIN: ${potential_win:.2f}")

        if self.is_live:
            try:
                # Trade réel sur Polymarket
                order = self.polymarket.place_order(
                    symbol=base,
                    direction=signal,
                    amount=self.shares,
                    price=MAX_PRICE
                )

                if order:
                    order_id = order.get('order_id', 'N/A')
                    actual_price = order.get('price', entry_price)
                    logger.info(f"✅ ORDRE PLACÉ | ID: {order_id} | Prix: {actual_price*100:.0f}¢")

                    # Log pour tracking
                    trade_tracker.log_trade(
                        symbol=symbol,
                        direction=signal,
                        shares=self.shares,
                        entry_price=actual_price * 100,
                        order_id=order_id
                    )

                    # Notification Telegram
                    price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
                    self.telegram.send_message(f"""
🎯 <b>TRADE V2 PLACÉ</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {base}:</b> {price_fmt}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")
                else:
                    logger.warning(f"⚠️ Ordre non exécuté")

            except Exception as e:
                logger.error(f"❌ Erreur: {e}")
                self.telegram.notify_error(f"Erreur trade {base}: {e}")
        else:
            # Mode simulation
            logger.info(f"🔵 [PAPER] Trade simulé")

            # Log pour tracking même en paper
            trade_tracker.log_trade(
                symbol=symbol,
                direction=signal,
                shares=self.shares,
                entry_price=52.5,
                order_id=f"PAPER_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            )

            price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
            self.telegram.send_message(f"""
🔵 <b>PAPER TRADE V2</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {base}:</b> {price_fmt}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")

    def run(self):
        """Boucle principale"""
        mode = "LIVE" if self.is_live else "PAPER TRADING"

        logger.info("=" * 60)
        logger.info(f"BOT V2 SIMPLE - {mode}")
        logger.info("=" * 60)
        logger.info(f"Stratégie: 3 candles consécutives -> inverse")
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Shares: {self.shares} (~${self.shares * 0.525:.2f} @ 52.5¢)")
        logger.info(f"Trades attendus: ~65/jour | WR ~55%")
        logger.info("=" * 60)

        # Notification démarrage
        mode_emoji = "🔴" if self.is_live else "🔵"
        self.telegram.send_message(f"""
{mode_emoji} <b>BOT V2 SIMPLE</b> - {mode}

📊 <b>Stratégie:</b> 3 candles consécutives
🪙 <b>Symboles:</b> {', '.join([s.split('/')[0] for s in self.symbols])}
💰 <b>Mise:</b> {self.shares} shares (~${self.shares * 0.525:.2f})

📈 <b>Attendu:</b> ~65 trades/jour | 55% WR
💵 <b>PnL estimé:</b> ~$11,000/mois

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        try:
            while True:
                wait = self.wait_for_candle()
                logger.info(f"⏳ Prochaine analyse dans {wait} secondes...")
                time.sleep(wait + 5)  # +5s pour laisser la candle se fermer

                logger.info("-" * 40)
                logger.info(f"🔍 ANALYSE | {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

                for symbol in self.symbols:
                    df = self.get_candles(symbol)
                    if df is None:
                        continue

                    signal = self.get_signal(df, symbol)

                    if signal:
                        current_price = df.iloc[-1]['close']
                        self.execute_trade(symbol, signal, current_price)
                    else:
                        logger.info(f"   Pas de signal")

        except KeyboardInterrupt:
            logger.info("Arrêt demandé")
            self.telegram.send_message("🛑 <b>BOT V2 ARRÊTÉ</b>")


def main():
    parser = argparse.ArgumentParser(description='Bot V2 Simple')
    parser.add_argument('--live', action='store_true', help='Mode live (argent réel)')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation')
    parser.add_argument('--shares', type=int, default=10, help='Shares par trade')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,XRP/USDT')

    args = parser.parse_args()

    if args.live and not args.yes:
        print("\n⚠️  MODE LIVE - Argent réel!")
        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annulé.")
            return

    bot = BotV2Simple(
        symbols=args.symbols.split(','),
        shares=args.shares,
        is_live=args.live
    )

    bot.run()


if __name__ == "__main__":
    main()
