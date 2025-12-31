#!/usr/bin/env python3
"""
DETECTION DYNAMIQUE des mauvaises candles
Au lieu d'une liste statique, on utilise un rolling window pour
détecter en temps réel les candles à éviter/reverser
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import yaml

print("=" * 70)
print("DETECTION DYNAMIQUE vs LISTE STATIQUE")
print("=" * 70)

# Paramètres stratégie V8
RSI_PERIOD = 7
RSI_LOW = 38
RSI_HIGH = 58
STOCH_PERIOD = 5
STOCH_LOW = 30
STOCH_HIGH = 80

# Paramètres détection dynamique
ROLLING_WINDOW = 20  # Derniers N trades par candle pour calculer WR
MIN_TRADES = 5       # Minimum trades pour décider
WR_SKIP_THRESHOLD = 48  # Skip si WR < 48%
WR_REVERSE_THRESHOLD = 45  # Reverse si WR < 45%

def load_data(symbol):
    df = pd.read_csv(f'/Users/mac/poly/data/historical/{symbol}_USDT_15m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df

def calculate_indicators(df):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    low_min = df['low'].rolling(window=STOCH_PERIOD).min()
    high_max = df['high'].rolling(window=STOCH_PERIOD).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    return df

def get_signal(row):
    if pd.isna(row['rsi']) or pd.isna(row['stoch_k']):
        return None
    if row['rsi'] < RSI_LOW and row['stoch_k'] < STOCH_LOW:
        return 'UP'
    elif row['rsi'] > RSI_HIGH and row['stoch_k'] > STOCH_HIGH:
        return 'DOWN'
    return None

def get_actual_result(df, idx):
    if idx + 1 >= len(df):
        return None
    next_close = df.iloc[idx + 1]['close']
    current_close = df.iloc[idx]['close']
    return 'UP' if next_close > current_close else 'DOWN'

class DynamicDetector:
    """Detecteur dynamique basé sur rolling window"""
    def __init__(self, window=20, min_trades=5, skip_threshold=48, reverse_threshold=45):
        self.window = window
        self.min_trades = min_trades
        self.skip_threshold = skip_threshold
        self.reverse_threshold = reverse_threshold
        # Historique par candle: {(day, hour, minute): [list of (is_win, timestamp)]}
        self.history = defaultdict(list)

    def update(self, candle_key, is_win, timestamp):
        """Ajouter un résultat à l'historique"""
        self.history[candle_key].append((is_win, timestamp))
        # Garder seulement les N derniers
        if len(self.history[candle_key]) > self.window:
            self.history[candle_key] = self.history[candle_key][-self.window:]

    def get_action(self, candle_key):
        """Décider: TRADE, SKIP, ou REVERSE"""
        history = self.history[candle_key]
        if len(history) < self.min_trades:
            return 'TRADE'  # Pas assez de données

        wins = sum(1 for w, _ in history if w)
        wr = wins / len(history) * 100

        if wr < self.reverse_threshold:
            return 'REVERSE'
        elif wr < self.skip_threshold:
            return 'SKIP'
        else:
            return 'TRADE'

def simulate_dynamic(df, symbol):
    """Simulation avec détection dynamique"""
    detector = DynamicDetector(
        window=ROLLING_WINDOW,
        min_trades=MIN_TRADES,
        skip_threshold=WR_SKIP_THRESHOLD,
        reverse_threshold=WR_REVERSE_THRESHOLD
    )

    results = {
        'dynamic': {'wins': 0, 'losses': 0, 'pnl': 0, 'trades': 0, 'skipped': 0, 'reversed': 0},
        'baseline': {'wins': 0, 'losses': 0, 'pnl': 0}
    }

    for idx in range(len(df) - 1):
        row = df.iloc[idx]
        signal = get_signal(row)

        if signal is None:
            continue

        actual = get_actual_result(df, idx)
        if actual is None:
            continue

        day = row['timestamp'].dayofweek
        hour = row['timestamp'].hour
        minute = row['timestamp'].minute
        candle_key = (day, hour, minute)

        is_win_normal = (signal == actual)

        # Baseline (sans filtre)
        results['baseline']['wins' if is_win_normal else 'losses'] += 1
        results['baseline']['pnl'] += 90.48 if is_win_normal else -100

        # Détection dynamique
        action = detector.get_action(candle_key)

        if action == 'TRADE':
            # Trade normal
            results['dynamic']['wins' if is_win_normal else 'losses'] += 1
            results['dynamic']['pnl'] += 90.48 if is_win_normal else -100
            results['dynamic']['trades'] += 1
        elif action == 'SKIP':
            results['dynamic']['skipped'] += 1
        elif action == 'REVERSE':
            # Signal inversé
            is_win_reversed = not is_win_normal
            results['dynamic']['wins' if is_win_reversed else 'losses'] += 1
            results['dynamic']['pnl'] += 90.48 if is_win_reversed else -100
            results['dynamic']['reversed'] += 1
            results['dynamic']['trades'] += 1

        # Mettre à jour l'historique (APRES la décision)
        detector.update(candle_key, is_win_normal, row['timestamp'])

    return results, detector

# Tester plusieurs configurations
configs = [
    {'window': 10, 'min': 3, 'skip': 48, 'reverse': 42},
    {'window': 20, 'min': 5, 'skip': 48, 'reverse': 45},
    {'window': 30, 'min': 8, 'skip': 50, 'reverse': 45},
    {'window': 50, 'min': 10, 'skip': 50, 'reverse': 45},
]

print("\n" + "=" * 70)
print("TEST PLUSIEURS CONFIGURATIONS DYNAMIQUES")
print("=" * 70)

best_config = None
best_pnl = -float('inf')

for config in configs:
    print(f"\n--- Window={config['window']}, Min={config['min']}, Skip<{config['skip']}%, Reverse<{config['reverse']}% ---")

    total_dynamic = {'wins': 0, 'losses': 0, 'pnl': 0, 'trades': 0, 'skipped': 0, 'reversed': 0}
    total_baseline = {'wins': 0, 'losses': 0, 'pnl': 0}

    # Update global params
    ROLLING_WINDOW = config['window']
    MIN_TRADES = config['min']
    WR_SKIP_THRESHOLD = config['skip']
    WR_REVERSE_THRESHOLD = config['reverse']

    for symbol in ['BTC', 'ETH', 'XRP']:
        df = load_data(symbol)
        df = calculate_indicators(df)
        df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2026-01-01')]

        results, detector = simulate_dynamic(df, symbol)

        for key in total_dynamic:
            total_dynamic[key] += results['dynamic'][key]
        for key in total_baseline:
            total_baseline[key] += results['baseline'][key]

    # Stats
    dyn_total = total_dynamic['wins'] + total_dynamic['losses']
    dyn_wr = total_dynamic['wins'] / dyn_total * 100 if dyn_total > 0 else 0
    dyn_monthly = total_dynamic['pnl'] / 24

    base_total = total_baseline['wins'] + total_baseline['losses']
    base_wr = total_baseline['wins'] / base_total * 100 if base_total > 0 else 0

    print(f"  Trades exécutés: {total_dynamic['trades']:,} ({total_dynamic['skipped']:,} skip, {total_dynamic['reversed']:,} reverse)")
    print(f"  WR: {dyn_wr:.1f}%")
    print(f"  PnL/mois: ${dyn_monthly:,.0f}")

    if dyn_monthly > best_pnl:
        best_pnl = dyn_monthly
        best_config = config

print("\n" + "=" * 70)
print("MEILLEURE CONFIG DYNAMIQUE")
print("=" * 70)
print(f"Window={best_config['window']}, Min={best_config['min']}, Skip<{best_config['skip']}%, Reverse<{best_config['reverse']}%")
print(f"PnL/mois: ${best_pnl:,.0f}")

# Comparer avec V8 statique
print("\n" + "=" * 70)
print("COMPARAISON FINALE")
print("=" * 70)

# Charger V8 pour référence
with open('/Users/mac/poly/blocked_candles_235.yaml', 'r') as f:
    blocked_data = yaml.safe_load(f)
    blocked_candles = set((c['day'], c['hour'], c['minute']) for c in blocked_data['blocked_candles'])

total_v8 = {'wins': 0, 'losses': 0, 'pnl': 0}
for symbol in ['BTC', 'ETH', 'XRP']:
    df = load_data(symbol)
    df = calculate_indicators(df)
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2026-01-01')]

    for idx in range(len(df) - 1):
        row = df.iloc[idx]
        signal = get_signal(row)
        if signal is None:
            continue
        actual = get_actual_result(df, idx)
        if actual is None:
            continue

        candle_key = (row['timestamp'].dayofweek, row['timestamp'].hour, row['timestamp'].minute)
        if candle_key not in blocked_candles:
            is_win = (signal == actual)
            total_v8['wins' if is_win else 'losses'] += 1
            total_v8['pnl'] += 90.48 if is_win else -100

v8_total = total_v8['wins'] + total_v8['losses']
v8_wr = total_v8['wins'] / v8_total * 100
v8_monthly = total_v8['pnl'] / 24

print(f"""
📊 V8 STATIQUE (235 candles bloquées)
   Trades: {v8_total:,}
   WR: {v8_wr:.1f}%
   PnL/mois: ${v8_monthly:,.0f}

🔄 DYNAMIQUE (meilleure config)
   PnL/mois: ${best_pnl:,.0f}

📈 Différence: ${best_pnl - v8_monthly:,.0f}/mois
""")

if best_pnl > v8_monthly:
    print("✅ DYNAMIQUE est MEILLEUR!")
else:
    print("⭐ V8 STATIQUE reste MEILLEUR")
    print(f"   Avantage V8: ${v8_monthly - best_pnl:,.0f}/mois")
