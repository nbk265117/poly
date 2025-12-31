#!/usr/bin/env python3
"""
STRATEGIE HYBRIDE OPTIMALE
- SKIP les candles très mauvaises (WR < 45%)
- REVERSE les candles avec WR entre 40-45% (fortes pertes = fortes inversions)
- TRADE normal le reste
"""

import pandas as pd
import numpy as np
import yaml
from collections import defaultdict

print("=" * 70)
print("STRATEGIE HYBRIDE OPTIMALE: SKIP + REVERSE SELECTIF")
print("=" * 70)

# Paramètres
RSI_PERIOD = 7
RSI_LOW = 38
RSI_HIGH = 58
STOCH_PERIOD = 5
STOCH_LOW = 30
STOCH_HIGH = 80

def load_data(symbol):
    df = pd.read_csv(f'/Users/mac/poly/data/historical/{symbol}_USDT_15m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp').reset_index(drop=True)

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

# Charger les candles bloquées
with open('/Users/mac/poly/blocked_candles_235.yaml', 'r') as f:
    blocked_data = yaml.safe_load(f)
    blocked_candles = set((c['day'], c['hour'], c['minute']) for c in blocked_data['blocked_candles'])

# ETAPE 1: Analyser chaque candle bloquée pour trouver son WR exact
print("\n📊 Analyse WR par candle bloquée...")

candle_stats = defaultdict(lambda: {'wins': 0, 'losses': 0})

for symbol in ['BTC', 'ETH', 'XRP']:
    df = load_data(symbol)
    df = calculate_indicators(df)
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2026-01-01')]

    for idx in range(len(df) - 1):
        row = df.iloc[idx]
        signal = get_signal(row)
        if signal is None:
            continue

        next_close = df.iloc[idx + 1]['close']
        actual = 'UP' if next_close > row['close'] else 'DOWN'

        candle_key = (row['timestamp'].dayofweek, row['timestamp'].hour, row['timestamp'].minute)

        if candle_key in blocked_candles:
            is_win = (signal == actual)
            candle_stats[candle_key]['wins' if is_win else 'losses'] += 1

# Calculer WR et classifier
print("\n📋 Classification des 235 candles:")

candles_to_skip = []
candles_to_reverse = []
candles_analysis = []

for candle, stats in candle_stats.items():
    total = stats['wins'] + stats['losses']
    if total == 0:
        continue
    wr = stats['wins'] / total * 100
    wr_reversed = 100 - wr

    candles_analysis.append({
        'candle': candle,
        'trades': total,
        'wr_normal': wr,
        'wr_reversed': wr_reversed,
        'pnl_normal': stats['wins'] * 90.48 - stats['losses'] * 100,
        'pnl_reversed': stats['losses'] * 90.48 - stats['wins'] * 100
    })

df_analysis = pd.DataFrame(candles_analysis)
df_analysis = df_analysis.sort_values('wr_normal')

# Classifier:
# WR < 42% → REVERSE (WR inversé > 58%)
# WR 42-53% → SKIP
# WR > 53% → ne devrait pas être bloquée!

REVERSE_THRESHOLD = 42
SKIP_THRESHOLD = 48

for _, row in df_analysis.iterrows():
    if row['wr_normal'] < REVERSE_THRESHOLD:
        candles_to_reverse.append(row['candle'])
    else:
        candles_to_skip.append(row['candle'])

print(f"  Candles à REVERSER (WR < {REVERSE_THRESHOLD}%): {len(candles_to_reverse)}")
print(f"  Candles à SKIP (WR {REVERSE_THRESHOLD}-53%): {len(candles_to_skip)}")

# ETAPE 2: Backtest de la stratégie hybride
print("\n" + "=" * 70)
print("BACKTEST STRATEGIE HYBRIDE")
print("=" * 70)

results = {
    'v8_skip_all': {'wins': 0, 'losses': 0, 'pnl': 0},
    'hybrid': {'wins': 0, 'losses': 0, 'pnl': 0, 'reversed': 0, 'skipped': 0},
    'no_filter': {'wins': 0, 'losses': 0, 'pnl': 0}
}

monthly_pnl = defaultdict(lambda: {'v8': 0, 'hybrid': 0})

for symbol in ['BTC', 'ETH', 'XRP']:
    df = load_data(symbol)
    df = calculate_indicators(df)
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2026-01-01')]

    for idx in range(len(df) - 1):
        row = df.iloc[idx]
        signal = get_signal(row)
        if signal is None:
            continue

        next_close = df.iloc[idx + 1]['close']
        actual = 'UP' if next_close > row['close'] else 'DOWN'

        candle_key = (row['timestamp'].dayofweek, row['timestamp'].hour, row['timestamp'].minute)
        is_win_normal = (signal == actual)
        is_win_reversed = not is_win_normal

        month_key = row['timestamp'].strftime('%Y-%m')

        # Sans filtre
        results['no_filter']['wins' if is_win_normal else 'losses'] += 1
        results['no_filter']['pnl'] += 90.48 if is_win_normal else -100

        if candle_key in blocked_candles:
            # V8 Skip All
            # Ne rien faire (skip)

            # Hybride
            if candle_key in candles_to_reverse:
                # Reverser le signal
                results['hybrid']['wins' if is_win_reversed else 'losses'] += 1
                pnl_hybrid = 90.48 if is_win_reversed else -100
                results['hybrid']['pnl'] += pnl_hybrid
                results['hybrid']['reversed'] += 1
                monthly_pnl[month_key]['hybrid'] += pnl_hybrid
            else:
                # Skip
                results['hybrid']['skipped'] += 1
        else:
            # Candle normale - trader
            results['v8_skip_all']['wins' if is_win_normal else 'losses'] += 1
            pnl = 90.48 if is_win_normal else -100
            results['v8_skip_all']['pnl'] += pnl
            monthly_pnl[month_key]['v8'] += pnl

            results['hybrid']['wins' if is_win_normal else 'losses'] += 1
            results['hybrid']['pnl'] += pnl
            monthly_pnl[month_key]['hybrid'] += pnl

# Résultats
print("\n📊 RESULTATS COMPARATIFS")
print("-" * 50)

for name, data in [('V8 SKIP ALL', results['v8_skip_all']),
                   ('HYBRIDE', results['hybrid']),
                   ('SANS FILTRE', results['no_filter'])]:
    total = data['wins'] + data['losses']
    wr = data['wins'] / total * 100 if total > 0 else 0
    monthly = data['pnl'] / 24

    print(f"\n{name}")
    print(f"  Trades: {total:,}")
    print(f"  WR: {wr:.1f}%")
    print(f"  PnL Total: ${data['pnl']:,.0f}")
    print(f"  PnL/Mois: ${monthly:,.0f}")
    if 'reversed' in data:
        print(f"  Trades reversés: {data['reversed']:,}")
        print(f"  Trades skippés: {data['skipped']:,}")

# Analyse mensuelle
print("\n" + "=" * 70)
print("ANALYSE MENSUELLE: V8 vs HYBRIDE")
print("=" * 70)

df_monthly = pd.DataFrame([
    {'month': k, 'v8': v['v8'], 'hybrid': v['hybrid']}
    for k, v in sorted(monthly_pnl.items())
])

df_monthly['diff'] = df_monthly['hybrid'] - df_monthly['v8']

print(f"\n{'Mois':<10} {'V8':>12} {'Hybride':>12} {'Diff':>12}")
print("-" * 48)
for _, row in df_monthly.iterrows():
    emoji = "✅" if row['diff'] > 0 else "❌"
    print(f"{row['month']:<10} ${row['v8']:>10,.0f} ${row['hybrid']:>10,.0f} {emoji} ${row['diff']:>+,.0f}")

# Stats
print(f"\n📈 Mois où HYBRIDE > V8: {len(df_monthly[df_monthly['diff'] > 0])}/24")
print(f"📊 Gain moyen HYBRIDE: ${df_monthly['diff'].mean():+,.0f}/mois")

# Pire mois
worst_v8 = df_monthly['v8'].min()
worst_hybrid = df_monthly['hybrid'].min()
print(f"\n⚠️ Pire mois V8: ${worst_v8:,.0f}")
print(f"⚠️ Pire mois Hybride: ${worst_hybrid:,.0f}")

# Liste finale des candles à reverser
print("\n" + "=" * 70)
print("CANDLES A REVERSER (pour implémentation)")
print("=" * 70)

days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

df_reverse = df_analysis[df_analysis['wr_normal'] < REVERSE_THRESHOLD].sort_values('wr_normal')
print(f"\n{len(df_reverse)} candles avec WR < {REVERSE_THRESHOLD}% (WR inversé > {100-REVERSE_THRESHOLD}%):\n")

for _, row in df_reverse.iterrows():
    d, h, m = row['candle']
    print(f"  {days[d]} {h:02d}:{m:02d} - WR normal: {row['wr_normal']:.1f}% → WR reverse: {row['wr_reversed']:.1f}%")
