#!/usr/bin/env python3
"""
BACKTEST V8.1 HYBRIDE - Détail Mensuel 2024-2025
3 bots (BTC, ETH, XRP) - $100/trade @ 52.5¢
Stratégie: RSI(7) + Stoch(5) + 235 SKIP + 12 REVERSE
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

# Stratégie V8.1 HYBRIDE
RSI_PERIOD = 7
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 58
STOCH_PERIOD = 5
STOCH_OVERSOLD = 30
STOCH_OVERBOUGHT = 80

# 12 CANDLES A REVERSER (WR < 42% -> WR inverse > 58%)
REVERSE_CANDLES = {
    (6, 8, 30),   # Dim 08:30
    (6, 11, 15),  # Dim 11:15
    (4, 18, 15),  # Ven 18:15
    (4, 2, 0),    # Ven 02:00
    (2, 19, 30),  # Mer 19:30
    (6, 13, 15),  # Dim 13:15
    (6, 2, 30),   # Dim 02:30
    (4, 14, 30),  # Ven 14:30
    (2, 6, 30),   # Mer 06:30
    (3, 14, 30),  # Jeu 14:30
    (1, 14, 15),  # Mar 14:15
    (0, 2, 45),   # Lun 02:45
}

# 235 CANDLES BLOQUEES (SKIP)
BLOCKED_CANDLES = {
    # Lundi (44 candles)
    (0, 0, 0), (0, 0, 15), (0, 0, 30), (0, 1, 30), (0, 1, 45), (0, 2, 0), (0, 2, 45),
    (0, 3, 0), (0, 3, 15), (0, 3, 30), (0, 4, 30), (0, 5, 30), (0, 6, 15), (0, 6, 30),
    (0, 7, 0), (0, 7, 15), (0, 7, 30), (0, 8, 0), (0, 9, 0), (0, 11, 30),
    (0, 14, 15), (0, 14, 30), (0, 14, 45), (0, 15, 0), (0, 15, 15), (0, 15, 30), (0, 15, 45),
    (0, 16, 45), (0, 17, 15), (0, 17, 30), (0, 18, 0), (0, 18, 15), (0, 18, 30),
    (0, 19, 0), (0, 19, 15), (0, 19, 30), (0, 20, 15), (0, 20, 30), (0, 20, 45),
    (0, 21, 0), (0, 21, 30), (0, 22, 0), (0, 23, 0), (0, 23, 30),
    # Mardi (33 candles)
    (1, 0, 0), (1, 1, 15), (1, 1, 30), (1, 2, 45), (1, 3, 15), (1, 4, 15), (1, 4, 30),
    (1, 5, 0), (1, 5, 15), (1, 6, 0), (1, 7, 0), (1, 7, 30), (1, 7, 45),
    (1, 9, 0), (1, 9, 30), (1, 10, 15), (1, 11, 15), (1, 14, 15), (1, 15, 0), (1, 15, 30),
    (1, 16, 30), (1, 17, 0), (1, 18, 0), (1, 18, 15), (1, 18, 45),
    (1, 19, 0), (1, 19, 15), (1, 19, 30), (1, 20, 0), (1, 22, 15), (1, 22, 30), (1, 22, 45), (1, 23, 0),
    # Mercredi (31 candles)
    (2, 0, 0), (2, 0, 15), (2, 0, 30), (2, 2, 45), (2, 3, 15), (2, 3, 30), (2, 4, 15),
    (2, 5, 0), (2, 6, 30), (2, 7, 0), (2, 7, 30), (2, 8, 0), (2, 8, 15), (2, 8, 30),
    (2, 9, 15), (2, 9, 30), (2, 10, 30), (2, 11, 15), (2, 15, 0), (2, 16, 0), (2, 16, 45),
    (2, 17, 15), (2, 17, 30), (2, 18, 0), (2, 18, 30), (2, 19, 30), (2, 20, 30),
    (2, 21, 45), (2, 23, 0), (2, 23, 15), (2, 23, 45),
    # Jeudi (42 candles)
    (3, 0, 0), (3, 0, 15), (3, 1, 30), (3, 2, 0), (3, 2, 15), (3, 3, 0), (3, 3, 30),
    (3, 4, 0), (3, 4, 15), (3, 4, 30), (3, 5, 15), (3, 5, 30), (3, 5, 45),
    (3, 6, 15), (3, 6, 30), (3, 7, 0), (3, 7, 30), (3, 7, 45), (3, 8, 0), (3, 8, 30),
    (3, 9, 0), (3, 9, 30), (3, 10, 30), (3, 11, 0), (3, 11, 15), (3, 12, 30),
    (3, 13, 15), (3, 13, 30), (3, 13, 45), (3, 14, 30), (3, 15, 15), (3, 15, 30),
    (3, 16, 0), (3, 16, 30), (3, 18, 30), (3, 19, 30), (3, 20, 30), (3, 21, 0),
    (3, 22, 0), (3, 22, 15), (3, 22, 30), (3, 23, 15),
    # Vendredi (40 candles)
    (4, 0, 30), (4, 2, 0), (4, 2, 15), (4, 2, 30), (4, 3, 0), (4, 4, 15), (4, 4, 30),
    (4, 5, 0), (4, 5, 15), (4, 5, 30), (4, 6, 0), (4, 6, 30), (4, 7, 0), (4, 7, 15), (4, 7, 30),
    (4, 8, 0), (4, 8, 45), (4, 10, 0), (4, 10, 30), (4, 10, 45), (4, 11, 0),
    (4, 13, 15), (4, 14, 15), (4, 14, 30), (4, 14, 45), (4, 15, 15), (4, 15, 30), (4, 15, 45),
    (4, 16, 15), (4, 16, 45), (4, 17, 0), (4, 17, 15), (4, 17, 30), (4, 18, 15),
    (4, 19, 0), (4, 20, 0), (4, 22, 0), (4, 22, 15), (4, 23, 0), (4, 23, 15),
    # Samedi (18 candles)
    (5, 0, 0), (5, 0, 15), (5, 1, 15), (5, 3, 0), (5, 3, 15), (5, 4, 15),
    (5, 6, 0), (5, 8, 15), (5, 8, 30), (5, 9, 45), (5, 10, 30), (5, 12, 15),
    (5, 13, 0), (5, 15, 15), (5, 19, 15), (5, 20, 30), (5, 22, 30), (5, 22, 45),
    # Dimanche (27 candles)
    (6, 0, 45), (6, 1, 30), (6, 2, 30), (6, 4, 0), (6, 4, 30), (6, 5, 30), (6, 5, 45),
    (6, 6, 30), (6, 7, 15), (6, 8, 30), (6, 8, 45), (6, 11, 15), (6, 13, 15), (6, 13, 30),
    (6, 15, 30), (6, 16, 30), (6, 17, 0), (6, 17, 15), (6, 19, 0), (6, 19, 45),
    (6, 21, 45), (6, 22, 0), (6, 22, 30), (6, 22, 45), (6, 23, 0), (6, 23, 15), (6, 23, 30),
}

def fetch_data(symbol, days=730):
    """Télécharge les données historiques"""
    print(f"    Téléchargement {symbol}...", end=" ", flush=True)
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
    print(f"OK ({len(df):,} bougies)")
    return df

def calculate_indicators(df):
    """Calcule RSI et Stochastic"""
    # RSI (period 7)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic (period 5)
    low_min = df['low'].rolling(window=STOCH_PERIOD).min()
    high_max = df['high'].rolling(window=STOCH_PERIOD).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Time info
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute

    return df

def get_candle_action(day, hour, minute):
    """Retourne TRADE, SKIP ou REVERSE"""
    candle_key = (day, hour, minute)
    if candle_key in REVERSE_CANDLES:
        return 'REVERSE'
    elif candle_key in BLOCKED_CANDLES:
        return 'SKIP'
    return 'TRADE'

def backtest_v81(df, pair_name):
    """Backtest V8.1 HYBRIDE avec SKIP + REVERSE"""
    results = []
    stats = {'trades': 0, 'skipped': 0, 'reversed': 0}

    for i in range(30, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # Vérifier action pour cette candle
        action = get_candle_action(row['day_of_week'], row['hour'], row['minute'])

        if action == 'SKIP':
            stats['skipped'] += 1
            continue

        # Générer le signal de base
        signal = None

        # Signal UP
        if row['rsi'] < RSI_OVERSOLD and row['stoch_k'] < STOCH_OVERSOLD:
            signal = 'UP'
        # Signal DOWN
        elif row['rsi'] > RSI_OVERBOUGHT and row['stoch_k'] > STOCH_OVERBOUGHT:
            signal = 'DOWN'

        if signal is None:
            continue

        # REVERSE si nécessaire
        if action == 'REVERSE':
            signal = 'DOWN' if signal == 'UP' else 'UP'
            stats['reversed'] += 1

        # Évaluer le résultat
        win = (next_row['close'] > row['close']) if signal == 'UP' else (next_row['close'] < row['close'])
        pnl = WIN_PROFIT if win else LOSS

        results.append({
            'timestamp': row['timestamp'],
            'year': row['year'],
            'month': row['month'],
            'pair': pair_name,
            'signal': signal,
            'action': action,
            'win': win,
            'pnl': pnl
        })

        stats['trades'] += 1

    return pd.DataFrame(results), stats

def main():
    print("=" * 90)
    print("  BACKTEST V8.1 HYBRIDE - DETAIL MENSUEL 2024-2025")
    print("  3 bots (BTC, ETH, XRP) - $100/trade @ 52.5c")
    print("=" * 90)
    print(f"\n  Configuration V8.1 HYBRIDE:")
    print(f"  • Entry Price: {ENTRY_PRICE*100:.1f}c | Bet: ${BET}")
    print(f"  • WIN: +${WIN_PROFIT:.2f} | LOSS: -${BET}")
    print(f"  • RSI({RSI_PERIOD}): <{RSI_OVERSOLD} UP | >{RSI_OVERBOUGHT} DOWN")
    print(f"  • Stoch({STOCH_PERIOD}): <{STOCH_OVERSOLD} UP | >{STOCH_OVERBOUGHT} DOWN")
    print(f"  • Filtres: {len(BLOCKED_CANDLES)} SKIP + {len(REVERSE_CANDLES)} REVERSE")

    # Télécharger les données
    print("\n" + "-" * 90)
    print("  Téléchargement des données (2 ans)...")
    print("-" * 90)

    all_data = {}
    for pair in PAIRS:
        symbol = f"{pair}/USDT"
        df = fetch_data(symbol)
        df = calculate_indicators(df)
        all_data[pair] = df

    # Backtest
    print("\n" + "-" * 90)
    print("  Exécution du backtest V8.1 HYBRIDE...")
    print("-" * 90)

    all_results = []
    total_stats = {'trades': 0, 'skipped': 0, 'reversed': 0}

    for pair in PAIRS:
        results, stats = backtest_v81(all_data[pair], pair)
        all_results.append(results)
        total_stats['trades'] += stats['trades']
        total_stats['skipped'] += stats['skipped']
        total_stats['reversed'] += stats['reversed']
        print(f"    {pair}: {stats['trades']:,} trades | {stats['skipped']:,} skipped | {stats['reversed']:,} reversed")

    df_all = pd.concat(all_results, ignore_index=True)

    # Résultats par année et mois
    print("\n" + "=" * 90)
    print("  RESULTATS MENSUELS DETAILLES - V8.1 HYBRIDE ($100/trade)")
    print("=" * 90)

    for year in [2024, 2025]:
        year_df = df_all[df_all['year'] == year]

        if len(year_df) == 0:
            continue

        print(f"\n{'='*90}")
        print(f"  ANNEE {year}")
        print(f"{'='*90}")
        print(f"\n  {'Mois':<12} {'Trades':>8} {'Wins':>6} {'Loss':>6} {'WR':>8} {'PnL':>14}  | {'BTC':>10} {'ETH':>10} {'XRP':>10}")
        print(f"  {'-'*12} {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*14}  | {'-'*10} {'-'*10} {'-'*10}")

        year_total_trades = 0
        year_total_wins = 0
        year_total_pnl = 0
        months_count = 0

        for month in range(1, 13):
            month_df = year_df[year_df['month'] == month]

            if len(month_df) == 0:
                continue

            months_count += 1
            month_name = datetime(year, month, 1).strftime('%B')

            # Stats par paire
            btc_pnl = month_df[month_df['pair'] == 'BTC']['pnl'].sum()
            eth_pnl = month_df[month_df['pair'] == 'ETH']['pnl'].sum()
            xrp_pnl = month_df[month_df['pair'] == 'XRP']['pnl'].sum()

            # Stats globales
            total_trades = len(month_df)
            total_wins = month_df['win'].sum()
            total_losses = total_trades - total_wins
            total_pnl = month_df['pnl'].sum()
            win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

            year_total_trades += total_trades
            year_total_wins += total_wins
            year_total_pnl += total_pnl

            # Affichage avec couleur
            pnl_sign = "+" if total_pnl >= 0 else ""
            print(f"  {month_name:<12} {total_trades:>8,} {int(total_wins):>6,} {total_losses:>6,} {win_rate:>7.1f}% {pnl_sign}${total_pnl:>12,.0f}  | ${btc_pnl:>9,.0f} ${eth_pnl:>9,.0f} ${xrp_pnl:>9,.0f}")

        # Total année
        year_wr = (year_total_wins / year_total_trades * 100) if year_total_trades > 0 else 0
        avg_monthly = year_total_pnl / months_count if months_count > 0 else 0

        print(f"  {'-'*12} {'-'*8} {'-'*6} {'-'*6} {'-'*8} {'-'*14}")
        year_sign = "+" if year_total_pnl >= 0 else ""
        print(f"  {'TOTAL':<12} {year_total_trades:>8,} {int(year_total_wins):>6,} {year_total_trades-int(year_total_wins):>6,} {year_wr:>7.1f}% {year_sign}${year_total_pnl:>12,.0f}")
        avg_sign = "+" if avg_monthly >= 0 else ""
        print(f"  {'MOYENNE/MOIS':<12} {year_total_trades//max(months_count,1):>8,} {'':<6} {'':<6} {'':<8} {avg_sign}${avg_monthly:>12,.0f}")

    # Résumé final
    print("\n" + "=" * 90)
    print("  RESUME FINAL - V8.1 HYBRIDE - 3 BOTS x $100/TRADE")
    print("=" * 90)

    total_trades = len(df_all)
    total_wins = df_all['win'].sum()
    total_pnl = df_all['pnl'].sum()
    overall_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    # Trades par jour
    if len(df_all) > 0:
        days = (df_all['timestamp'].max() - df_all['timestamp'].min()).days
        days = max(days, 1)
        trades_per_day = total_trades / days
    else:
        days = 0
        trades_per_day = 0

    # Mois distincts
    df_all['year_month'] = df_all['year'].astype(str) + '-' + df_all['month'].astype(str).str.zfill(2)
    months_count = df_all['year_month'].nunique()
    avg_monthly_pnl = total_pnl / months_count if months_count > 0 else 0

    print(f"\n  Total Trades:       {total_trades:,}")
    print(f"  Trades/jour:        {trades_per_day:.1f}")
    print(f"  Win Rate:           {overall_wr:.1f}%")
    print(f"  PnL Total:          ${total_pnl:,.0f}")
    print(f"  PnL Mensuel Moyen:  ${avg_monthly_pnl:,.0f}")

    # Meilleur et pire mois
    monthly_pnl = df_all.groupby('year_month')['pnl'].sum()
    if len(monthly_pnl) > 0:
        best_month = monthly_pnl.idxmax()
        worst_month = monthly_pnl.idxmin()
        print(f"\n  Meilleur mois:      {best_month} (+${monthly_pnl[best_month]:,.0f})")
        print(f"  Pire mois:          {worst_month} (${monthly_pnl[worst_month]:,.0f})")

    # Stats par paire
    print(f"\n  {'Paire':<8} {'Trades':>10} {'WR':>8} {'PnL Total':>14} {'PnL/mois':>12}")
    print(f"  {'-'*8} {'-'*10} {'-'*8} {'-'*14} {'-'*12}")

    for pair in PAIRS:
        pair_df = df_all[df_all['pair'] == pair]
        if len(pair_df) > 0:
            p_trades = len(pair_df)
            p_wins = pair_df['win'].sum()
            p_wr = (p_wins / p_trades * 100)
            p_pnl = pair_df['pnl'].sum()
            p_monthly = p_pnl / months_count if months_count > 0 else 0
            print(f"  {pair:<8} {p_trades:>10,} {p_wr:>7.1f}% ${p_pnl:>13,.0f} ${p_monthly:>11,.0f}")

    print("\n" + "=" * 90)
    print("  STATISTIQUES V8.1 HYBRIDE")
    print("=" * 90)
    print(f"  Candles analysées:  {total_stats['trades'] + total_stats['skipped']:,}")
    print(f"  Trades exécutés:    {total_stats['trades']:,}")
    print(f"  Candles SKIP:       {total_stats['skipped']:,}")
    print(f"  Candles REVERSE:    {total_stats['reversed']:,}")
    print("=" * 90)

if __name__ == "__main__":
    main()
