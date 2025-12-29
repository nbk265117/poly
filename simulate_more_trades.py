#!/usr/bin/env python3
"""
SIMULATION: PLUS DE TRADES + PLUS DE FILTRES
=============================================
Hypothèse: Élargir seuils pour plus de trades + bloquer plus de combos toxiques
"""

import pandas as pd
import numpy as np
from datetime import datetime
import ccxt

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

# Combos toxiques identifiés (>50% loss rate)
BLOCKED_COMBOS_7 = [
    (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7)
]

# Combos avec >48% loss rate (26 combos)
BLOCKED_COMBOS_26 = [
    (4, 14), (6, 8), (0, 15), (0, 18), (1, 5), (0, 0), (1, 7), (5, 3),
    (4, 5), (0, 7), (2, 15), (4, 19), (0, 4), (1, 14), (2, 4), (4, 7),
    (6, 0), (0, 5), (2, 8), (4, 4), (1, 0), (3, 5), (4, 0), (1, 4),
    (3, 7), (4, 8)
]

# ========================================
# STRATEGIES A TESTER
# ========================================

STRATEGIES = [
    # Baseline actuel
    {
        'name': 'ACTUELLE (38/58 + 30/80)',
        'rsi_oversold': 38, 'rsi_overbought': 58,
        'stoch_oversold': 30, 'stoch_overbought': 80,
        'blocked_combos': BLOCKED_COMBOS_7 + [(5, 3)],
    },

    # Test 1: Plus de combos bloqués (26 au lieu de 8)
    {
        'name': 'ACTUELLE + 26 COMBOS BLOQUES',
        'rsi_oversold': 38, 'rsi_overbought': 58,
        'stoch_oversold': 30, 'stoch_overbought': 80,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 2: Seuils élargis RSI
    {
        'name': 'RSI ELARGI (42/54)',
        'rsi_oversold': 42, 'rsi_overbought': 54,
        'stoch_oversold': 30, 'stoch_overbought': 80,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 3: Seuils élargis Stoch
    {
        'name': 'STOCH ELARGI (35/75)',
        'rsi_oversold': 38, 'rsi_overbought': 58,
        'stoch_oversold': 35, 'stoch_overbought': 75,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 4: Les deux élargis
    {
        'name': 'RSI+STOCH ELARGIS',
        'rsi_oversold': 42, 'rsi_overbought': 54,
        'stoch_oversold': 35, 'stoch_overbought': 75,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 5: Très élargi + tous les combos
    {
        'name': 'TRES ELARGI (45/52 + 40/70)',
        'rsi_oversold': 45, 'rsi_overbought': 52,
        'stoch_oversold': 40, 'stoch_overbought': 70,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 6: Asymétrique optimisé (plus de UP que DOWN)
    {
        'name': 'ASYMETRIQUE UP',
        'rsi_oversold': 42, 'rsi_overbought': 58,  # Plus de signaux UP
        'stoch_oversold': 35, 'stoch_overbought': 80,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 7: Asymétrique optimisé (plus de DOWN que UP)
    {
        'name': 'ASYMETRIQUE DOWN',
        'rsi_oversold': 38, 'rsi_overbought': 54,  # Plus de signaux DOWN
        'stoch_oversold': 30, 'stoch_overbought': 75,
        'blocked_combos': BLOCKED_COMBOS_26,
    },

    # Test 8: Optimal théorique (basé sur analyse)
    {
        'name': 'OPTIMAL THEORIQUE',
        'rsi_oversold': 40, 'rsi_overbought': 56,
        'stoch_oversold': 32, 'stoch_overbought': 78,
        'blocked_combos': BLOCKED_COMBOS_26,
    },
]


def fetch_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical 15m data"""
    exchange = ccxt.binance()
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

    all_candles = []
    current_ts = start_ts

    while current_ts < end_ts:
        candles = exchange.fetch_ohlcv(symbol, '15m', current_ts, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        current_ts = candles[-1][0] + 1

    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[(df['timestamp'] >= start_date) & (df['timestamp'] < end_date)]
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate indicators"""
    df = df.copy()

    # RSI (period 7)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic (period 5)
    low_min = df['low'].rolling(5).min()
    high_max = df['high'].rolling(5).max()
    df['stoch'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Time info
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.dayofweek

    return df


def backtest_strategy(df: pd.DataFrame, config: dict) -> dict:
    """Run backtest"""
    trades = []
    blocked_count = 0

    for i in range(len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue

        signal = None

        # UP signal
        if row['rsi'] < config['rsi_oversold'] and row['stoch'] < config['stoch_oversold']:
            signal = 'UP'

        # DOWN signal
        elif row['rsi'] > config['rsi_overbought'] and row['stoch'] > config['stoch_overbought']:
            signal = 'DOWN'

        if signal:
            # Check blocked combos
            if (row['day'], row['hour']) in config['blocked_combos']:
                blocked_count += 1
                continue

            next_direction = 'UP' if next_row['close'] > row['close'] else 'DOWN'
            win = signal == next_direction

            trades.append({
                'timestamp': row['timestamp'],
                'signal': signal,
                'win': win,
            })

    if not trades:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'pnl': 0, 'blocked': blocked_count}

    trades_df = pd.DataFrame(trades)
    total = len(trades_df)
    wins = trades_df['win'].sum()
    win_rate = wins / total * 100

    # PnL @ $120/trade
    pnl = (wins * 108.57) - ((total - wins) * 120)

    return {
        'trades': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': win_rate,
        'pnl': pnl,
        'blocked': blocked_count,
    }


def run_simulation():
    """Run full simulation"""
    print("=" * 90)
    print("SIMULATION: PLUS DE TRADES + PLUS DE FILTRES")
    print("=" * 90)
    print("Objectif: Trouver l'équilibre optimal entre nombre de trades et win rate")
    print("Mise: $120/trade @ 52.5¢ | WIN: +$108.57 | LOSS: -$120")
    print("=" * 90)

    # Fetch data
    print("\nChargement des données...")
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  {symbol}...", end=" ", flush=True)
        df_2024 = fetch_data(symbol, '2024-01-01', '2025-01-01')
        df_2025 = fetch_data(symbol, '2025-01-01', '2025-12-29')

        df_2024 = calculate_indicators(df_2024)
        df_2025 = calculate_indicators(df_2025)

        all_data[symbol] = {'2024': df_2024, '2025': df_2025}
        print("OK")

    # Results
    results = []

    print("\n" + "=" * 90)
    print("BACKTESTING...")
    print("=" * 90)

    for strategy in STRATEGIES:
        print(f"\n📊 {strategy['name']}")

        total_2024 = {'trades': 0, 'wins': 0, 'pnl': 0, 'blocked': 0}
        total_2025 = {'trades': 0, 'wins': 0, 'pnl': 0, 'blocked': 0}

        for symbol in SYMBOLS:
            r24 = backtest_strategy(all_data[symbol]['2024'], strategy)
            r25 = backtest_strategy(all_data[symbol]['2025'], strategy)

            for k in ['trades', 'wins', 'pnl', 'blocked']:
                total_2024[k] += r24[k]
                total_2025[k] += r25[k]

        total_2024['win_rate'] = total_2024['wins'] / total_2024['trades'] * 100 if total_2024['trades'] > 0 else 0
        total_2025['win_rate'] = total_2025['wins'] / total_2025['trades'] * 100 if total_2025['trades'] > 0 else 0

        results.append({
            'name': strategy['name'],
            '2024': total_2024,
            '2025': total_2025,
        })

    # Display results
    print("\n" + "=" * 90)
    print("RESULTATS 2024")
    print("=" * 90)
    print(f"{'Stratégie':<30} {'Trades':>10} {'Bloqués':>10} {'WR':>8} {'PnL/mois':>15}")
    print("-" * 90)

    for r in results:
        d = r['2024']
        monthly = d['pnl'] / 12
        print(f"{r['name']:<30} {d['trades']:>10,} {d['blocked']:>10,} {d['win_rate']:>7.1f}% ${monthly:>13,.0f}")

    print("\n" + "=" * 90)
    print("RESULTATS 2025")
    print("=" * 90)
    print(f"{'Stratégie':<30} {'Trades':>10} {'Bloqués':>10} {'WR':>8} {'PnL/mois':>15}")
    print("-" * 90)

    for r in results:
        d = r['2025']
        monthly = d['pnl'] / 12
        print(f"{r['name']:<30} {d['trades']:>10,} {d['blocked']:>10,} {d['win_rate']:>7.1f}% ${monthly:>13,.0f}")

    # Summary
    print("\n" + "=" * 90)
    print("RESUME - MOYENNE 2024-2025")
    print("=" * 90)
    print(f"{'Stratégie':<30} {'Trades/j':>10} {'WR':>8} {'PnL/mois':>15} {'vs Base':>12}")
    print("-" * 90)

    base_pnl = None
    summary = []

    for r in results:
        total_trades = r['2024']['trades'] + r['2025']['trades']
        total_wins = r['2024']['wins'] + r['2025']['wins']
        total_pnl = r['2024']['pnl'] + r['2025']['pnl']

        trades_day = total_trades / (365 * 2)
        wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        monthly = total_pnl / 24

        if base_pnl is None:
            base_pnl = monthly

        diff = monthly - base_pnl
        diff_str = f"+${diff:,.0f}" if diff >= 0 else f"-${abs(diff):,.0f}"
        diff_str = "---" if r['name'].startswith('ACTUELLE (') else diff_str

        summary.append({
            'name': r['name'],
            'trades_day': trades_day,
            'wr': wr,
            'monthly': monthly,
            'diff': diff,
        })

        print(f"{r['name']:<30} {trades_day:>9.1f} {wr:>7.1f}% ${monthly:>13,.0f} {diff_str:>12}")

    # Find best
    best = max(summary, key=lambda x: x['monthly'])
    base = summary[0]

    print("\n" + "=" * 90)
    print("CONCLUSION")
    print("=" * 90)
    print(f"""
🏆 MEILLEURE STRATEGIE: {best['name']}

   Trades/jour: {best['trades_day']:.1f} (vs {base['trades_day']:.1f} base)
   Win Rate:    {best['wr']:.1f}% (vs {base['wr']:.1f}% base)
   PnL/mois:    ${best['monthly']:,.0f} (vs ${base['monthly']:,.0f} base)

   Différence:  ${best['diff']:+,.0f}/mois ({best['diff']/base['monthly']*100:+.1f}%)
""")

    # Recommendations
    print("📋 RECOMMANDATIONS:")
    print("-" * 60)

    better = [s for s in summary if s['diff'] > 0]
    if better:
        print("\n✅ Stratégies qui AMÉLIORENT le PnL:")
        for s in sorted(better, key=lambda x: -x['diff']):
            print(f"   • {s['name']}: +${s['diff']:,.0f}/mois ({s['wr']:.1f}% WR, {s['trades_day']:.0f} trades/j)")
    else:
        print("\n❌ Aucune stratégie testée n'améliore le PnL")
        print("   → La stratégie ACTUELLE est déjà optimale!")


if __name__ == "__main__":
    run_simulation()
