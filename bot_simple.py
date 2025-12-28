#!/usr/bin/env python3
"""
BOT SIMPLE - Trading Polymarket sans complexité
Logique: Mean Reversion + Polymarket binaire
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
    print("❌ ccxt non installé. Exécutez: pip install ccxt")
    sys.exit(1)

from src.config import get_config
from src.telegram_bot import TelegramNotifier
from src.polymarket_client import PolymarketClient

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot_simple.log')
    ]
)
logger = logging.getLogger(__name__)

# Constantes OPTIMISÉES (WR 57.45%)
RSI_PERIOD = 14
RSI_OVERSOLD = 25      # Plus strict (était 30)
RSI_OVERBOUGHT = 75    # Plus strict (était 70)
CONSEC_THRESHOLD = 5   # Plus strict (était 3)
MIN_MOMENTUM = 0.2     # Nouveau: momentum minimum
MAX_PRICE = 0.50       # 50 centimes max
BLOCKED_HOURS = [3, 7, 15, 18, 19, 20]  # Heures faibles à éviter


class SimpleBot:
    def __init__(self, symbols: list, shares: int = 5, is_live: bool = False):
        self.symbols = symbols
        self.shares = shares
        self.is_live = is_live

        self.config = get_config()
        self.telegram = TelegramNotifier()
        self.exchange = ccxt.binance({'enableRateLimit': True})

        # Polymarket client (sans validation dynamique complexe)
        if is_live:
            self.polymarket = PolymarketClient()
        else:
            self.polymarket = None

        # Stats
        self.trades = []
        self.last_trade = {}

        Path('logs').mkdir(exist_ok=True)

    def get_candles(self, symbol: str) -> pd.DataFrame:
        """Récupère les bougies"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except Exception as e:
            logger.error(f"Erreur données {symbol}: {e}")
            return None

    def calculate_rsi(self, closes: pd.Series) -> float:
        """RSI simple"""
        delta = closes.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=RSI_PERIOD, adjust=False).mean()
        avg_loss = loss.ewm(span=RSI_PERIOD, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def count_consecutive(self, df: pd.DataFrame) -> tuple:
        """Compte bougies consécutives"""
        is_up = (df['close'] > df['open']).astype(int)
        is_down = (df['close'] < df['open']).astype(int)

        # Compter depuis la fin
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
        """Génère signal UP, DOWN ou None - VERSION OPTIMISÉE"""
        if df is None or len(df) < RSI_PERIOD + 5:
            return None

        # Filtre des heures faibles
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in BLOCKED_HOURS:
            logger.info(f"⏰ Heure {current_hour}h bloquée - pas de trading")
            return None

        closes = df['close']
        rsi = self.calculate_rsi(closes)
        consec_up, consec_down = self.count_consecutive(df)

        # Momentum (doit être > MIN_MOMENTUM)
        momentum = (closes.iloc[-1] - closes.iloc[-4]) / closes.iloc[-4] * 100

        # Signal UP: 5+ DOWN consécutives OU RSI < 25, avec momentum < -0.2%
        if (consec_down >= CONSEC_THRESHOLD or rsi < RSI_OVERSOLD) and momentum < -MIN_MOMENTUM:
            logger.info(f"📈 Signal UP | RSI={rsi:.1f} | DOWN={consec_down} | Mom={momentum:.2f}%")
            return 'UP'

        # Signal DOWN: 5+ UP consécutives OU RSI > 75, avec momentum > +0.2%
        if (consec_up >= CONSEC_THRESHOLD or rsi > RSI_OVERBOUGHT) and momentum > MIN_MOMENTUM:
            logger.info(f"📉 Signal DOWN | RSI={rsi:.1f} | UP={consec_up} | Mom={momentum:.2f}%")
            return 'DOWN'

        return None

    def execute_trade(self, symbol: str, signal: str, btc_price: float):
        """Exécute un trade"""
        base = symbol.split('/')[0]

        # Cooldown 15 min
        last = self.last_trade.get(symbol)
        if last and (datetime.now(timezone.utc) - last).seconds < 900:
            logger.info(f"⏳ Cooldown actif pour {symbol}")
            return

        # Calculs
        entry_price = 0.50  # Prix estimé
        bet_cost = self.shares * entry_price
        potential_win = self.shares - bet_cost

        logger.info(f"🎯 TRADE | {base} {signal} | {self.shares} shares @ {entry_price*100:.0f}¢")
        logger.info(f"💰 BET: ${bet_cost:.2f} | TO WIN: ${potential_win:.2f}")

        if self.is_live:
            try:
                # Placer l'ordre sur Polymarket
                order = self.polymarket.place_order(
                    symbol=base,
                    direction='BUY',
                    outcome=signal,
                    amount=self.shares,
                    price=MAX_PRICE
                )

                if order:
                    order_id = order.get('order_id', 'N/A')
                    actual_price = order.get('price', entry_price)
                    logger.info(f"✅ ORDRE PLACÉ | ID: {order_id} | Prix: {actual_price*100:.0f}¢")

                    # Notification Telegram
                    self.telegram.send_message(f"""
🎯 <b>TRADE PLACÉ</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix BTC:</b> ${btc_price:,.0f}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")
                else:
                    logger.warning(f"⚠️ Ordre non exécuté (prix > {MAX_PRICE*100:.0f}¢)")

            except Exception as e:
                logger.error(f"❌ Erreur: {e}")
                self.telegram.notify_error(f"Erreur trade {base}: {e}")
        else:
            # Mode simulation
            logger.info(f"🔵 [SIMULATION] Trade non exécuté")
            self.telegram.send_message(f"""
🔵 <b>SIGNAL (Simulation)</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
💵 <b>Prix BTC:</b> ${btc_price:,.0f}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
""")

        self.last_trade[symbol] = datetime.now(timezone.utc)

    def wait_for_candle(self) -> int:
        """Attend la prochaine bougie 15m"""
        now = datetime.now(timezone.utc)
        minutes = now.minute
        seconds = now.second

        # Prochaine bougie
        next_min = ((minutes // 15) + 1) * 15
        if next_min >= 60:
            next_min = 0
            wait = (60 - minutes - 1) * 60 + (60 - seconds)
        else:
            wait = (next_min - minutes - 1) * 60 + (60 - seconds)

        # Entrer 8 secondes avant
        return max(0, wait - 8)

    def run(self):
        """Boucle principale"""
        mode = "🔴 LIVE" if self.is_live else "🔵 SIMULATION"

        logger.info("=" * 60)
        logger.info(f"🤖 BOT OPTIMISÉ DÉMARRÉ - {mode}")
        logger.info("=" * 60)
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Shares: {self.shares} (~${self.shares * 0.50:.2f} @ 50¢)")
        logger.info(f"RSI: {RSI_OVERSOLD}/{RSI_OVERBOUGHT} | Consec: {CONSEC_THRESHOLD} | Mom: {MIN_MOMENTUM}%")
        logger.info(f"Heures bloquées: {BLOCKED_HOURS}")
        logger.info(f"Win Rate attendu: ~57.5%")
        logger.info("=" * 60)

        # Notification démarrage
        self.telegram.send_message(f"""
🤖 <b>BOT OPTIMISÉ</b> - {mode}

📊 Symboles: {', '.join([s.split('/')[0] for s in self.symbols])}
💰 Mise: {self.shares} shares (~${self.shares * 0.50:.2f})

⚙️ <b>Config optimisée (WR ~57.5%):</b>
• RSI: {RSI_OVERSOLD}/{RSI_OVERBOUGHT}
• Consécutives: {CONSEC_THRESHOLD}
• Momentum min: {MIN_MOMENTUM}%
• Heures bloquées: {len(BLOCKED_HOURS)}

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        try:
            while True:
                wait = self.wait_for_candle()
                logger.info(f"⏳ Prochaine analyse dans {wait} secondes...")
                time.sleep(wait)

                logger.info("-" * 40)
                logger.info(f"🔍 ANALYSE | {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")

                for symbol in self.symbols:
                    logger.info(f"\n📊 {symbol}...")

                    df = self.get_candles(symbol)
                    if df is None:
                        continue

                    signal = self.get_signal(df)

                    if signal:
                        self.execute_trade(symbol, signal, df['close'].iloc[-1])
                    else:
                        logger.info(f"   Pas de signal")

                # Attendre fin de bougie
                time.sleep(15)

        except KeyboardInterrupt:
            logger.info("\n🛑 Arrêt demandé")
            self.telegram.send_message("🛑 <b>BOT ARRÊTÉ</b>")


def main():
    parser = argparse.ArgumentParser(description='Bot Simple Polymarket')
    parser.add_argument('--live', action='store_true', help='Mode live (argent réel)')
    parser.add_argument('--shares', type=int, default=5, help='Nombre de shares par trade')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,XRP/USDT')

    args = parser.parse_args()

    if args.live:
        print("\n⚠️  MODE LIVE - Argent réel!")
        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annulé.")
            return

    bot = SimpleBot(
        symbols=args.symbols.split(','),
        shares=args.shares,
        is_live=args.live
    )

    bot.run()


if __name__ == "__main__":
    main()
