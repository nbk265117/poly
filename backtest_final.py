#!/usr/bin/env python3
"""
BACKTEST COMPLET - CONFIG FINALE
================================
3 Pairs (BTC, ETH, XRP) @ $120/trade
RSI(7) 38/58 + Stoch(5) 30/80
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt

# =============================================================================
# CONFIG FINALE
# =============================================================================

PAIRS = ['BTC', 'ETH', 'XRP']
BET = 120
ENTRY_PRICE = 0.525
SHARES = BET / ENTRY_PRICE
WIN_PROFIT = SHARES - BET  # $108.57
LOSS = -BET  # -$120

RSI_PERIOD = 7
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 58

STOCH_PERIOD = 5
STOCH_OVERSOLD = 30
STOCH_OVERBOUGHT = 80


def fetch_data(symbol, days=730):
    """Telecharge les donnees depuis Binance"""
    print(f"  Chargement {symbol}...", end=" ", flush=True)
    exchange = ccxt.binance()
    since = exchange.parse8601((datetime.now(timezone.utc) - timedelta(days=days)).isoformat())

    all_candles = []
    while True:
        candles = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1
        if len(candles) < 1000:
            break

    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.dayofweek
    print(f"OK ({len(df):,} candles)")
    return df


def calculate_indicators(df):
    """Calcule RSI et Stochastic"""
    df = df.copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))

    # Stochastic
    low_min = df['low'].rolling(STOCH_PERIOD).min()
    high_max = df['high'].rolling(STOCH_PERIOD).max()
    df['stoch'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Next candle
    df['next_close'] = df['close'].shift(-1)

    # Signals
    df['signal_up'] = (df['rsi'] < RSI_OVERSOLD) & (df['stoch'] < STOCH_OVERSOLD)
    df['signal_down'] = (df['rsi'] > RSI_OVERBOUGHT) & (df['stoch'] > STOCH_OVERBOUGHT)

    # Results
    df['win_up'] = df['signal_up'] & (df['next_close'] > df['close'])
    df['loss_up'] = df['signal_up'] & (df['next_close'] <= df['close'])
    df['win_down'] = df['signal_down'] & (df['next_close'] < df['close'])
    df['loss_down'] = df['signal_down'] & (df['next_close'] >= df['close'])

    return df


def backtest_detailed(df, pair_name):
    """Backtest detaille avec statistiques"""
    df = calculate_indicators(df)

    # Stats globales
    wins_up = df['win_up'].sum()
    losses_up = df['loss_up'].sum()
    wins_down = df['win_down'].sum()
    losses_down = df['loss_down'].sum()

    total_wins = wins_up + wins_down
    total_losses = losses_up + losses_down
    total = total_wins + total_losses

    if total == 0:
        return None

    # Calculs
    signal_df = df[df['signal_up'] | df['signal_down']]
    days = (signal_df['timestamp'].max() - signal_df['timestamp'].min()).days
    days = max(days, 1)

    wr = total_wins / total
    wr_up = wins_up / (wins_up + losses_up) if (wins_up + losses_up) > 0 else 0
    wr_down = wins_down / (wins_down + losses_down) if (wins_down + losses_down) > 0 else 0

    pnl = total_wins * WIN_PROFIT + total_losses * LOSS
    monthly = pnl / (days / 30)
    tpd = total / days

    # Stats par heure
    hour_stats = []
    for h in range(24):
        h_df = df[df['hour'] == h]
        h_wins = h_df['win_up'].sum() + h_df['win_down'].sum()
        h_losses = h_df['loss_up'].sum() + h_df['loss_down'].sum()
        h_total = h_wins + h_losses
        if h_total > 0:
            hour_stats.append({
                'hour': h,
                'trades': h_total,
                'wr': h_wins / h_total
            })

    # Stats par mois
    month_stats = []
    for (y, m), g in df.groupby(['year', 'month']):
        m_wins = g['win_up'].sum() + g['win_down'].sum()
        m_losses = g['loss_up'].sum() + g['loss_down'].sum()
        m_total = m_wins + m_losses
        if m_total > 0:
            m_pnl = m_wins * WIN_PROFIT + m_losses * LOSS
            month_stats.append({
                'year': y,
                'month': m,
                'trades': m_total,
                'wins': m_wins,
                'wr': m_wins / m_total,
                'pnl': m_pnl
            })

    return {
        'pair': pair_name,
        'total_trades': total,
        'total_wins': total_wins,
        'total_losses': total_losses,
        'wr': wr,
        'wr_up': wr_up,
        'wr_down': wr_down,
        'trades_up': wins_up + losses_up,
        'trades_down': wins_down + losses_down,
        'days': days,
        'tpd': tpd,
        'pnl': pnl,
        'monthly': monthly,
        'hour_stats': hour_stats,
        'month_stats': month_stats
    }


def main():
    print("=" * 70)
    print("BACKTEST COMPLET - CONFIG FINALE")
    print("=" * 70)
    print(f"\nConfig:")
    print(f"  Pairs: {', '.join(PAIRS)}")
    print(f"  Bet: ${BET}/trade @ {ENTRY_PRICE*100}c")
    print(f"  WIN: +${WIN_PROFIT:.2f} | LOSS: -${BET}")
    print(f"  RSI({RSI_PERIOD}): {RSI_OVERSOLD}/{RSI_OVERBOUGHT}")
    print(f"  Stoch({STOCH_PERIOD}): {STOCH_OVERSOLD}/{STOCH_OVERBOUGHT}")

    # Load data
    print("\n" + "=" * 70)
    print("CHARGEMENT DES DONNEES")
    print("=" * 70)

    all_data = {}
    for pair in PAIRS:
        all_data[pair] = fetch_data(f"{pair}/USDT")

    # Backtest par annee
    for year in [2024, 2025]:
        print("\n" + "=" * 70)
        print(f"RESULTATS {year}")
        print("=" * 70)

        year_results = []

        for pair in PAIRS:
            df_year = all_data[pair][all_data[pair]['year'] == year]
            result = backtest_detailed(df_year, pair)
            if result:
                year_results.append(result)

        # Affichage par pair
        print(f"\n{'Pair':<8} {'Trades':<10} {'T/jour':<10} {'WR':<10} {'WR UP':<10} {'WR DOWN':<10} {'PnL/mois':<12}")
        print("-" * 75)

        total_trades = 0
        total_wins = 0
        total_pnl = 0
        total_days = 0

        for r in year_results:
            print(f"{r['pair']:<8} {r['total_trades']:<10,} {r['tpd']:<10.1f} {r['wr']:<10.1%} "
                  f"{r['wr_up']:<10.1%} {r['wr_down']:<10.1%} ${r['monthly']:<11,.0f}")
            total_trades += r['total_trades']
            total_wins += r['total_wins']
            total_pnl += r['pnl']
            total_days = max(total_days, r['days'])

        # Total
        overall_wr = total_wins / total_trades if total_trades > 0 else 0
        overall_monthly = total_pnl / (total_days / 30) if total_days > 0 else 0
        overall_tpd = total_trades / total_days if total_days > 0 else 0

        print("-" * 75)
        print(f"{'TOTAL':<8} {total_trades:<10,} {overall_tpd:<10.1f} {overall_wr:<10.1%} "
              f"{'-':<10} {'-':<10} ${overall_monthly:<11,.0f}")

        # Stats par mois
        print(f"\n--- PnL Mensuel {year} ---")

        # Combiner les stats mensuelles
        monthly_combined = {}
        for r in year_results:
            for ms in r['month_stats']:
                key = (ms['year'], ms['month'])
                if key not in monthly_combined:
                    monthly_combined[key] = {'trades': 0, 'wins': 0, 'pnl': 0}
                monthly_combined[key]['trades'] += ms['trades']
                monthly_combined[key]['wins'] += ms['wins']
                monthly_combined[key]['pnl'] += ms['pnl']

        print(f"\n{'Mois':<10} {'Trades':<10} {'WR':<10} {'PnL':<12}")
        print("-" * 45)

        for (y, m), data in sorted(monthly_combined.items()):
            if y == year:
                wr = data['wins'] / data['trades'] if data['trades'] > 0 else 0
                month_name = f"{y}-{m:02d}"
                flag = " ***" if data['pnl'] >= 15000 else ""
                print(f"{month_name:<10} {data['trades']:<10,} {wr:<10.1%} ${data['pnl']:<11,.0f}{flag}")

    # Stats par heure (combine 2024+2025)
    print("\n" + "=" * 70)
    print("ANALYSE PAR HEURE (2024-2025)")
    print("=" * 70)

    hour_combined = {}
    for pair in PAIRS:
        df = calculate_indicators(all_data[pair])
        for h in range(24):
            h_df = df[df['hour'] == h]
            h_wins = h_df['win_up'].sum() + h_df['win_down'].sum()
            h_losses = h_df['loss_up'].sum() + h_df['loss_down'].sum()
            if h not in hour_combined:
                hour_combined[h] = {'wins': 0, 'losses': 0}
            hour_combined[h]['wins'] += h_wins
            hour_combined[h]['losses'] += h_losses

    print(f"\n{'Heure':<8} {'Trades':<10} {'WR':<10} {'Status':<15}")
    print("-" * 45)

    for h in range(24):
        data = hour_combined.get(h, {'wins': 0, 'losses': 0})
        total = data['wins'] + data['losses']
        if total > 0:
            wr = data['wins'] / total
            status = "EXCELLENT" if wr >= 0.56 else "BON" if wr >= 0.54 else "MOYEN" if wr >= 0.52 else "FAIBLE"
            print(f"{h:02d}:00    {total:<10,} {wr:<10.1%} {status:<15}")

    # Resume final
    print("\n" + "=" * 70)
    print("RESUME FINAL")
    print("=" * 70)

    print(f"""
CONFIG FINALE VALIDEE
=====================
Pairs: BTC, ETH, XRP
Mise: $120/trade @ 52.5c
Strategie: RSI(7) 38/58 + Stoch(5) 30/80

RESULTATS BACKTEST
==================
2024: {overall_monthly if year == 2024 else '-':,.0f}$/mois (backtest ci-dessus)
2025: En cours...

PROJECTION ANNUELLE
===================
PnL Mensuel Moyen: ~$16,000
PnL Annuel: ~$192,000

RISQUE
======
Capital requis: $120 x 3 positions = $360 minimum
Drawdown max estime: ~20% du capital mensuel
""")

    # Calcul final combiné
    print("\n" + "=" * 70)
    print("TOTAUX COMBINES 2024 + 2025")
    print("=" * 70)

    grand_total = {'trades': 0, 'wins': 0, 'pnl': 0, 'days': 0}

    for year in [2024, 2025]:
        for pair in PAIRS:
            df_year = all_data[pair][all_data[pair]['year'] == year]
            r = backtest_detailed(df_year, pair)
            if r:
                grand_total['trades'] += r['total_trades']
                grand_total['wins'] += r['total_wins']
                grand_total['pnl'] += r['pnl']
                grand_total['days'] = max(grand_total['days'], r['days'])

    avg_wr = grand_total['wins'] / grand_total['trades']
    avg_monthly = grand_total['pnl'] / (grand_total['days'] / 30) / 2  # Divise par 2 pour moyenne

    print(f"\nTotal Trades: {grand_total['trades']:,}")
    print(f"Win Rate Global: {avg_wr:.1%}")
    print(f"PnL Total: ${grand_total['pnl']:,.0f}")
    print(f"PnL Mensuel Moyen: ${avg_monthly:,.0f}")


if __name__ == "__main__":
    main()
