#!/usr/bin/env python3
"""
Backtest Mensuel Détaillé 2024-2025
3 paires (BTC, ETH, XRP) - $100/trade @ 52.5¢
Stratégie: RSI(7) + Stoch(5) avec filtres temporels
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt
import warnings
warnings.filterwarnings('ignore')

# Configuration
PAIRS = ['BTC', 'ETH', 'XRP']
ENTRY_PRICE = 0.525
BET = 100  # $100 par position
SHARES = BET / ENTRY_PRICE  # 190.48 shares
WIN_PROFIT = SHARES - BET    # +$90.48
LOSS = -BET                  # -$100

# Stratégie RSI + Stoch (config.yaml)
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 58
STOCH_OVERSOLD = 30
STOCH_OVERBOUGHT = 80

# Filtres temporels (44 combos bloqués)
BLOCKED_COMBOS = [
    (0, 0), (0, 1), (0, 2), (0, 3), (0, 6), (0, 7), (0, 14), (0, 15), (0, 18), (0, 20),  # Lundi
    (1, 1), (1, 4), (1, 5), (1, 7), (1, 14), (1, 16), (1, 18), (1, 19), (1, 22),  # Mardi
    (2, 0), (2, 3), (2, 8), (2, 17), (2, 19), (2, 23),  # Mercredi
    (3, 4), (3, 5), (3, 9), (3, 16), (3, 22),  # Jeudi
    (4, 2), (4, 5), (4, 6), (4, 7), (4, 10), (4, 14), (4, 15), (4, 17), (4, 18),  # Vendredi
    (5, 3),  # Samedi
    (6, 8), (6, 13), (6, 22), (6, 23),  # Dimanche
]

def fetch_data(symbol, days=730):
    """Télécharge les données historiques"""
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
    """Calcule RSI et Stochastic"""
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

    # Time info
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['hour'] = df['timestamp'].dt.hour

    return df

def is_blocked(day_of_week, hour):
    """Vérifie si le combo jour/heure est bloqué"""
    return (day_of_week, hour) in BLOCKED_COMBOS

def backtest_monthly(df, pair_name, use_filters=True):
    """Backtest avec résultats mensuels"""
    results = []

    for i in range(30, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # Vérifier filtres temporels
        if use_filters and is_blocked(row['day_of_week'], row['hour']):
            continue

        signal = None

        # Signal UP
        if row['rsi'] < RSI_OVERSOLD and row['stoch_k'] < STOCH_OVERSOLD:
            signal = 'UP'
        # Signal DOWN
        elif row['rsi'] > RSI_OVERBOUGHT and row['stoch_k'] > STOCH_OVERBOUGHT:
            signal = 'DOWN'

        if signal:
            win = (next_row['close'] > row['close']) if signal == 'UP' else (next_row['close'] < row['close'])
            pnl = WIN_PROFIT if win else LOSS

            results.append({
                'timestamp': row['timestamp'],
                'year': row['year'],
                'month': row['month'],
                'pair': pair_name,
                'signal': signal,
                'win': win,
                'pnl': pnl
            })

    return pd.DataFrame(results)

def main():
    print("=" * 80)
    print("  BACKTEST MENSUEL DETAILLE - 3 BOTS (BTC, ETH, XRP)")
    print("  Stratégie: RSI(7) + Stoch(5) + 44 Filtres Temporels")
    print("=" * 80)
    print(f"\n  Configuration:")
    print(f"  • Entry Price: {ENTRY_PRICE*100:.1f}¢")
    print(f"  • Bet: ${BET} par position")
    print(f"  • Shares: {SHARES:.2f}")
    print(f"  • WIN: +${WIN_PROFIT:.2f} | LOSS: -${BET}")
    print(f"  • RSI: <{RSI_OVERSOLD} (UP) / >{RSI_OVERBOUGHT} (DOWN)")
    print(f"  • Stoch: <{STOCH_OVERSOLD} (UP) / >{STOCH_OVERBOUGHT} (DOWN)")
    print(f"  • Filtres: 44 combos horaires bloqués")

    # Télécharger les données
    print("\n" + "-" * 80)
    print("  Téléchargement des données (2 ans)...")
    print("-" * 80)

    all_data = {}
    for pair in PAIRS:
        symbol = f"{pair}/USDT"
        print(f"  {pair}...", end=" ", flush=True)
        df = fetch_data(symbol)
        df = calculate_indicators(df)
        all_data[pair] = df
        print(f"OK ({len(df):,} bougies)")

    # Backtest
    print("\n" + "-" * 80)
    print("  Exécution du backtest...")
    print("-" * 80)

    all_results = []
    for pair in PAIRS:
        results = backtest_monthly(all_data[pair], pair, use_filters=True)
        all_results.append(results)
        print(f"  {pair}: {len(results):,} trades")

    df_all = pd.concat(all_results, ignore_index=True)

    # Résultats mensuels
    months_order = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            months_order.append((year, month))

    print("\n" + "=" * 80)
    print("  RESULTATS MENSUELS DETAILLES")
    print("=" * 80)

    monthly_data = []

    for year, month in months_order:
        month_df = df_all[(df_all['year'] == year) & (df_all['month'] == month)]

        if len(month_df) == 0:
            continue

        # Stats par paire
        pair_stats = {}
        for pair in PAIRS:
            pair_df = month_df[month_df['pair'] == pair]
            if len(pair_df) > 0:
                pair_stats[pair] = {
                    'trades': len(pair_df),
                    'wins': pair_df['win'].sum(),
                    'pnl': pair_df['pnl'].sum()
                }

        # Stats globales du mois
        total_trades = len(month_df)
        total_wins = month_df['win'].sum()
        total_pnl = month_df['pnl'].sum()
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

        month_name = datetime(year, month, 1).strftime('%B')

        monthly_data.append({
            'year': year,
            'month': month,
            'month_name': month_name,
            'trades': total_trades,
            'wins': total_wins,
            'losses': total_trades - total_wins,
            'win_rate': win_rate,
            'pnl': total_pnl,
            'pair_stats': pair_stats
        })

    # Affichage par année
    for year in [2024, 2025]:
        year_data = [m for m in monthly_data if m['year'] == year]

        if not year_data:
            continue

        print(f"\n{'='*80}")
        print(f"  ANNÉE {year}")
        print(f"{'='*80}")
        print(f"\n  {'Mois':<12} {'Trades':>8} {'Wins':>6} {'Loss':>6} {'WR':>8} {'PnL':>12}  {'BTC':>10} {'ETH':>10} {'XRP':>10}")
        print(f"  {'-'*12} {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*12}  {'-'*10} {'-'*10} {'-'*10}")

        year_total_trades = 0
        year_total_wins = 0
        year_total_pnl = 0

        for m in year_data:
            btc_pnl = m['pair_stats'].get('BTC', {}).get('pnl', 0)
            eth_pnl = m['pair_stats'].get('ETH', {}).get('pnl', 0)
            xrp_pnl = m['pair_stats'].get('XRP', {}).get('pnl', 0)

            print(f"  {m['month_name']:<12} {m['trades']:>8,} {m['wins']:>6,} {m['losses']:>6,} {m['win_rate']:>7.1f}% ${m['pnl']:>10,.0f}  ${btc_pnl:>9,.0f} ${eth_pnl:>9,.0f} ${xrp_pnl:>9,.0f}")

            year_total_trades += m['trades']
            year_total_wins += m['wins']
            year_total_pnl += m['pnl']

        year_wr = (year_total_wins / year_total_trades * 100) if year_total_trades > 0 else 0
        months_count = len(year_data)
        avg_monthly_pnl = year_total_pnl / months_count if months_count > 0 else 0

        print(f"  {'-'*12} {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*12}")
        print(f"  {'TOTAL':<12} {year_total_trades:>8,} {year_total_wins:>6,} {year_total_trades-year_total_wins:>6,} {year_wr:>7.1f}% ${year_total_pnl:>10,.0f}")
        print(f"  {'MOYENNE/MOIS':<12} {year_total_trades//months_count:>8,} {'':<6} {'':<6} {'':<8} ${avg_monthly_pnl:>10,.0f}")

    # Résumé final
    print("\n" + "=" * 80)
    print("  RESUME FINAL - 3 BOTS x $100/TRADE")
    print("=" * 80)

    total_trades = len(df_all)
    total_wins = df_all['win'].sum()
    total_pnl = df_all['pnl'].sum()
    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    # Calculer trades par jour
    if len(df_all) > 0:
        days = (df_all['timestamp'].max() - df_all['timestamp'].min()).days
        days = max(days, 1)
        trades_per_day = total_trades / days
    else:
        days = 0
        trades_per_day = 0

    months_count = len(monthly_data)
    avg_monthly_pnl = total_pnl / months_count if months_count > 0 else 0

    print(f"\n  Total Trades:      {total_trades:,}")
    print(f"  Trades/jour:       {trades_per_day:.1f}")
    print(f"  Win Rate:          {overall_wr:.1f}%")
    print(f"  PnL Total:         ${total_pnl:,.0f}")
    print(f"  PnL Mensuel Moyen: ${avg_monthly_pnl:,.0f}")

    # Meilleur et pire mois
    if monthly_data:
        best_month = max(monthly_data, key=lambda x: x['pnl'])
        worst_month = min(monthly_data, key=lambda x: x['pnl'])

        print(f"\n  Meilleur mois:     {best_month['month_name']} {best_month['year']} (${best_month['pnl']:,.0f})")
        print(f"  Pire mois:         {worst_month['month_name']} {worst_month['year']} (${worst_month['pnl']:,.0f})")

    # Stats par paire
    print(f"\n  {'Paire':<8} {'Trades':>10} {'WR':>8} {'PnL Total':>12} {'PnL/mois':>12}")
    print(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*12} {'-'*12}")

    for pair in PAIRS:
        pair_df = df_all[df_all['pair'] == pair]
        if len(pair_df) > 0:
            p_trades = len(pair_df)
            p_wins = pair_df['win'].sum()
            p_wr = (p_wins / p_trades * 100)
            p_pnl = pair_df['pnl'].sum()
            p_monthly = p_pnl / months_count if months_count > 0 else 0
            print(f"  {pair:<8} {p_trades:>10,} {p_wr:>7.1f}% ${p_pnl:>11,.0f} ${p_monthly:>11,.0f}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
