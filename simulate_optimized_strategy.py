#!/usr/bin/env python3
"""
SIMULATION STRATEGIE OPTIMISEE
==============================
Compare la stratégie actuelle vs stratégie avec seuils stricts + filtres
"""

import pandas as pd
import numpy as np
from datetime import datetime
import ccxt

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

# ========================================
# STRATEGIE ACTUELLE
# ========================================
CURRENT = {
    'name': 'ACTUELLE',
    'rsi_period': 7,
    'rsi_oversold': 38,
    'rsi_overbought': 58,
    'stoch_period': 5,
    'stoch_oversold': 30,
    'stoch_overbought': 80,
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0,
    'require_strong_signal': False,
}

# ========================================
# STRATEGIES OPTIMISEES A TESTER
# ========================================

# Option 1: RSI plus strict seulement
OPTIMIZED_RSI = {
    'name': 'RSI STRICT (30/70)',
    'rsi_period': 7,
    'rsi_oversold': 30,  # Plus strict (était 38)
    'rsi_overbought': 70,  # Plus strict (était 58)
    'stoch_period': 5,
    'stoch_oversold': 30,
    'stoch_overbought': 80,
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0,
    'require_strong_signal': False,
}

# Option 2: Stoch plus strict seulement
OPTIMIZED_STOCH = {
    'name': 'STOCH STRICT (15/90)',
    'rsi_period': 7,
    'rsi_oversold': 38,
    'rsi_overbought': 58,
    'stoch_period': 5,
    'stoch_oversold': 15,  # Plus strict (était 30)
    'stoch_overbought': 90,  # Plus strict (était 80)
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0,
    'require_strong_signal': False,
}

# Option 3: RSI + Stoch stricts
OPTIMIZED_BOTH = {
    'name': 'RSI+STOCH STRICTS',
    'rsi_period': 7,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'stoch_period': 5,
    'stoch_oversold': 15,
    'stoch_overbought': 90,
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0,
    'require_strong_signal': False,
}

# Option 4: Stricts + Filtre volume
OPTIMIZED_VOLUME = {
    'name': 'STRICTS + VOLUME',
    'rsi_period': 7,
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'stoch_period': 5,
    'stoch_oversold': 15,
    'stoch_overbought': 90,
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0.5,  # Éviter volume trop bas
    'require_strong_signal': False,
}

# Option 5: Signal fort requis (RSI<25 & Stoch<10 ou RSI>75 & Stoch>95)
OPTIMIZED_STRONG = {
    'name': 'SIGNAUX FORTS',
    'rsi_period': 7,
    'rsi_oversold': 25,  # Très strict
    'rsi_overbought': 75,  # Très strict
    'stoch_period': 5,
    'stoch_oversold': 10,  # Très strict
    'stoch_overbought': 95,  # Très strict
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0.5,
    'require_strong_signal': True,
}

# Option 6: Équilibré (compromis trades/WR)
OPTIMIZED_BALANCED = {
    'name': 'EQUILIBRE (32/68 + 20/85)',
    'rsi_period': 7,
    'rsi_oversold': 32,
    'rsi_overbought': 68,
    'stoch_period': 5,
    'stoch_oversold': 20,
    'stoch_overbought': 85,
    'blocked_combos': [
        (4, 14), (6, 8), (0, 0), (0, 15), (0, 18), (1, 5), (1, 7), (5, 3)
    ],
    'min_volume_ratio': 0.5,
    'require_strong_signal': False,
}

ALL_STRATEGIES = [CURRENT, OPTIMIZED_RSI, OPTIMIZED_STOCH, OPTIMIZED_BOTH,
                  OPTIMIZED_VOLUME, OPTIMIZED_STRONG, OPTIMIZED_BALANCED]


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


def calculate_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Calculate indicators"""
    df = df.copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(config['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(config['rsi_period']).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic
    low_min = df['low'].rolling(config['stoch_period']).min()
    high_max = df['high'].rolling(config['stoch_period']).max()
    df['stoch'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Volume ratio
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']

    # Time info
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.dayofweek

    return df


def backtest_strategy(df: pd.DataFrame, config: dict) -> dict:
    """Run backtest with given config"""
    df = calculate_indicators(df, config)

    trades = []

    for i in range(len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # Skip if not enough data
        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue

        # Check blocked combos
        if (row['day'], row['hour']) in config['blocked_combos']:
            continue

        # Check volume filter
        if config['min_volume_ratio'] > 0 and row['vol_ratio'] < config['min_volume_ratio']:
            continue

        signal = None

        # UP signal
        if row['rsi'] < config['rsi_oversold'] and row['stoch'] < config['stoch_oversold']:
            signal = 'UP'

        # DOWN signal
        elif row['rsi'] > config['rsi_overbought'] and row['stoch'] > config['stoch_overbought']:
            signal = 'DOWN'

        if signal:
            # Determine result
            next_direction = 'UP' if next_row['close'] > row['close'] else 'DOWN'
            win = signal == next_direction

            trades.append({
                'timestamp': row['timestamp'],
                'signal': signal,
                'win': win,
                'rsi': row['rsi'],
                'stoch': row['stoch'],
            })

    if not trades:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'pnl': 0}

    trades_df = pd.DataFrame(trades)
    total = len(trades_df)
    wins = trades_df['win'].sum()
    win_rate = wins / total * 100

    # PnL calculation @ $120/trade, 52.5¢ entry
    # WIN: +$108.57 (0.905 * 120), LOSS: -$120
    pnl = (wins * 108.57) - ((total - wins) * 120)

    return {
        'trades': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': win_rate,
        'pnl': pnl,
    }


def run_simulation():
    """Run full simulation"""
    print("=" * 80)
    print("SIMULATION STRATEGIES OPTIMISEES - 2024 & 2025")
    print("=" * 80)
    print("Mise: $120/trade @ 52.5¢ | WIN: +$108.57 | LOSS: -$120")
    print("=" * 80)

    # Fetch all data first
    print("\nChargement des données...")
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  {symbol}...", end=" ", flush=True)
        df_2024 = fetch_data(symbol, '2024-01-01', '2025-01-01')
        df_2025 = fetch_data(symbol, '2025-01-01', '2025-12-29')
        all_data[symbol] = {'2024': df_2024, '2025': df_2025}
        print(f"OK ({len(df_2024)} + {len(df_2025)} candles)")

    # Results storage
    results = {s['name']: {'2024': {'trades': 0, 'wins': 0, 'pnl': 0},
                           '2025': {'trades': 0, 'wins': 0, 'pnl': 0}}
               for s in ALL_STRATEGIES}

    # Run backtest for each strategy
    print("\n" + "=" * 80)
    print("BACKTESTING...")
    print("=" * 80)

    for strategy in ALL_STRATEGIES:
        print(f"\n📊 {strategy['name']}")
        print(f"   RSI: {strategy['rsi_oversold']}/{strategy['rsi_overbought']} | Stoch: {strategy['stoch_oversold']}/{strategy['stoch_overbought']}")
        if strategy['min_volume_ratio'] > 0:
            print(f"   Volume filter: >{strategy['min_volume_ratio']}x")

        for year in ['2024', '2025']:
            year_trades = 0
            year_wins = 0
            year_pnl = 0

            for symbol in SYMBOLS:
                df = all_data[symbol][year]
                result = backtest_strategy(df, strategy)
                year_trades += result['trades']
                year_wins += result['wins']
                year_pnl += result['pnl']

            results[strategy['name']][year] = {
                'trades': year_trades,
                'wins': year_wins,
                'losses': year_trades - year_wins,
                'win_rate': year_wins / year_trades * 100 if year_trades > 0 else 0,
                'pnl': year_pnl,
            }

    # Display results
    print("\n" + "=" * 80)
    print("RESULTATS COMPARATIFS")
    print("=" * 80)

    print("\n📊 2024:")
    print("-" * 80)
    print(f"{'Stratégie':<25} {'Trades':>10} {'Win Rate':>10} {'PnL/mois':>15} {'vs Actuelle':>15}")
    print("-" * 80)

    base_pnl_2024 = results['ACTUELLE']['2024']['pnl'] / 12

    for strategy in ALL_STRATEGIES:
        r = results[strategy['name']]['2024']
        monthly_pnl = r['pnl'] / 12
        diff = monthly_pnl - base_pnl_2024
        diff_str = f"+${diff:,.0f}" if diff >= 0 else f"-${abs(diff):,.0f}"
        diff_str = "---" if strategy['name'] == 'ACTUELLE' else diff_str

        print(f"{strategy['name']:<25} {r['trades']:>10,} {r['win_rate']:>9.1f}% ${monthly_pnl:>13,.0f} {diff_str:>15}")

    print("\n📊 2025:")
    print("-" * 80)
    print(f"{'Stratégie':<25} {'Trades':>10} {'Win Rate':>10} {'PnL/mois':>15} {'vs Actuelle':>15}")
    print("-" * 80)

    base_pnl_2025 = results['ACTUELLE']['2025']['pnl'] / 12

    for strategy in ALL_STRATEGIES:
        r = results[strategy['name']]['2025']
        monthly_pnl = r['pnl'] / 12
        diff = monthly_pnl - base_pnl_2025
        diff_str = f"+${diff:,.0f}" if diff >= 0 else f"-${abs(diff):,.0f}"
        diff_str = "---" if strategy['name'] == 'ACTUELLE' else diff_str

        print(f"{strategy['name']:<25} {r['trades']:>10,} {r['win_rate']:>9.1f}% ${monthly_pnl:>13,.0f} {diff_str:>15}")

    # Summary
    print("\n" + "=" * 80)
    print("RESUME - MOYENNE 2024-2025")
    print("=" * 80)
    print(f"{'Stratégie':<25} {'Trades/jour':>12} {'Win Rate':>10} {'PnL/mois':>15} {'vs Actuelle':>15}")
    print("-" * 80)

    base_avg_pnl = (results['ACTUELLE']['2024']['pnl'] + results['ACTUELLE']['2025']['pnl']) / 24

    summary_data = []
    for strategy in ALL_STRATEGIES:
        r24 = results[strategy['name']]['2024']
        r25 = results[strategy['name']]['2025']

        total_trades = r24['trades'] + r25['trades']
        total_wins = r24['wins'] + r25['wins']
        total_pnl = r24['pnl'] + r25['pnl']

        avg_trades_day = total_trades / (365 * 2)
        avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        avg_monthly_pnl = total_pnl / 24

        diff = avg_monthly_pnl - base_avg_pnl
        diff_str = f"+${diff:,.0f}" if diff >= 0 else f"-${abs(diff):,.0f}"
        diff_str = "---" if strategy['name'] == 'ACTUELLE' else diff_str

        summary_data.append({
            'name': strategy['name'],
            'trades_day': avg_trades_day,
            'win_rate': avg_wr,
            'monthly_pnl': avg_monthly_pnl,
            'diff': diff,
        })

        print(f"{strategy['name']:<25} {avg_trades_day:>11.1f} {avg_wr:>9.1f}% ${avg_monthly_pnl:>13,.0f} {diff_str:>15}")

    # Best strategy
    print("\n" + "=" * 80)
    print("ANALYSE")
    print("=" * 80)

    best = max(summary_data, key=lambda x: x['monthly_pnl'])
    current = next(x for x in summary_data if x['name'] == 'ACTUELLE')

    print(f"""
📈 MEILLEURE STRATEGIE: {best['name']}
   - Win Rate: {best['win_rate']:.1f}% (vs {current['win_rate']:.1f}% actuel)
   - Trades/jour: {best['trades_day']:.1f} (vs {current['trades_day']:.1f} actuel)
   - PnL/mois: ${best['monthly_pnl']:,.0f} (vs ${current['monthly_pnl']:,.0f} actuel)
   - Gain: +${best['diff']:,.0f}/mois ({best['diff']/current['monthly_pnl']*100:.1f}% amélioration)
""")

    # Trade-off analysis
    print("📊 ANALYSE DES COMPROMIS:")
    print("-" * 60)
    for s in summary_data:
        trades_reduction = (1 - s['trades_day'] / current['trades_day']) * 100
        wr_gain = s['win_rate'] - current['win_rate']
        pnl_change = s['diff']

        if s['name'] != 'ACTUELLE':
            print(f"\n{s['name']}:")
            print(f"  Trades: {trades_reduction:+.1f}% | WR: {wr_gain:+.1f}% | PnL: ${pnl_change:+,.0f}/mois")

            if pnl_change > 0:
                print(f"  ✅ RECOMMANDÉ - Améliore le PnL de ${pnl_change:,.0f}/mois")
            elif wr_gain > 1 and trades_reduction < 50:
                print(f"  ⚠️ À CONSIDÉRER - Meilleur WR mais moins de trades")
            else:
                print(f"  ❌ NON RECOMMANDÉ - Réduit le PnL")

    return results


if __name__ == "__main__":
    results = run_simulation()
