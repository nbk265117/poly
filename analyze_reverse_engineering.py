#!/usr/bin/env python3
"""
Analyse Reverse Engineering vs Skip vs Dynamic Detection
- Skip: Bloquer les 235 candles (actuel V8)
- Reverse: Inverser le signal sur ces candles
- Dynamic: Detection adaptative basée sur rolling window
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml

# Charger les données
print("=" * 70)
print("ANALYSE: REVERSE ENGINEERING vs SKIP vs DYNAMIC")
print("=" * 70)

# Paramètres stratégie V8
RSI_PERIOD = 7
RSI_LOW = 38
RSI_HIGH = 58
STOCH_PERIOD = 5
STOCH_LOW = 30
STOCH_HIGH = 80

# Charger les 235 candles bloquées
with open('/Users/mac/poly/blocked_candles_235.yaml', 'r') as f:
    blocked_data = yaml.safe_load(f)
    # Format: {day: X, hour: Y, minute: Z}
    blocked_candles = set((c['day'], c['hour'], c['minute']) for c in blocked_data['blocked_candles'])

print(f"\n📊 Candles bloquées chargées: {len(blocked_candles)}")

def load_data(symbol):
    """Charger données historiques"""
    df = pd.read_csv(f'/Users/mac/poly/data/historical/{symbol}_USDT_15m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    return df

def calculate_indicators(df):
    """Calculer RSI et Stochastic"""
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic
    low_min = df['low'].rolling(window=STOCH_PERIOD).min()
    high_max = df['high'].rolling(window=STOCH_PERIOD).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    return df

def get_signal(row):
    """Signal basé sur RSI + Stochastic"""
    if pd.isna(row['rsi']) or pd.isna(row['stoch_k']):
        return None

    if row['rsi'] < RSI_LOW and row['stoch_k'] < STOCH_LOW:
        return 'UP'
    elif row['rsi'] > RSI_HIGH and row['stoch_k'] > STOCH_HIGH:
        return 'DOWN'
    return None

def get_actual_result(df, idx):
    """Résultat réel de la prochaine bougie"""
    if idx + 1 >= len(df):
        return None
    next_close = df.iloc[idx + 1]['close']
    current_close = df.iloc[idx]['close']
    return 'UP' if next_close > current_close else 'DOWN'

def simulate_strategies(df, symbol):
    """Simuler les 3 stratégies"""
    results = {
        'skip': {'wins': 0, 'losses': 0, 'pnl': 0},
        'reverse': {'wins': 0, 'losses': 0, 'pnl': 0},
        'all_signals': {'wins': 0, 'losses': 0, 'pnl': 0}
    }

    # Pour analyse détaillée des candles bloquées
    blocked_analysis = []

    # Rolling window pour detection dynamique
    rolling_stats = {}  # (day, hour, minute) -> list of recent results

    for idx in range(len(df) - 1):
        row = df.iloc[idx]
        signal = get_signal(row)

        if signal is None:
            continue

        actual = get_actual_result(df, idx)
        if actual is None:
            continue

        # Candle info
        day = row['timestamp'].dayofweek
        hour = row['timestamp'].hour
        minute = row['timestamp'].minute
        candle_key = (day, hour, minute)

        is_blocked = candle_key in blocked_candles
        is_win_normal = (signal == actual)
        is_win_reversed = (signal != actual)  # Signal inversé = gagne si normal perd

        # Stratégie 1: ALL (sans filtre)
        results['all_signals']['wins' if is_win_normal else 'losses'] += 1
        results['all_signals']['pnl'] += 90.48 if is_win_normal else -100

        if is_blocked:
            # Analyse de la candle bloquée
            blocked_analysis.append({
                'candle': candle_key,
                'signal': signal,
                'actual': actual,
                'win_if_normal': is_win_normal,
                'win_if_reversed': is_win_reversed,
                'timestamp': row['timestamp']
            })

            # Stratégie 2: SKIP (V8 actuel) - on ne trade pas
            # Pas de comptage

            # Stratégie 3: REVERSE - on inverse le signal
            results['reverse']['wins' if is_win_reversed else 'losses'] += 1
            results['reverse']['pnl'] += 90.48 if is_win_reversed else -100

        else:
            # Candle non bloquée - on trade normalement
            results['skip']['wins' if is_win_normal else 'losses'] += 1
            results['skip']['pnl'] += 90.48 if is_win_normal else -100

    return results, blocked_analysis

# Analyser chaque paire
all_results = {'skip': {'wins': 0, 'losses': 0, 'pnl': 0},
               'reverse': {'wins': 0, 'losses': 0, 'pnl': 0},
               'all_signals': {'wins': 0, 'losses': 0, 'pnl': 0}}

all_blocked_analysis = []

for symbol in ['BTC', 'ETH', 'XRP']:
    print(f"\n{'='*50}")
    print(f"Analyse {symbol}...")

    df = load_data(symbol)
    df = calculate_indicators(df)

    # Filtrer 2024-2025
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] < '2026-01-01')]

    results, blocked = simulate_strategies(df, symbol)
    all_blocked_analysis.extend(blocked)

    for strategy in ['skip', 'reverse', 'all_signals']:
        for key in ['wins', 'losses', 'pnl']:
            all_results[strategy][key] += results[strategy][key]

    # Stats par paire
    for strat_name, strat_data in results.items():
        total = strat_data['wins'] + strat_data['losses']
        wr = strat_data['wins'] / total * 100 if total > 0 else 0
        print(f"  {strat_name:12}: {total:,} trades, WR={wr:.1f}%, PnL=${strat_data['pnl']:,.0f}")

# Résultats globaux
print("\n" + "=" * 70)
print("RESULTATS GLOBAUX (BTC + ETH + XRP)")
print("=" * 70)

for strat_name, strat_data in all_results.items():
    total = strat_data['wins'] + strat_data['losses']
    wr = strat_data['wins'] / total * 100 if total > 0 else 0
    monthly_pnl = strat_data['pnl'] / 24  # 24 mois

    emoji = "⭐" if strat_name == 'skip' else ("🔄" if strat_name == 'reverse' else "📊")
    label = {
        'skip': 'V8 SKIP (actuel)',
        'reverse': 'REVERSE SIGNAL',
        'all_signals': 'SANS FILTRE'
    }[strat_name]

    print(f"\n{emoji} {label}")
    print(f"   Trades: {total:,}")
    print(f"   Win Rate: {wr:.1f}%")
    print(f"   PnL Total: ${strat_data['pnl']:,.0f}")
    print(f"   PnL/Mois: ${monthly_pnl:,.0f}")

# Analyse des candles bloquées - est-ce que reverse marche?
print("\n" + "=" * 70)
print("ANALYSE DETAILLEE DES 235 CANDLES BLOQUEES")
print("=" * 70)

df_blocked = pd.DataFrame(all_blocked_analysis)
if len(df_blocked) > 0:
    # Stats globales sur candles bloquées
    wins_normal = df_blocked['win_if_normal'].sum()
    wins_reversed = df_blocked['win_if_reversed'].sum()
    total_blocked_trades = len(df_blocked)

    wr_normal = wins_normal / total_blocked_trades * 100
    wr_reversed = wins_reversed / total_blocked_trades * 100

    print(f"\nTrades sur candles bloquées: {total_blocked_trades:,}")
    print(f"WR si signal NORMAL: {wr_normal:.1f}% ({wins_normal:,} wins)")
    print(f"WR si signal REVERSE: {wr_reversed:.1f}% ({wins_reversed:,} wins)")

    # PnL potentiel si on reverse
    pnl_normal = wins_normal * 90.48 - (total_blocked_trades - wins_normal) * 100
    pnl_reversed = wins_reversed * 90.48 - (total_blocked_trades - wins_reversed) * 100

    print(f"\nPnL si NORMAL: ${pnl_normal:,.0f}")
    print(f"PnL si REVERSE: ${pnl_reversed:,.0f}")

    # Analyse par candle - lesquelles marchent en reverse?
    print("\n" + "-" * 50)
    print("TOP 20 CANDLES où REVERSE est profitable")
    print("-" * 50)

    candle_stats = df_blocked.groupby('candle').agg({
        'win_if_normal': ['sum', 'count'],
        'win_if_reversed': 'sum'
    }).reset_index()
    candle_stats.columns = ['candle', 'wins_normal', 'total', 'wins_reversed']
    candle_stats['wr_normal'] = candle_stats['wins_normal'] / candle_stats['total'] * 100
    candle_stats['wr_reversed'] = candle_stats['wins_reversed'] / candle_stats['total'] * 100
    candle_stats['pnl_normal'] = candle_stats['wins_normal'] * 90.48 - (candle_stats['total'] - candle_stats['wins_normal']) * 100
    candle_stats['pnl_reversed'] = candle_stats['wins_reversed'] * 90.48 - (candle_stats['total'] - candle_stats['wins_reversed']) * 100

    # Candles où reverse > 55%
    good_reverse = candle_stats[candle_stats['wr_reversed'] > 55].sort_values('wr_reversed', ascending=False)

    days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    print(f"\n{'Candle':<20} {'Trades':<8} {'WR Normal':<12} {'WR Reverse':<12} {'PnL Reverse':<12}")
    print("-" * 64)

    for _, row in good_reverse.head(20).iterrows():
        d, h, m = row['candle']
        candle_str = f"{days[d]} {h:02d}:{m:02d}"
        print(f"{candle_str:<20} {int(row['total']):<8} {row['wr_normal']:.1f}%{'':<7} {row['wr_reversed']:.1f}%{'':<7} ${row['pnl_reversed']:,.0f}")

    # Combien de candles sont profitables en reverse?
    profitable_reverse = candle_stats[candle_stats['wr_reversed'] > 52.5]
    print(f"\n📊 Candles profitables en REVERSE (WR > 52.5%): {len(profitable_reverse)}/{len(candle_stats)}")

    # Stratégie hybride: skip les mauvaises, reverse les bonnes
    print("\n" + "=" * 70)
    print("STRATEGIE HYBRIDE: SKIP + REVERSE SELECTIF")
    print("=" * 70)

    # Identifier les candles à reverser vs skip
    candles_to_reverse = set(tuple(row['candle']) for _, row in candle_stats[candle_stats['wr_reversed'] > 55].iterrows())
    candles_to_skip = blocked_candles - candles_to_reverse

    print(f"\nCandles à REVERSER (WR reverse > 55%): {len(candles_to_reverse)}")
    print(f"Candles à SKIP: {len(candles_to_skip)}")

    # Calculer PnL hybride
    pnl_from_reverse = candle_stats[candle_stats['wr_reversed'] > 55]['pnl_reversed'].sum()
    print(f"\nPnL additionnel du REVERSE sélectif: ${pnl_from_reverse:,.0f}")
    print(f"PnL V8 SKIP actuel: ${all_results['skip']['pnl']:,.0f}")
    print(f"PnL HYBRIDE estimé: ${all_results['skip']['pnl'] + pnl_from_reverse:,.0f}")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
