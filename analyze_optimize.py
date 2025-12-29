#!/usr/bin/env python3
"""
ANALYSE DES TRADES PERDANTS + OPTIMISATION MAXIMALE
====================================================
Objectif: $15,000+ / mois
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import ccxt

PAIRS = ['BTC', 'ETH', 'XRP']
ENTRY_PRICE = 0.525
BET = 100
SHARES = BET / ENTRY_PRICE
WIN_PROFIT = SHARES - BET  # $90.48
LOSS = -BET  # -$100

# Pour avoir $15,000/mois avec ce ratio:
# PnL = Wins * 90.48 - Losses * 100
# Si WR = 55%, 1000 trades: 550*90.48 - 450*100 = 49,764 - 45,000 = $4,764
# Pour $15,000: besoin de ~3150 trades/mois = 105 trades/jour
# OU augmenter WR a 57%+

def fetch_data(symbol, days=730):
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
    return df


def calculate_indicators(df):
    """Calcule TOUS les indicateurs possibles pour analyse"""
    df = df.copy()

    # RSI multiple periods
    for period in [5, 7, 9, 14]:
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        df[f'rsi_{period}'] = 100 - (100 / (1 + gain / loss))

    # Stochastic multiple periods
    for period in [5, 7, 9, 14]:
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        df[f'stoch_{period}'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # EMAs
    for period in [5, 8, 13, 21, 50]:
        df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()

    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    df['bb_pct'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    # Candle patterns
    df['body'] = abs(df['close'] - df['open'])
    df['range'] = df['high'] - df['low']
    df['body_pct'] = df['body'] / df['range'].replace(0, np.nan)
    df['is_green'] = df['close'] > df['open']
    df['is_red'] = df['close'] < df['open']

    # Consecutive candles
    df['green_streak'] = df['is_green'].groupby((~df['is_green']).cumsum()).cumsum()
    df['red_streak'] = df['is_red'].groupby((~df['is_red']).cumsum()).cumsum()

    # Volume
    df['vol_avg'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_avg']

    # Momentum
    df['mom_1'] = df['close'].pct_change(1) * 100
    df['mom_3'] = df['close'].pct_change(3) * 100
    df['mom_5'] = df['close'].pct_change(5) * 100

    # Hour
    df['hour'] = df['timestamp'].dt.hour
    df['day'] = df['timestamp'].dt.dayofweek

    # Next candle (for results)
    df['next_close'] = df['close'].shift(-1)
    df['next_change'] = (df['next_close'] - df['close']) / df['close'] * 100

    return df


def analyze_losing_trades(df, rsi_low=35, rsi_high=65, stoch_low=30, stoch_high=70):
    """Analyse pourquoi les trades perdent"""
    df = df.copy()

    # Signal UP
    df['signal_up'] = (df['rsi_7'] < rsi_low) & (df['stoch_5'] < stoch_low)
    df['signal_down'] = (df['rsi_7'] > rsi_high) & (df['stoch_5'] > stoch_high)

    # Resultats
    df['win_up'] = df['signal_up'] & (df['next_close'] > df['close'])
    df['loss_up'] = df['signal_up'] & (df['next_close'] <= df['close'])
    df['win_down'] = df['signal_down'] & (df['next_close'] < df['close'])
    df['loss_down'] = df['signal_down'] & (df['next_close'] >= df['close'])

    # Analyse des perdants UP
    losing_up = df[df['loss_up']].copy()
    winning_up = df[df['win_up']].copy()

    # Analyse des perdants DOWN
    losing_down = df[df['loss_down']].copy()
    winning_down = df[df['win_down']].copy()

    print("\n" + "=" * 70)
    print("ANALYSE DES TRADES PERDANTS")
    print("=" * 70)

    print(f"\n--- SIGNAL UP (RSI<{rsi_low}, Stoch<{stoch_low}) ---")
    print(f"Gagnants: {len(winning_up):,} | Perdants: {len(losing_up):,}")

    if len(losing_up) > 0 and len(winning_up) > 0:
        print(f"\nMoyenne RSI_7:")
        print(f"  Gagnants: {winning_up['rsi_7'].mean():.1f}")
        print(f"  Perdants: {losing_up['rsi_7'].mean():.1f}")

        print(f"\nMoyenne Stoch_5:")
        print(f"  Gagnants: {winning_up['stoch_5'].mean():.1f}")
        print(f"  Perdants: {losing_up['stoch_5'].mean():.1f}")

        print(f"\nMoyenne Red Streak:")
        print(f"  Gagnants: {winning_up['red_streak'].mean():.1f}")
        print(f"  Perdants: {losing_up['red_streak'].mean():.1f}")

        print(f"\nMoyenne Momentum 3:")
        print(f"  Gagnants: {winning_up['mom_3'].mean():.2f}%")
        print(f"  Perdants: {losing_up['mom_3'].mean():.2f}%")

        print(f"\nMoyenne Volume Ratio:")
        print(f"  Gagnants: {winning_up['vol_ratio'].mean():.2f}")
        print(f"  Perdants: {losing_up['vol_ratio'].mean():.2f}")

        # Heures
        print(f"\nHeures les plus perdantes (UP):")
        hour_loss = losing_up.groupby('hour').size()
        hour_win = winning_up.groupby('hour').size()
        hour_wr = hour_win / (hour_win + hour_loss)
        worst_hours = hour_wr.nsmallest(5)
        for h, wr in worst_hours.items():
            print(f"  {h}h: {wr:.1%} WR")

    print(f"\n--- SIGNAL DOWN (RSI>{rsi_high}, Stoch>{stoch_high}) ---")
    print(f"Gagnants: {len(winning_down):,} | Perdants: {len(losing_down):,}")

    if len(losing_down) > 0 and len(winning_down) > 0:
        print(f"\nMoyenne RSI_7:")
        print(f"  Gagnants: {winning_down['rsi_7'].mean():.1f}")
        print(f"  Perdants: {losing_down['rsi_7'].mean():.1f}")

        print(f"\nMoyenne Stoch_5:")
        print(f"  Gagnants: {winning_down['stoch_5'].mean():.1f}")
        print(f"  Perdants: {losing_down['stoch_5'].mean():.1f}")

        print(f"\nMoyenne Green Streak:")
        print(f"  Gagnants: {winning_down['green_streak'].mean():.1f}")
        print(f"  Perdants: {losing_down['green_streak'].mean():.1f}")

        # Heures
        print(f"\nHeures les plus perdantes (DOWN):")
        hour_loss = losing_down.groupby('hour').size()
        hour_win = winning_down.groupby('hour').size()
        hour_wr = hour_win / (hour_win + hour_loss)
        worst_hours = hour_wr.nsmallest(5)
        for h, wr in worst_hours.items():
            print(f"  {h}h: {wr:.1%} WR")

    return df


def test_optimizations(df):
    """Test differentes optimisations pour maximiser WR et PnL"""
    results = []

    # Test RSI thresholds
    for rsi_low in [25, 30, 32, 35, 38, 40]:
        for rsi_high in [60, 62, 65, 68, 70, 75]:
            for stoch_low in [20, 25, 30, 35]:
                for stoch_high in [65, 70, 75, 80]:

                    # Signals
                    sig_up = (df['rsi_7'] < rsi_low) & (df['stoch_5'] < stoch_low)
                    sig_down = (df['rsi_7'] > rsi_high) & (df['stoch_5'] > stoch_high)

                    # Results
                    wins = ((sig_up & (df['next_close'] > df['close'])) |
                           (sig_down & (df['next_close'] < df['close']))).sum()
                    losses = ((sig_up & (df['next_close'] <= df['close'])) |
                             (sig_down & (df['next_close'] >= df['close']))).sum()

                    total = wins + losses
                    if total < 100:
                        continue

                    wr = wins / total
                    pnl = wins * WIN_PROFIT + losses * LOSS

                    results.append({
                        'rsi_low': rsi_low,
                        'rsi_high': rsi_high,
                        'stoch_low': stoch_low,
                        'stoch_high': stoch_high,
                        'trades': total,
                        'wr': wr,
                        'pnl': pnl
                    })

    return pd.DataFrame(results)


def test_simple_strategies(df):
    """Test des strategies ultra simples"""
    results = []

    # 1. RSI seul
    for rsi_low in [25, 30, 35, 40]:
        for rsi_high in [60, 65, 70, 75]:
            sig_up = df['rsi_7'] < rsi_low
            sig_down = df['rsi_7'] > rsi_high

            wins = ((sig_up & (df['next_close'] > df['close'])) |
                   (sig_down & (df['next_close'] < df['close']))).sum()
            losses = ((sig_up & (df['next_close'] <= df['close'])) |
                     (sig_down & (df['next_close'] >= df['close']))).sum()

            total = wins + losses
            if total > 100:
                results.append({
                    'strategy': f'RSI({rsi_low}/{rsi_high})',
                    'trades': total,
                    'wr': wins/total,
                    'pnl': wins * WIN_PROFIT + losses * LOSS
                })

    # 2. Stoch seul
    for stoch_low in [20, 25, 30]:
        for stoch_high in [70, 75, 80]:
            sig_up = df['stoch_5'] < stoch_low
            sig_down = df['stoch_5'] > stoch_high

            wins = ((sig_up & (df['next_close'] > df['close'])) |
                   (sig_down & (df['next_close'] < df['close']))).sum()
            losses = ((sig_up & (df['next_close'] <= df['close'])) |
                     (sig_down & (df['next_close'] >= df['close']))).sum()

            total = wins + losses
            if total > 100:
                results.append({
                    'strategy': f'Stoch({stoch_low}/{stoch_high})',
                    'trades': total,
                    'wr': wins/total,
                    'pnl': wins * WIN_PROFIT + losses * LOSS
                })

    # 3. Consecutive candles (Mean Reversion)
    for streak in [2, 3, 4, 5]:
        sig_up = df['red_streak'] >= streak
        sig_down = df['green_streak'] >= streak

        wins = ((sig_up & (df['next_close'] > df['close'])) |
               (sig_down & (df['next_close'] < df['close']))).sum()
        losses = ((sig_up & (df['next_close'] <= df['close'])) |
                 (sig_down & (df['next_close'] >= df['close']))).sum()

        total = wins + losses
        if total > 100:
            results.append({
                'strategy': f'Streak({streak})',
                'trades': total,
                'wr': wins/total,
                'pnl': wins * WIN_PROFIT + losses * LOSS
            })

    # 4. Bollinger Bands
    for bb_low in [0.05, 0.1, 0.15, 0.2]:
        for bb_high in [0.8, 0.85, 0.9, 0.95]:
            sig_up = df['bb_pct'] < bb_low
            sig_down = df['bb_pct'] > bb_high

            wins = ((sig_up & (df['next_close'] > df['close'])) |
                   (sig_down & (df['next_close'] < df['close']))).sum()
            losses = ((sig_up & (df['next_close'] <= df['close'])) |
                     (sig_down & (df['next_close'] >= df['close']))).sum()

            total = wins + losses
            if total > 100:
                results.append({
                    'strategy': f'BB({bb_low}/{bb_high})',
                    'trades': total,
                    'wr': wins/total,
                    'pnl': wins * WIN_PROFIT + losses * LOSS
                })

    # 5. RSI + Streak combo
    for rsi_low in [30, 35, 40]:
        for streak in [2, 3]:
            sig_up = (df['rsi_7'] < rsi_low) | (df['red_streak'] >= streak)
            sig_down = (df['rsi_7'] > (100-rsi_low)) | (df['green_streak'] >= streak)

            wins = ((sig_up & (df['next_close'] > df['close'])) |
                   (sig_down & (df['next_close'] < df['close']))).sum()
            losses = ((sig_up & (df['next_close'] <= df['close'])) |
                     (sig_down & (df['next_close'] >= df['close']))).sum()

            total = wins + losses
            if total > 100:
                results.append({
                    'strategy': f'RSI{rsi_low}|Streak{streak}',
                    'trades': total,
                    'wr': wins/total,
                    'pnl': wins * WIN_PROFIT + losses * LOSS
                })

    return pd.DataFrame(results)


def main():
    print("=" * 70)
    print("ANALYSE & OPTIMISATION - OBJECTIF $15,000+/MOIS")
    print("=" * 70)

    # Load data
    print("\nChargement...")
    all_data = {}
    for pair in PAIRS:
        df = fetch_data(f"{pair}/USDT")
        df = calculate_indicators(df)
        all_data[pair] = df
        print(f"  {pair}: {len(df):,} candles")

    # Combine all pairs for analysis
    combined_2024 = pd.concat([df[df['year'] == 2024] for df in all_data.values()])
    combined_2025 = pd.concat([df[df['year'] == 2025] for df in all_data.values()])

    # Analyze losing trades
    print("\n" + "=" * 70)
    print("ANALYSE 2024")
    analyze_losing_trades(combined_2024)

    # Test optimizations
    print("\n" + "=" * 70)
    print("TEST OPTIMISATIONS RSI/STOCH - 2024")
    print("=" * 70)

    opt_results = test_optimizations(combined_2024)
    opt_results['monthly'] = opt_results['pnl'] / 12

    # Top by WR
    print("\nTop 10 par Win Rate:")
    top_wr = opt_results.nlargest(10, 'wr')
    for _, r in top_wr.iterrows():
        print(f"  RSI({r['rsi_low']}/{r['rsi_high']}) Stoch({r['stoch_low']}/{r['stoch_high']}): "
              f"{r['wr']:.1%} WR, {r['trades']:,} trades, ${r['monthly']:,.0f}/mois")

    # Top by PnL
    print("\nTop 10 par PnL mensuel:")
    top_pnl = opt_results.nlargest(10, 'monthly')
    for _, r in top_pnl.iterrows():
        print(f"  RSI({r['rsi_low']}/{r['rsi_high']}) Stoch({r['stoch_low']}/{r['stoch_high']}): "
              f"${r['monthly']:,.0f}/mois, {r['wr']:.1%} WR, {r['trades']:,} trades")

    # Test simple strategies
    print("\n" + "=" * 70)
    print("TEST STRATEGIES SIMPLES - 2024")
    print("=" * 70)

    simple_results = test_simple_strategies(combined_2024)
    simple_results['monthly'] = simple_results['pnl'] / 12

    print("\nTop strategies par PnL:")
    top_simple = simple_results.nlargest(15, 'monthly')
    for _, r in top_simple.iterrows():
        print(f"  {r['strategy']:<20}: ${r['monthly']:,.0f}/mois, {r['wr']:.1%} WR, {r['trades']:,} trades")

    # Validate on 2025
    print("\n" + "=" * 70)
    print("VALIDATION SUR 2025")
    print("=" * 70)

    simple_2025 = test_simple_strategies(combined_2025)
    simple_2025['monthly'] = simple_2025['pnl'] / 12

    print("\nTop strategies 2025:")
    top_2025 = simple_2025.nlargest(15, 'monthly')
    for _, r in top_2025.iterrows():
        print(f"  {r['strategy']:<20}: ${r['monthly']:,.0f}/mois, {r['wr']:.1%} WR, {r['trades']:,} trades")


if __name__ == "__main__":
    main()
