#!/usr/bin/env python3
"""
Backtest séparé 2024 et 2025 avec simulation $100/trade
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt

PAIRS = ['BTC', 'ETH', 'XRP', 'SOL']
ENTRY_PRICE = 0.52
BET = 100
SHARES = BET / ENTRY_PRICE  # 192.31 shares
WIN_PROFIT = SHARES - BET  # $92.31
LOSS = -BET

def fetch_data(symbol, days=730):
    """Récupère les données historiques"""
    exchange = ccxt.binance()
    timeframe = '15m'
    since = exchange.parse8601((datetime.now(timezone.utc) - timedelta(days=days)).isoformat())

    all_candles = []
    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1
        if len(candles) < 1000:
            break

    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    """Calcule les indicateurs"""
    # RSI (period 7)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic (period 5)
    low_min = df['low'].rolling(window=5).min()
    high_max = df['high'].rolling(window=5).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Consecutive candles
    df['candle_dir'] = np.where(df['close'] > df['open'], 1, -1)

    consec_up = []
    consec_down = []
    up = 0
    down = 0
    for direction in df['candle_dir']:
        if direction == 1:
            up += 1
            down = 0
        else:
            down += 1
            up = 0
        consec_up.append(up)
        consec_down.append(down)

    df['consec_up'] = consec_up
    df['consec_down'] = consec_down
    df['year'] = df['timestamp'].dt.year

    return df

def backtest_pair(df, pair_name, year=None):
    """Backtest une paire pour une année spécifique"""
    if year:
        df = df[df['year'] == year].copy()

    if len(df) < 50:
        return None

    results = []

    # Config: RSI 35/65, Stoch 30/70, consec 1
    rsi_oversold = 35
    rsi_overbought = 65
    stoch_oversold = 30
    stoch_overbought = 70

    for i in range(30, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        signal = None

        # Signal UP
        if (row['rsi'] < rsi_oversold and
            row['stoch_k'] < stoch_oversold and
            row['consec_down'] >= 1):
            signal = 'UP'

        # Signal DOWN
        elif (row['rsi'] > rsi_overbought and
              row['stoch_k'] > stoch_overbought and
              row['consec_up'] >= 1):
            signal = 'DOWN'

        if signal:
            win = (next_row['close'] > row['close']) if signal == 'UP' else (next_row['close'] < row['close'])
            pnl = WIN_PROFIT if win else LOSS
            results.append({
                'timestamp': row['timestamp'],
                'signal': signal,
                'win': win,
                'pnl': pnl
            })

    if not results:
        return None

    df_results = pd.DataFrame(results)
    wins = df_results['win'].sum()
    total = len(df_results)
    wr = wins / total if total > 0 else 0

    days = (df_results['timestamp'].max() - df_results['timestamp'].min()).days
    days = max(days, 1)
    trades_per_day = total / days

    total_pnl = df_results['pnl'].sum()
    monthly_pnl = total_pnl / (days / 30) if days > 0 else 0

    return {
        'pair': pair_name,
        'year': year or 'ALL',
        'total_trades': total,
        'wins': wins,
        'losses': total - wins,
        'wr': wr,
        'days': days,
        'trades_per_day': trades_per_day,
        'total_pnl': total_pnl,
        'monthly_pnl': monthly_pnl
    }

def main():
    print("=" * 80)
    print("BACKTEST 2024 vs 2025 - SIMULATION $100/TRADE")
    print("=" * 80)
    print(f"\nConditions:")
    print(f"  - Entry Price: {ENTRY_PRICE*100:.0f}¢")
    print(f"  - BET: ${BET}")
    print(f"  - Shares par trade: {SHARES:.0f}")
    print(f"  - WIN Profit: ${WIN_PROFIT:.2f}")
    print(f"  - LOSS: -${BET}")
    print(f"  - RSI: 35/65, Stoch: 30/70, Consec: 1")

    # Charger les données
    print("\n📊 Chargement des données...")
    all_data = {}
    for pair in PAIRS:
        symbol = f"{pair}/USDT"
        print(f"  {pair}...", end=" ", flush=True)
        df = fetch_data(symbol)
        df = calculate_indicators(df)
        all_data[pair] = df
        print(f"✓ ({len(df):,} candles)")

    # Backtest par année
    years = [2024, 2025]

    for year in years:
        print("\n" + "=" * 80)
        print(f"RÉSULTATS {year}")
        print("=" * 80)

        year_results = []
        total_trades = 0
        total_wins = 0
        total_pnl = 0
        total_days = 0

        for pair in PAIRS:
            result = backtest_pair(all_data[pair], pair, year)
            if result:
                year_results.append(result)
                total_trades += result['total_trades']
                total_wins += result['wins']
                total_pnl += result['total_pnl']
                total_days = max(total_days, result['days'])

                print(f"\n  {pair}:")
                print(f"    Trades: {result['total_trades']:,} ({result['trades_per_day']:.1f}/jour)")
                print(f"    Win Rate: {result['wr']:.1%} ({result['wins']}/{result['total_trades']})")
                print(f"    PnL Total: ${result['total_pnl']:,.0f}")
                print(f"    PnL Mensuel: ${result['monthly_pnl']:,.0f}")

        # Résumé année
        if total_trades > 0:
            overall_wr = total_wins / total_trades
            monthly_pnl = total_pnl / (total_days / 30) if total_days > 0 else 0
            trades_per_day = total_trades / total_days if total_days > 0 else 0

            print(f"\n  {'='*60}")
            print(f"  TOTAL {year} (4 paires combinées):")
            print(f"  {'='*60}")
            print(f"    Trades totaux: {total_trades:,}")
            print(f"    Trades/jour: {trades_per_day:.1f}")
            print(f"    Win Rate global: {overall_wr:.1%}")
            print(f"    PnL Total {year}: ${total_pnl:,.0f}")
            print(f"    PnL Mensuel estimé: ${monthly_pnl:,.0f}")

    # Comparaison 2024 vs 2025
    print("\n" + "=" * 80)
    print("COMPARAISON 2024 vs 2025")
    print("=" * 80)

    comparison = []
    for year in years:
        total_trades = 0
        total_wins = 0
        total_pnl = 0
        total_days = 0

        for pair in PAIRS:
            result = backtest_pair(all_data[pair], pair, year)
            if result:
                total_trades += result['total_trades']
                total_wins += result['wins']
                total_pnl += result['total_pnl']
                total_days = max(total_days, result['days'])

        if total_trades > 0:
            comparison.append({
                'year': year,
                'trades': total_trades,
                'wr': total_wins / total_trades,
                'pnl': total_pnl,
                'monthly': total_pnl / (total_days / 30) if total_days > 0 else 0,
                'days': total_days
            })

    print(f"\n{'Année':<10} {'Trades':<12} {'WR':<10} {'PnL Total':<15} {'PnL/Mois':<12}")
    print("-" * 60)
    for c in comparison:
        print(f"{c['year']:<10} {c['trades']:<12,} {c['wr']:<10.1%} ${c['pnl']:<14,.0f} ${c['monthly']:<11,.0f}")

    # Projection pour déploiement
    print("\n" + "=" * 80)
    print("PROJECTION POUR DÉPLOIEMENT VPS")
    print("=" * 80)

    # Utiliser les données 2025 comme référence (plus récent)
    if comparison:
        latest = comparison[-1]  # 2025
        print(f"\nBasé sur les données {latest['year']} ({latest['days']} jours):")
        print(f"  - Win Rate attendu: {latest['wr']:.1%}")
        print(f"  - Trades/jour attendus: {latest['trades']/latest['days']:.1f}")
        print(f"  - PnL mensuel projeté: ${latest['monthly']:,.0f}")

        print(f"\n📋 Configuration pour les 4 bots:")
        print(f"  - BET: $100 (soit {SHARES:.0f} shares à 52¢)")
        print(f"  - RSI: oversold=35, overbought=65")
        print(f"  - Stoch: oversold=30, overbought=70")
        print(f"  - Consec threshold: 1")
        print(f"  - Max price: 52¢")

if __name__ == "__main__":
    main()
