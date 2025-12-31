#!/usr/bin/env python3
"""
Simulation V7 Strategy - BTC + ETH + XRP
$100/trade, Entry 52.5c
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fetch_ohlcv(symbol, timeframe='15m', days=730):
    """Fetch historical data from Binance"""
    exchange = ccxt.binance()
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())

    all_data = []
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        all_data.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        if len(ohlcv) < 1000:
            break

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_rsi(prices, period=7):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_stochastic(df, period=5):
    """Calculate Stochastic %K"""
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)

def simulate_v7(df, bet_size=100, entry_price=0.525):
    """
    Simulate V7 strategy
    UP: RSI(7) < 38 AND Stoch(5) < 30
    DOWN: RSI(7) > 68 AND Stoch(5) > 75
    """
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], 7)
    df['stoch'] = calculate_stochastic(df, 5)
    df['next_close'] = df['close'].shift(-1)

    trades = []

    for i in range(len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue

        signal = None

        # V7 signals
        if row['rsi'] < 38 and row['stoch'] < 30:
            signal = 'UP'
        elif row['rsi'] > 68 and row['stoch'] > 75:
            signal = 'DOWN'

        if signal:
            # Determine outcome
            price_went_up = next_row['close'] > row['close']

            if signal == 'UP':
                win = price_went_up
            else:
                win = not price_went_up

            # Calculate PnL
            shares = bet_size / entry_price
            if win:
                pnl = shares * (1 - entry_price)  # Win: get $1 per share
            else:
                pnl = -bet_size  # Lose: lose entire bet

            trades.append({
                'timestamp': row['timestamp'],
                'signal': signal,
                'win': win,
                'pnl': pnl
            })

    return pd.DataFrame(trades)

def main():
    print("=" * 70)
    print("SIMULATION V7 - BTC + ETH + XRP")
    print("$100/trade | Entry: 52.5c | RSI(7) 38/68 | Stoch(5) 30/75")
    print("=" * 70)

    pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    all_trades = []

    for pair in pairs:
        print(f"\nFetching {pair}...")
        df = fetch_ohlcv(pair, '15m', 730)
        print(f"  {len(df)} candles loaded")

        trades = simulate_v7(df)
        trades['pair'] = pair.split('/')[0]
        all_trades.append(trades)

        wins = trades['win'].sum()
        total = len(trades)
        wr = wins / total * 100 if total > 0 else 0
        print(f"  {total} trades | WR: {wr:.1f}% | PnL: ${trades['pnl'].sum():,.0f}")

    # Combine all trades
    all_df = pd.concat(all_trades, ignore_index=True)
    all_df['month'] = all_df['timestamp'].dt.to_period('M')

    # Monthly breakdown
    print("\n" + "=" * 70)
    print("DETAIL MENSUEL 2024-2025 (BTC + ETH + XRP)")
    print("=" * 70)

    monthly = all_df.groupby('month').agg({
        'pnl': 'sum',
        'win': ['sum', 'count']
    })
    monthly.columns = ['pnl', 'wins', 'total']
    monthly['wr'] = monthly['wins'] / monthly['total'] * 100

    print(f"\n{'Mois':<12} {'Trades':>8} {'Win Rate':>10} {'PnL':>15}")
    print("-" * 50)

    year_2024 = {'trades': 0, 'wins': 0, 'pnl': 0}
    year_2025 = {'trades': 0, 'wins': 0, 'pnl': 0}

    for period, row in monthly.iterrows():
        year = period.year
        month_name = period.strftime('%b %Y')

        print(f"{month_name:<12} {int(row['total']):>8} {row['wr']:>9.1f}% ${row['pnl']:>13,.0f}")

        if year == 2024:
            year_2024['trades'] += row['total']
            year_2024['wins'] += row['wins']
            year_2024['pnl'] += row['pnl']
        elif year == 2025:
            year_2025['trades'] += row['total']
            year_2025['wins'] += row['wins']
            year_2025['pnl'] += row['pnl']

    # Yearly summary
    print("\n" + "=" * 70)
    print("RESUME ANNUEL")
    print("=" * 70)

    if year_2024['trades'] > 0:
        wr_2024 = year_2024['wins'] / year_2024['trades'] * 100
        trades_day_2024 = year_2024['trades'] / 366
        print(f"\n2024:")
        print(f"  Trades: {int(year_2024['trades']):,}")
        print(f"  Trades/jour: {trades_day_2024:.0f}")
        print(f"  Win Rate: {wr_2024:.1f}%")
        print(f"  PnL Total: ${year_2024['pnl']:,.0f}")
        print(f"  PnL Moyen/Mois: ${year_2024['pnl']/12:,.0f}")

    if year_2025['trades'] > 0:
        # Count months in 2025 data
        months_2025 = len([p for p in monthly.index if p.year == 2025])
        wr_2025 = year_2025['wins'] / year_2025['trades'] * 100
        trades_day_2025 = year_2025['trades'] / (months_2025 * 30)
        print(f"\n2025 (jusqu'a maintenant):")
        print(f"  Trades: {int(year_2025['trades']):,}")
        print(f"  Trades/jour: {trades_day_2025:.0f}")
        print(f"  Win Rate: {wr_2025:.1f}%")
        print(f"  PnL Total: ${year_2025['pnl']:,.0f}")
        print(f"  PnL Moyen/Mois: ${year_2025['pnl']/months_2025:,.0f}")

    # Grand total
    total_trades = year_2024['trades'] + year_2025['trades']
    total_wins = year_2024['wins'] + year_2025['wins']
    total_pnl = year_2024['pnl'] + year_2025['pnl']
    total_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    total_months = len(monthly)

    print("\n" + "=" * 70)
    print("TOTAL (BTC + ETH + XRP)")
    print("=" * 70)
    print(f"  Trades: {int(total_trades):,}")
    print(f"  Trades/jour: {total_trades / 730:.0f}")
    print(f"  Win Rate: {total_wr:.1f}%")
    print(f"  PnL Total: ${total_pnl:,.0f}")
    print(f"  PnL Moyen/Mois: ${total_pnl/total_months:,.0f}")

    # Per pair breakdown
    print("\n" + "=" * 70)
    print("PERFORMANCE PAR PAIR")
    print("=" * 70)

    pair_stats = []
    for pair in ['BTC', 'ETH', 'XRP']:
        pair_df = all_df[all_df['pair'] == pair]
        wins = pair_df['win'].sum()
        total = len(pair_df)
        wr = wins / total * 100 if total > 0 else 0
        pnl = pair_df['pnl'].sum()
        pair_stats.append({'pair': pair, 'trades': total, 'wr': wr, 'pnl': pnl})
        print(f"\n{pair}:")
        print(f"  Trades: {total:,}")
        print(f"  Win Rate: {wr:.1f}%")
        print(f"  PnL Total: ${pnl:,.0f}")
        print(f"  PnL/Mois: ${pnl/total_months:,.0f}")

    # Ranking
    print("\n" + "=" * 70)
    print("CLASSEMENT PAR PERFORMANCE")
    print("=" * 70)
    pair_stats_sorted = sorted(pair_stats, key=lambda x: x['pnl'], reverse=True)
    for i, p in enumerate(pair_stats_sorted):
        medal = ['🥇', '🥈', '🥉'][i]
        print(f"{medal} {p['pair']}: WR {p['wr']:.1f}% | PnL ${p['pnl']:,.0f}")

if __name__ == "__main__":
    main()
