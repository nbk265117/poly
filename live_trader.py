#!/usr/bin/env python3
"""
LIVE TRADER V8.1 HYBRIDE - Stratégie RSI+Stoch pour Polymarket
Trading automatique BTC/ETH/XRP Up/Down 15 minutes

STRATEGIE HYBRIDE:
- RSI(7) < 38 AND Stoch(5) < 30 = Signal UP
- RSI(7) > 58 AND Stoch(5) > 80 = Signal DOWN
- 223 candles SKIP (pas de trade)
- 12 candles REVERSE (signal inversé)

PnL attendu: $23,750/mois (vs $22,891 V8 pure)

Usage:
    python live_trader.py              # Mode simulation
    python live_trader.py --live       # Mode production (argent réel)
"""

import os
import sys
import time
import logging
import argparse
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ajouter le path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

try:
    import ccxt
except ImportError:
    print("ccxt non installe. Executez: pip install ccxt")
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


class HybridStrategyV8:
    """
    Strategie V8.1 Hybride pour trading live
    RSI(7) + Stochastic(5) avec SKIP et REVERSE sur candles specifiques
    """

    def __init__(self):
        # Parametres strategie V8
        self.rsi_period = 7
        self.rsi_low = 38
        self.rsi_high = 58
        self.stoch_period = 5
        self.stoch_low = 30
        self.stoch_high = 80

        # Charger les candles hybrides
        self.skip_candles = set()
        self.reverse_candles = set()
        self._load_hybrid_candles()

    def _load_hybrid_candles(self):
        """Charge les candles SKIP et REVERSE depuis le fichier YAML"""
        yaml_path = Path(__file__).parent / 'blocked_candles_hybrid.yaml'

        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            # Charger les candles a SKIP
            for c in data.get('skip_candles', []):
                self.skip_candles.add((c['day'], c['hour'], c['minute']))

            # Charger les candles a REVERSE
            for c in data.get('reverse_candles', []):
                self.reverse_candles.add((c['day'], c['hour'], c['minute']))

            logger.info(f"Candles chargees: {len(self.skip_candles)} SKIP, {len(self.reverse_candles)} REVERSE")

        except Exception as e:
            logger.error(f"Erreur chargement candles hybrides: {e}")
            # Fallback: pas de filtres
            self.skip_candles = set()
            self.reverse_candles = set()

    def calculate_rsi(self, closes: list) -> float:
        """Calcule le RSI(7) sur une serie de prix"""
        if len(closes) < self.rsi_period + 1:
            return 50.0

        df = pd.Series(closes)
        delta = df.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    def calculate_stochastic(self, candles: list) -> float:
        """Calcule le Stochastic(5) K"""
        if len(candles) < self.stoch_period:
            return 50.0

        recent = candles[-self.stoch_period:]
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        close = candles[-1]['close']

        highest = max(highs)
        lowest = min(lows)

        if highest == lowest:
            return 50.0

        stoch_k = 100 * (close - lowest) / (highest - lowest)
        return stoch_k

    def get_candle_action(self, timestamp: datetime) -> str:
        """
        Determine l'action pour cette candle: TRADE, SKIP, ou REVERSE

        Args:
            timestamp: Timestamp de la candle

        Returns:
            'TRADE', 'SKIP', ou 'REVERSE'
        """
        day = timestamp.weekday()  # 0=Lundi, 6=Dimanche
        hour = timestamp.hour
        minute = timestamp.minute

        candle_key = (day, hour, minute)

        if candle_key in self.reverse_candles:
            return 'REVERSE'
        elif candle_key in self.skip_candles:
            return 'SKIP'
        else:
            return 'TRADE'

    def generate_signal(self, candles: list, current_time: datetime = None) -> tuple:
        """
        Genere un signal base sur RSI + Stochastic + filtres hybrides

        Args:
            candles: Liste de bougies OHLCV [{open, high, low, close, volume, timestamp}, ...]
            current_time: Timestamp actuel (pour determiner SKIP/REVERSE)

        Returns:
            (signal, action) - signal: 'UP', 'DOWN', None | action: 'TRADE', 'SKIP', 'REVERSE'
        """
        if len(candles) < max(self.rsi_period, self.stoch_period) + 5:
            return None, 'TRADE'

        # Determiner l'action pour cette candle
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        action = self.get_candle_action(current_time)

        # Si SKIP, pas de signal
        if action == 'SKIP':
            return None, 'SKIP'

        # Calculer les indicateurs
        closes = [c['close'] for c in candles]
        rsi = self.calculate_rsi(closes)
        stoch = self.calculate_stochastic(candles)

        signal = None

        # Signal UP: RSI < 38 AND Stoch < 30
        if rsi < self.rsi_low and stoch < self.stoch_low:
            signal = 'UP'
            logger.info(f"Signal UP | RSI={rsi:.1f} < {self.rsi_low} | Stoch={stoch:.1f} < {self.stoch_low}")

        # Signal DOWN: RSI > 58 AND Stoch > 80
        elif rsi > self.rsi_high and stoch > self.stoch_high:
            signal = 'DOWN'
            logger.info(f"Signal DOWN | RSI={rsi:.1f} > {self.rsi_high} | Stoch={stoch:.1f} > {self.stoch_high}")

        # Si REVERSE, inverser le signal
        if signal and action == 'REVERSE':
            original = signal
            signal = 'DOWN' if signal == 'UP' else 'UP'
            logger.info(f"REVERSE: {original} -> {signal}")

        return signal, action


class LiveTrader:
    """
    Trader live pour Polymarket - V8.1 Hybride
    """

    def __init__(self, symbols: list, bet_size: float = 2.0, is_live: bool = False):
        self.symbols = symbols
        self.bet_size = bet_size
        self.is_live = is_live

        # Initialiser les composants
        self.config = get_config()
        self.strategy = HybridStrategyV8()
        self.telegram = TelegramNotifier()
        self.polymarket = PolymarketClient()

        # Stats supplementaires pour hybride
        self.trades_reversed = 0
        self.trades_skipped = 0

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
        now = datetime.now(timezone.utc)
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
        last_trade = self.last_trade_time.get(symbol, datetime.min.replace(tzinfo=timezone.utc))
        if (datetime.now(timezone.utc) - last_trade).seconds < 900:
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

                    # Calcul du coût et gain potentiel
                    actual_price = order.get('price', 0.50)
                    bet_cost = self.bet_size * actual_price
                    to_win = self.bet_size * 1.00

                    # Notification Telegram
                    self.telegram.send_message(f"""
🎯 <b>TRADE EXÉCUTÉ</b>

🪙 <b>Symbole:</b> {base_symbol}
📊 <b>Direction:</b> {signal}
💵 <b>Prix {base_symbol}:</b> ${price:,.2f}

💰 <b>BET:</b> ${bet_cost:.2f} ({self.bet_size:.0f} shares @ {actual_price*100:.0f}¢)
🎯 <b>TO WIN:</b> ${to_win:.2f}

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
                else:
                    # Ordre non exécuté (probablement prix > 50¢)
                    logger.warning(f"⚠️ Trade {base_symbol} {signal} SKIPPED (prix > 50¢)")
                    self.telegram.send_message(f"""
⚠️ <b>TRADE SKIPPED</b>

🪙 <b>Symbole:</b> {base_symbol}
📊 <b>Signal:</b> {signal}
💵 <b>Prix {base_symbol}:</b> ${price:,.2f}

❌ <b>Raison:</b> Prix marché > 50¢
💡 On attend un meilleur prix

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
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

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        # Mettre à jour stats
        self.trades_today += 1
        self.last_trade_time[symbol] = datetime.now(timezone.utc)

    def run_once(self):
        """Execute un cycle d'analyse"""
        current_time = datetime.now(timezone.utc)
        logger.info("-" * 60)
        logger.info(f"ANALYSE | {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        for symbol in self.symbols:
            logger.info(f"\nAnalyse {symbol}...")

            # Recuperer les bougies
            candles = self.get_candles(symbol)
            if not candles:
                continue

            # Generer le signal avec action hybride
            signal, action = self.strategy.generate_signal(candles, current_time)

            if action == 'SKIP':
                self.trades_skipped += 1
                logger.info(f"   SKIP - Candle bloquee")
                continue

            if signal:
                current_price = candles[-1]['close']

                # Log si REVERSE
                if action == 'REVERSE':
                    self.trades_reversed += 1
                    logger.info(f"   REVERSE ACTIF - Signal inverse")

                self.execute_trade(symbol, signal, current_price)
            else:
                logger.info(f"   Aucun signal pour {symbol}")

    def run(self):
        """Boucle principale de trading"""
        mode = "PRODUCTION" if self.is_live else "SIMULATION"

        logger.info("=" * 60)
        logger.info(f"DEMARRAGE LIVE TRADER V8.1 HYBRIDE - {mode}")
        logger.info("=" * 60)
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Shares par trade: {self.bet_size:.0f} (~${self.bet_size * 0.525:.2f} BET @ 52.5c)")
        logger.info(f"Strategie: V8.1 Hybride (RSI+Stoch + SKIP/REVERSE)")
        logger.info(f"  - RSI(7): <{self.strategy.rsi_low} UP, >{self.strategy.rsi_high} DOWN")
        logger.info(f"  - Stoch(5): <{self.strategy.stoch_low} UP, >{self.strategy.stoch_high} DOWN")
        logger.info(f"  - Candles SKIP: {len(self.strategy.skip_candles)}")
        logger.info(f"  - Candles REVERSE: {len(self.strategy.reverse_candles)}")
        logger.info("=" * 60)

        # Notification demarrage
        bet_cost = self.bet_size * 0.525
        to_win = self.bet_size * 1.00
        self.telegram.send_message(f"""
<b>BOT V8.1 HYBRIDE</b> - {mode}

<b>Configuration:</b>
- Symboles: {', '.join([s.split('/')[0] for s in self.symbols])}
- BET: ${bet_cost:.2f} ({self.bet_size:.0f} shares @ 52.5c)
- TO WIN: ${to_win:.2f}

<b>Strategie V8.1:</b>
- RSI(7) {self.strategy.rsi_low}/{self.strategy.rsi_high}
- Stoch(5) {self.strategy.stoch_low}/{self.strategy.stoch_high}
- {len(self.strategy.skip_candles)} SKIP + {len(self.strategy.reverse_candles)} REVERSE

<b>PnL attendu:</b> $23,750/mois

{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
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
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation (pour systemd)')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,XRP/USDT',
                        help='Symboles à trader (séparés par des virgules)')
    parser.add_argument('--shares', type=float, default=5.0, help='Nombre de shares par trade (5 shares @ 50¢ = $2.50 BET)')

    args = parser.parse_args()

    symbols = args.symbols.split(',')

    if args.live and not args.yes:
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
        bet_size=args.shares,
        is_live=args.live
    )

    trader.run()


if __name__ == "__main__":
    main()
