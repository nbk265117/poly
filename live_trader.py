#!/usr/bin/env python3
"""
LIVE TRADER - Stratégie Mean Reversion pour Polymarket
Trading automatique BTC/ETH/XRP Up/Down 15 minutes

Usage:
    python live_trader.py              # Mode simulation
    python live_trader.py --live       # Mode production (argent réel)
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le path
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

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/live_trader.log')
    ]
)
logger = logging.getLogger(__name__)


class MeanReversionLive:
    """
    Stratégie Mean Reversion pour trading live
    """

    def __init__(self, rsi_period=14, rsi_oversold=30, rsi_overbought=70, consec_threshold=3):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.consec_threshold = consec_threshold

    def calculate_rsi(self, closes: list) -> float:
        """Calcule le RSI sur une série de prix"""
        if len(closes) < self.rsi_period + 1:
            return 50.0

        df = pd.Series(closes)
        delta = df.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def count_consecutive(self, candles: list) -> tuple:
        """Compte les bougies consécutives UP et DOWN"""
        consec_down = 0
        consec_up = 0

        # Parcourir les bougies de la plus récente à la plus ancienne
        for i in range(len(candles) - 1, -1, -1):
            candle = candles[i]
            is_up = candle['close'] > candle['open']
            is_down = candle['close'] < candle['open']

            if i == len(candles) - 1:
                # Dernière bougie
                if is_down:
                    consec_down = 1
                elif is_up:
                    consec_up = 1
            else:
                # Bougies précédentes
                if is_down and consec_down > 0:
                    consec_down += 1
                elif is_up and consec_up > 0:
                    consec_up += 1
                else:
                    break

        return consec_up, consec_down

    def generate_signal(self, candles: list) -> str:
        """
        Génère un signal basé sur les dernières bougies

        Args:
            candles: Liste de bougies OHLCV [{open, high, low, close, volume}, ...]

        Returns:
            'UP', 'DOWN', ou None
        """
        if len(candles) < self.rsi_period + 5:
            return None

        # Calculer RSI
        closes = [c['close'] for c in candles]
        rsi = self.calculate_rsi(closes)

        # Compter bougies consécutives
        consec_up, consec_down = self.count_consecutive(candles)

        # Calculer momentum
        if len(closes) >= 4:
            momentum = (closes[-1] - closes[-4]) / closes[-4] * 100
        else:
            momentum = 0

        # === Règles de signal ===

        # Signal UP : 3+ DOWN consécutives OU RSI < 30, avec momentum négatif
        cond_up = (consec_down >= self.consec_threshold) or (rsi < self.rsi_oversold)
        if cond_up and momentum < 0:
            logger.info(f"📈 Signal UP détecté | RSI={rsi:.1f} | Consec DOWN={consec_down} | Mom={momentum:.2f}%")
            return 'UP'

        # Signal DOWN : 3+ UP consécutives OU RSI > 70, avec momentum positif
        cond_down = (consec_up >= self.consec_threshold) or (rsi > self.rsi_overbought)
        if cond_down and momentum > 0:
            logger.info(f"📉 Signal DOWN détecté | RSI={rsi:.1f} | Consec UP={consec_up} | Mom={momentum:.2f}%")
            return 'DOWN'

        return None


class LiveTrader:
    """
    Trader live pour Polymarket
    """

    def __init__(self, symbols: list, bet_size: float = 2.0, is_live: bool = False):
        self.symbols = symbols
        self.bet_size = bet_size
        self.is_live = is_live

        # Initialiser les composants
        self.config = get_config()
        self.strategy = MeanReversionLive()
        self.telegram = TelegramNotifier()
        self.polymarket = PolymarketClient()

        # Exchange pour données
        self.exchange = ccxt.binance({'enableRateLimit': True})

        # Stats
        self.trades_today = 0
        self.wins_today = 0
        self.losses_today = 0
        self.pnl_today = 0.0
        self.last_trade_time = {}

        # Créer le dossier logs
        Path('logs').mkdir(exist_ok=True)

    def get_candles(self, symbol: str, limit: int = 50) -> list:
        """Récupère les dernières bougies depuis Binance"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='15m', limit=limit)
            candles = []
            for o in ohlcv:
                candles.append({
                    'timestamp': o[0],
                    'open': o[1],
                    'high': o[2],
                    'low': o[3],
                    'close': o[4],
                    'volume': o[5]
                })
            return candles
        except Exception as e:
            logger.error(f"Erreur récupération données {symbol}: {e}")
            return []

    def get_time_to_next_candle(self) -> int:
        """Calcule le temps restant avant la prochaine bougie 15m"""
        now = datetime.utcnow()
        minutes = now.minute
        seconds = now.second

        # Prochaine bougie à :00, :15, :30, :45
        next_minute = ((minutes // 15) + 1) * 15
        if next_minute >= 60:
            next_minute = 0

        if next_minute > minutes:
            wait_minutes = next_minute - minutes - 1
            wait_seconds = 60 - seconds
        else:
            wait_minutes = 60 - minutes + next_minute - 1
            wait_seconds = 60 - seconds

        total_seconds = wait_minutes * 60 + wait_seconds
        return total_seconds

    def execute_trade(self, symbol: str, signal: str, price: float):
        """Exécute un trade sur Polymarket"""
        base_symbol = symbol.split('/')[0]

        logger.info(f"🎯 EXÉCUTION TRADE | {base_symbol} | {signal} | Prix: ${price:,.2f}")

        # Vérifier cooldown (pas de trade sur le même symbole en moins de 15 min)
        last_trade = self.last_trade_time.get(symbol, datetime.min)
        if (datetime.utcnow() - last_trade).seconds < 900:
            logger.warning(f"⏳ Cooldown actif pour {symbol}")
            return

        if self.is_live:
            # Mode production - exécuter réellement
            try:
                order = self.polymarket.place_order(
                    symbol=base_symbol,
                    direction='BUY',
                    outcome=signal,  # UP ou DOWN
                    amount=self.bet_size,
                    price=None
                )

                if order:
                    logger.info(f"✅ ORDRE EXÉCUTÉ | ID: {order.get('order_id')}")

                    # Notification Telegram
                    self.telegram.send_message(f"""
🎯 <b>TRADE EXÉCUTÉ</b>

🪙 <b>Symbole:</b> {base_symbol}
📊 <b>Direction:</b> {signal}
💰 <b>Mise:</b> ${self.bet_size:.2f}
💵 <b>Prix BTC:</b> ${price:,.2f}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

            except Exception as e:
                logger.error(f"❌ Erreur exécution: {e}")
                self.telegram.notify_error(f"Erreur exécution {base_symbol}: {e}")

        else:
            # Mode simulation
            logger.info(f"🔵 [SIMULATION] Trade {signal} sur {base_symbol}")

            self.telegram.send_message(f"""
🔵 <b>SIGNAL (Simulation)</b>

🪙 <b>Symbole:</b> {base_symbol}
📊 <b>Direction:</b> {signal}
💰 <b>Mise:</b> ${self.bet_size:.2f}
💵 <b>Prix:</b> ${price:,.2f}

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        # Mettre à jour stats
        self.trades_today += 1
        self.last_trade_time[symbol] = datetime.utcnow()

    def run_once(self):
        """Exécute un cycle d'analyse"""
        logger.info("-" * 60)
        logger.info(f"🔍 ANALYSE | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        for symbol in self.symbols:
            logger.info(f"\n📊 Analyse {symbol}...")

            # Récupérer les bougies
            candles = self.get_candles(symbol)
            if not candles:
                continue

            # Générer le signal
            signal = self.strategy.generate_signal(candles)

            if signal:
                current_price = candles[-1]['close']
                self.execute_trade(symbol, signal, current_price)
            else:
                logger.info(f"   Aucun signal pour {symbol}")

    def run(self):
        """Boucle principale de trading"""
        mode = "🔴 PRODUCTION" if self.is_live else "🔵 SIMULATION"

        logger.info("=" * 60)
        logger.info(f"🤖 DÉMARRAGE LIVE TRADER - {mode}")
        logger.info("=" * 60)
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Mise par trade: ${self.bet_size}")
        logger.info(f"Stratégie: Mean Reversion (RSI + Bougies consécutives)")
        logger.info("=" * 60)

        # Notification démarrage
        self.telegram.send_message(f"""
🤖 <b>BOT DÉMARRÉ</b> - {mode}

📊 <b>Configuration:</b>
• Symboles: {', '.join([s.split('/')[0] for s in self.symbols])}
• Mise: ${self.bet_size}/trade
• Stratégie: Mean Reversion

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        try:
            while True:
                # Calculer le temps avant la prochaine bougie
                wait_time = self.get_time_to_next_candle()

                # Attendre 8 secondes avant la fin de la bougie
                if wait_time > 8:
                    sleep_time = wait_time - 8
                    logger.info(f"⏳ Prochaine analyse dans {sleep_time} secondes...")
                    time.sleep(sleep_time)

                # Exécuter l'analyse
                self.run_once()

                # Attendre la fin de la bougie + un peu de marge
                time.sleep(15)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Arrêt demandé par l'utilisateur")
            self.telegram.send_message("🛑 <b>BOT ARRÊTÉ</b> (manuel)")

        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
            self.telegram.notify_error(f"Erreur fatale: {e}")


def main():
    parser = argparse.ArgumentParser(description='Live Trader Polymarket')
    parser.add_argument('--live', action='store_true', help='Mode production (argent réel)')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT',
                        help='Symboles à trader (séparés par des virgules)')
    parser.add_argument('--bet', type=float, default=2.0, help='Mise par trade en USD')

    args = parser.parse_args()

    symbols = args.symbols.split(',')

    if args.live:
        print("\n" + "=" * 60)
        print("⚠️  ATTENTION: MODE PRODUCTION ACTIVÉ")
        print("    Vous allez trader avec de l'argent réel!")
        print("=" * 60)
        confirm = input("\nConfirmez en tapant 'OUI': ")
        if confirm != 'OUI':
            print("Annulé.")
            sys.exit(0)

    trader = LiveTrader(
        symbols=symbols,
        bet_size=args.bet,
        is_live=args.live
    )

    trader.run()


if __name__ == "__main__":
    main()
