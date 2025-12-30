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

# Logging - éviter les doublons
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    Path('logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler('logs/bot_simple.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False  # Éviter propagation aux loggers parents

# CONFIG OPTIMISEE V8 - 235 FILTRES CANDLE 15min (WR < 53%)
# PnL: +$22,891/mois | WR: 59.2% | Pire mois: +$14,761
# Strategie unifiee: RSI(7) 38/58 + Stoch(5) 30/80

SYMBOL_CONFIG = {
    'BTC': {
        'rsi_period': 7,
        'rsi_oversold': 38,
        'rsi_overbought': 58,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 80,
        'consec_threshold': 1,
        'expected_tpd': 20,
        'expected_wr': 59
    },
    'ETH': {
        'rsi_period': 7,
        'rsi_oversold': 38,
        'rsi_overbought': 58,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 80,
        'consec_threshold': 1,
        'expected_tpd': 20,
        'expected_wr': 59
    },
    'XRP': {
        'rsi_period': 7,
        'rsi_oversold': 38,
        'rsi_overbought': 58,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 80,
        'consec_threshold': 1,
        'expected_tpd': 19,
        'expected_wr': 59
    }
}

# 235 CANDLES BLOQUEES (WR < 53%) - Format: (day, hour, minute)
# day: 0=Lundi, 1=Mardi, ..., 6=Dimanche
BLOCKED_CANDLES = {
    # Lundi (44 candles)
    (0, 0, 0), (0, 0, 15), (0, 0, 30), (0, 1, 30), (0, 1, 45), (0, 2, 0), (0, 2, 45),
    (0, 3, 0), (0, 3, 15), (0, 3, 30), (0, 4, 30), (0, 5, 30), (0, 6, 15), (0, 6, 30),
    (0, 7, 0), (0, 7, 15), (0, 7, 30), (0, 8, 0), (0, 9, 0), (0, 11, 30),
    (0, 14, 15), (0, 14, 30), (0, 14, 45), (0, 15, 0), (0, 15, 15), (0, 15, 30), (0, 15, 45),
    (0, 16, 45), (0, 17, 15), (0, 17, 30), (0, 18, 0), (0, 18, 15), (0, 18, 30),
    (0, 19, 0), (0, 19, 15), (0, 19, 30), (0, 20, 15), (0, 20, 30), (0, 20, 45),
    (0, 21, 0), (0, 21, 30), (0, 22, 0), (0, 23, 0), (0, 23, 30),
    # Mardi (33 candles)
    (1, 0, 0), (1, 1, 15), (1, 1, 30), (1, 2, 45), (1, 3, 15), (1, 4, 15), (1, 4, 30),
    (1, 5, 0), (1, 5, 15), (1, 6, 0), (1, 7, 0), (1, 7, 30), (1, 7, 45),
    (1, 9, 0), (1, 9, 30), (1, 10, 15), (1, 11, 15), (1, 14, 15), (1, 15, 0), (1, 15, 30),
    (1, 16, 30), (1, 17, 0), (1, 18, 0), (1, 18, 15), (1, 18, 45),
    (1, 19, 0), (1, 19, 15), (1, 19, 30), (1, 20, 0), (1, 22, 15), (1, 22, 30), (1, 22, 45), (1, 23, 0),
    # Mercredi (31 candles)
    (2, 0, 0), (2, 0, 15), (2, 0, 30), (2, 2, 45), (2, 3, 15), (2, 3, 30), (2, 4, 15),
    (2, 5, 0), (2, 6, 30), (2, 7, 0), (2, 7, 30), (2, 8, 0), (2, 8, 15), (2, 8, 30),
    (2, 9, 15), (2, 9, 30), (2, 10, 30), (2, 11, 15), (2, 15, 0), (2, 16, 0), (2, 16, 45),
    (2, 17, 15), (2, 17, 30), (2, 18, 0), (2, 18, 30), (2, 19, 30), (2, 20, 30),
    (2, 21, 45), (2, 23, 0), (2, 23, 15), (2, 23, 45),
    # Jeudi (42 candles)
    (3, 0, 0), (3, 0, 15), (3, 1, 30), (3, 2, 0), (3, 2, 15), (3, 3, 0), (3, 3, 30),
    (3, 4, 0), (3, 4, 15), (3, 4, 30), (3, 5, 15), (3, 5, 30), (3, 5, 45),
    (3, 6, 15), (3, 6, 30), (3, 7, 0), (3, 7, 30), (3, 7, 45), (3, 8, 0), (3, 8, 30),
    (3, 9, 0), (3, 9, 30), (3, 10, 30), (3, 11, 0), (3, 11, 15), (3, 12, 30),
    (3, 13, 15), (3, 13, 30), (3, 13, 45), (3, 14, 30), (3, 15, 15), (3, 15, 30),
    (3, 16, 0), (3, 16, 30), (3, 18, 30), (3, 19, 30), (3, 20, 30), (3, 21, 0),
    (3, 22, 0), (3, 22, 15), (3, 22, 30), (3, 23, 15),
    # Vendredi (40 candles)
    (4, 0, 30), (4, 2, 0), (4, 2, 15), (4, 2, 30), (4, 3, 0), (4, 4, 15), (4, 4, 30),
    (4, 5, 0), (4, 5, 15), (4, 5, 30), (4, 6, 0), (4, 6, 30), (4, 7, 0), (4, 7, 15), (4, 7, 30),
    (4, 8, 0), (4, 8, 45), (4, 10, 0), (4, 10, 30), (4, 10, 45), (4, 11, 0),
    (4, 13, 15), (4, 14, 15), (4, 14, 30), (4, 14, 45), (4, 15, 15), (4, 15, 30), (4, 15, 45),
    (4, 16, 15), (4, 16, 45), (4, 17, 0), (4, 17, 15), (4, 17, 30), (4, 18, 15),
    (4, 19, 0), (4, 20, 0), (4, 22, 0), (4, 22, 15), (4, 23, 0), (4, 23, 15),
    # Samedi (18 candles)
    (5, 0, 0), (5, 0, 15), (5, 1, 15), (5, 3, 0), (5, 3, 15), (5, 4, 15),
    (5, 6, 0), (5, 8, 15), (5, 8, 30), (5, 9, 45), (5, 10, 30), (5, 12, 15),
    (5, 13, 0), (5, 15, 15), (5, 19, 15), (5, 20, 30), (5, 22, 30), (5, 22, 45),
    # Dimanche (27 candles)
    (6, 0, 45), (6, 1, 30), (6, 2, 30), (6, 4, 0), (6, 4, 30), (6, 5, 30), (6, 5, 45),
    (6, 6, 30), (6, 7, 15), (6, 8, 30), (6, 8, 45), (6, 11, 15), (6, 13, 15), (6, 13, 30),
    (6, 15, 30), (6, 16, 30), (6, 17, 0), (6, 17, 15), (6, 19, 0), (6, 19, 45),
    (6, 21, 45), (6, 22, 0), (6, 22, 30), (6, 22, 45), (6, 23, 0), (6, 23, 15), (6, 23, 30),
}

MAX_PRICE = 0.53       # 53 centimes max (marge 2% vs 55% break-even)


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

    def calculate_rsi(self, closes: pd.Series, period: int = 14) -> float:
        """RSI avec période configurable"""
        delta = closes.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def calculate_stochastic(self, df: pd.DataFrame, period: int = 5) -> float:
        """Stochastic %K"""
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        stoch = 100 * (df['close'] - low_min) / (high_max - low_min)
        return stoch.iloc[-1]

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

    def get_signal(self, df: pd.DataFrame, symbol: str) -> str:
        """Génère signal UP, DOWN ou None - CONFIG V8 avec filtrage 15min"""
        if df is None or len(df) < 20:
            return None

        # Récupérer la config pour ce symbole
        base = symbol.split('/')[0]
        cfg = SYMBOL_CONFIG.get(base, SYMBOL_CONFIG['BTC'])

        # Filtre des candles 15min (235 candles bloquées)
        now = datetime.now(timezone.utc)
        current_day = now.weekday()  # 0=Lundi, 6=Dimanche
        current_hour = now.hour
        current_minute = (now.minute // 15) * 15  # Arrondi au quart d'heure

        candle_key = (current_day, current_hour, current_minute)
        if candle_key in BLOCKED_CANDLES:
            logger.info(f"⏰ Candle bloquée: {['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'][current_day]} {current_hour:02d}:{current_minute:02d} UTC")
            return None

        # Calcul des indicateurs
        closes = df['close']
        rsi = self.calculate_rsi(closes, cfg['rsi_period'])
        stoch = self.calculate_stochastic(df, cfg['stoch_period'])

        # Signal UP: RSI < 38 AND Stoch < 30
        if rsi < cfg['rsi_oversold'] and stoch < cfg['stoch_oversold']:
            logger.info(f"📈 Signal UP | {base} | RSI={rsi:.1f} | Stoch={stoch:.1f}")
            return 'UP'

        # Signal DOWN: RSI > 58 AND Stoch > 80
        if rsi > cfg['rsi_overbought'] and stoch > cfg['stoch_overbought']:
            logger.info(f"📉 Signal DOWN | {base} | RSI={rsi:.1f} | Stoch={stoch:.1f}")
            return 'DOWN'

        return None

    def execute_trade(self, symbol: str, signal: str, current_price: float):
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

                    # Notification Telegram - Prix formaté selon le symbole
                    price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
                    self.telegram.send_message(f"""
🎯 <b>TRADE PLACÉ</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
🎯 <b>TO WIN:</b> ${potential_win:.2f}
💵 <b>Prix {base}:</b> {price_fmt}

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
            price_fmt = f"${current_price:,.0f}" if current_price > 100 else f"${current_price:.2f}"
            self.telegram.send_message(f"""
🔵 <b>SIGNAL (Simulation)</b>

🪙 <b>Marché:</b> {base} {signal}
💰 <b>BET:</b> ${bet_cost:.2f} ({self.shares} shares)
💵 <b>Prix {base}:</b> {price_fmt}

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

        # Entrer 20 secondes avant (conseil Adnane)
        return max(0, wait - 20)

    def run(self):
        """Boucle principale"""
        mode = "🔴 LIVE" if self.is_live else "🔵 SIMULATION"

        logger.info("=" * 60)
        logger.info(f"🤖 BOT V8 - 235 FILTRES 15min - {mode}")
        logger.info("=" * 60)
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Shares: {self.shares} (~${self.shares * 0.525:.2f} @ 52.5¢)")
        logger.info(f"Stratégie: RSI(7) 38/58 + Stoch(5) 30/80")
        logger.info(f"Filtres: 235 candles bloquées (WR < 53%)")
        total_tpd = 0
        for sym in self.symbols:
            base = sym.split('/')[0]
            cfg = SYMBOL_CONFIG.get(base, {})
            logger.info(f"  {base}: ~{cfg.get('expected_tpd', 20)}/jour | WR ~{cfg.get('expected_wr', 59)}%")
            total_tpd += cfg.get('expected_tpd', 20)
        logger.info(f"TOTAL ATTENDU: ~{total_tpd} trades/jour | 59% WR | +$22,891/mois")
        logger.info("=" * 60)

        # Notification démarrage
        self.telegram.send_message(f"""
🤖 <b>BOT V8 - 235 FILTRES 15min</b> - {mode}

📊 Symboles: {', '.join([s.split('/')[0] for s in self.symbols])}
💰 Mise: {self.shares} shares (~${self.shares * 0.525:.2f})

⚙️ <b>Config V8 (~{total_tpd}/jour, 59% WR):</b>
• RSI(7) 38/58 + Stoch(5) 30/80
• 235 candles bloquées (WR < 53%)
• PnL attendu: +$22,891/mois

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

                    signal = self.get_signal(df, symbol)

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
    parser.add_argument('--yes', action='store_true', help='Skip confirmation (pour VPS)')
    parser.add_argument('--shares', type=int, default=5, help='Nombre de shares par trade')
    parser.add_argument('--symbols', type=str, default='BTC/USDT,ETH/USDT,XRP/USDT')

    args = parser.parse_args()

    if args.live and not args.yes:
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
