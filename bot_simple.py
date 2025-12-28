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

# CONFIG HYBRIDE (~72/jour, 55%+ WR par pair)
# BTC/ETH: Config agressive (plus de trades)
# XRP: Config stricte (meilleur WR)

SYMBOL_CONFIG = {
    'BTC': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'expected_tpd': 30,
        'expected_wr': 56
    },
    'ETH': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'expected_tpd': 30,
        'expected_wr': 56
    },
    'XRP': {
        'rsi_period': 5,
        'rsi_oversold': 25,
        'rsi_overbought': 75,
        'stoch_period': 5,
        'stoch_oversold': 20,
        'stoch_overbought': 80,
        'consec_threshold': 2,
        'expected_tpd': 12,
        'expected_wr': 55
    }
}

MAX_PRICE = 0.52       # 52 centimes max (marge 3% vs 55% break-even)
BLOCKED_HOURS = []     # Aucune heure bloquée


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
        """Génère signal UP, DOWN ou None - CONFIG HYBRIDE par symbole"""
        if df is None or len(df) < 20:
            return None

        # Filtre des heures faibles
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in BLOCKED_HOURS:
            logger.info(f"⏰ Heure {current_hour}h bloquée - pas de trading")
            return None

        # Récupérer la config pour ce symbole
        base = symbol.split('/')[0]
        cfg = SYMBOL_CONFIG.get(base, SYMBOL_CONFIG['BTC'])

        # Calcul des indicateurs
        closes = df['close']
        rsi = self.calculate_rsi(closes, cfg['rsi_period'])
        stoch = self.calculate_stochastic(df, cfg['stoch_period'])
        consec_up, consec_down = self.count_consecutive(df)

        # Signal UP: RSI survendu + Stoch survendu (+ consec pour XRP)
        up_signal = (rsi < cfg['rsi_oversold']) and (stoch < cfg['stoch_oversold'])
        if cfg['consec_threshold'] > 1:
            up_signal = up_signal and (consec_down >= cfg['consec_threshold'])

        if up_signal:
            logger.info(f"📈 Signal UP | {base} | RSI={rsi:.1f} | Stoch={stoch:.1f} | DOWN={consec_down}")
            return 'UP'

        # Signal DOWN: RSI suracheté + Stoch suracheté (+ consec pour XRP)
        down_signal = (rsi > cfg['rsi_overbought']) and (stoch > cfg['stoch_overbought'])
        if cfg['consec_threshold'] > 1:
            down_signal = down_signal and (consec_up >= cfg['consec_threshold'])

        if down_signal:
            logger.info(f"📉 Signal DOWN | {base} | RSI={rsi:.1f} | Stoch={stoch:.1f} | UP={consec_up}")
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

        # Entrer 8 secondes avant
        return max(0, wait - 8)

    def run(self):
        """Boucle principale"""
        mode = "🔴 LIVE" if self.is_live else "🔵 SIMULATION"

        logger.info("=" * 60)
        logger.info(f"🤖 BOT HYBRIDE DÉMARRÉ - {mode}")
        logger.info("=" * 60)
        logger.info(f"Symboles: {', '.join(self.symbols)}")
        logger.info(f"Shares: {self.shares} (~${self.shares * 0.50:.2f} @ 50¢)")
        logger.info("CONFIG HYBRIDE:")
        for sym in self.symbols:
            base = sym.split('/')[0]
            cfg = SYMBOL_CONFIG.get(base, {})
            logger.info(f"  {base}: RSI({cfg.get('rsi_period')}) {cfg.get('rsi_oversold')}/{cfg.get('rsi_overbought')} + Stoch {cfg.get('stoch_oversold')}/{cfg.get('stoch_overbought')} | ~{cfg.get('expected_tpd')}/j ~{cfg.get('expected_wr')}%")
        logger.info(f"TOTAL ATTENDU: ~72 trades/jour | 55%+ WR par pair")
        logger.info("=" * 60)

        # Notification démarrage
        self.telegram.send_message(f"""
🤖 <b>BOT HYBRIDE</b> - {mode}

📊 Symboles: {', '.join([s.split('/')[0] for s in self.symbols])}
💰 Mise: {self.shares} shares (~${self.shares * 0.50:.2f})

⚙️ <b>Config HYBRIDE (~72/jour, 55%+ WR):</b>
• BTC: RSI(7) 35/65 + Stoch 30/70 (~30/j)
• ETH: RSI(7) 35/65 + Stoch 30/70 (~30/j)
• XRP: RSI(5) 25/75 + Stoch 20/80 (~12/j)

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
