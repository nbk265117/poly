#!/usr/bin/env python3
"""
Backtest 2024-2025 pour 3 pairs (BTC, ETH, XRP) avec 52.5¢
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt

PAIRS = ['BTC', 'ETH', 'XRP']
ENTRY_PRICE = 0.525
BET = 100
SHARES = BET / ENTRY_PRICE  # 190.48 shares
WIN_PROFIT = SHARES - BET    # $90.48
LOSS = -BET

def fetch_data(symbol, days=730):
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

    df['year'] = df['timestamp'].dt.year
    return df

def backtest_pair(df, pair_name, year=None):
    if year:
        df = df[df['year'] == year].copy()

    if len(df) < 50:
        return None

    results = []

    # Config: RSI 35/65, Stoch 30/70
    for i in range(30, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        signal = None

        # Signal UP
        if row['rsi'] < 35 and row['stoch_k'] < 30:
            signal = 'UP'
        # Signal DOWN
        elif row['rsi'] > 65 and row['stoch_k'] > 70:
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
    print("=" * 70)
    print("BACKTEST 3 PAIRS (BTC, ETH, XRP) - $100/TRADE @ 52.5¢")
    print("=" * 70)
    print(f"\nEntry Price: {ENTRY_PRICE*100:.1f}¢")
    print(f"BET: ${BET}")
    print(f"Shares: {SHARES:.2f}")
    print(f"WIN: +${WIN_PROFIT:.2f} | LOSS: -${BET}")
    print(f"Config: RSI 35/65, Stoch 30/70, No blocked hours")

    # Charger les données
    print("\n" + "=" * 70)
    print("Chargement des donnees...")
    print("=" * 70)
    all_data = {}
    for pair in PAIRS:
        symbol = f"{pair}/USDT"
        print(f"  {pair}...", end=" ", flush=True)
        df = fetch_data(symbol)
        df = calculate_indicators(df)
        all_data[pair] = df
        print(f"OK ({len(df):,} candles)")

    # Backtest par année
    for year in [2024, 2025]:
        print("\n" + "=" * 70)
        print(f"RESULTATS {year}")
        print("=" * 70)

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

        if total_trades > 0:
            overall_wr = total_wins / total_trades
            monthly_pnl = total_pnl / (total_days / 30) if total_days > 0 else 0
            trades_per_day = total_trades / total_days if total_days > 0 else 0

            print(f"\n  {'='*50}")
            print(f"  TOTAL {year} (3 paires):")
            print(f"  {'='*50}")
            print(f"    Trades: {total_trades:,} ({trades_per_day:.1f}/jour)")
            print(f"    Win Rate: {overall_wr:.1%}")
            print(f"    PnL Total: ${total_pnl:,.0f}")
            print(f"    PnL Mensuel: ${monthly_pnl:,.0f}")

    # Résumé final
    print("\n" + "=" * 70)
    print("RESUME FINAL - 3 PAIRS @ 52.5¢")
    print("=" * 70)

    print(f"\n{'Annee':<10} {'Trades':<12} {'Trades/j':<12} {'WR':<10} {'PnL Total':<15} {'PnL/mois':<12}")
    print("-" * 70)

    for year in [2024, 2025]:
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
            overall_wr = total_wins / total_trades
            monthly_pnl = total_pnl / (total_days / 30) if total_days > 0 else 0
            trades_per_day = total_trades / total_days

            print(f"{year:<10} {total_trades:<12,} {trades_per_day:<12.1f} {overall_wr:<10.1%} ${total_pnl:<14,.0f} ${monthly_pnl:<11,.0f}")

if __name__ == "__main__":
    main()
