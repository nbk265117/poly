#!/usr/bin/env python3
"""
Recherche rapide de la configuration optimale:
- Minimum 60 trades/jour
- Minimum $10k PnL/mois (0 mois sous $10k)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

def fetch_ohlcv(symbol, timeframe='15m', days=730):
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
    df.set_index('timestamp', inplace=True)
    return df

def calculate_rsi(prices, period=7):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_stochastic(df, period=5):
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)

def get_ftfc_score(df_1h, df_4h, timestamp):
    ts = pd.Timestamp(timestamp)

    h1_data = df_1h[df_1h.index <= ts].tail(5)
    h4_data = df_4h[df_4h.index <= ts].tail(5)

    h1_trend = (h1_data['close'].iloc[-1] - h1_data['close'].iloc[0]) / h1_data['close'].iloc[0] * 100 if len(h1_data) >= 3 else 0
    h4_trend = (h4_data['close'].iloc[-1] - h4_data['close'].iloc[0]) / h4_data['close'].iloc[0] * 100 if len(h4_data) >= 3 else 0

    h1_rsi = calculate_rsi(df_1h['close'], 14).loc[df_1h.index <= ts].iloc[-1] if len(df_1h[df_1h.index <= ts]) > 14 else 50
    h4_rsi = calculate_rsi(df_4h['close'], 14).loc[df_4h.index <= ts].iloc[-1] if len(df_4h[df_4h.index <= ts]) > 14 else 50

    ftfc_score = 0
    if h1_trend > 0.1: ftfc_score += 1
    elif h1_trend < -0.1: ftfc_score -= 1
    if h4_trend > 0.2: ftfc_score += 1
    elif h4_trend < -0.2: ftfc_score -= 1
    if h1_rsi > 55: ftfc_score += 0.5
    elif h1_rsi < 45: ftfc_score -= 0.5
    if h4_rsi > 55: ftfc_score += 0.5
    elif h4_rsi < 45: ftfc_score -= 0.5

    return ftfc_score

def precompute_signals(df_15m, df_1h, df_4h):
    """Pre-calculate all indicators and FTFC scores"""
    df = df_15m.copy()
    df['rsi'] = calculate_rsi(df['close'], 7)
    df['stoch'] = calculate_stochastic(df, 5)
    df['next_close'] = df['close'].shift(-1)
    df['price_up'] = df['next_close'] > df['close']

    print("    Pre-computing FTFC scores...")
    ftfc_scores = []
    total = len(df)
    for i, (idx, row) in enumerate(df.iterrows()):
        if i % 10000 == 0:
            print(f"      Progress: {i}/{total} ({i/total*100:.0f}%)")
        ftfc_scores.append(get_ftfc_score(df_1h, df_4h, idx))
    df['ftfc_score'] = ftfc_scores

    return df

def simulate_config(df, rsi_low, rsi_high, stoch_low, stoch_high, ftfc_threshold, bet_size=100, entry_price=0.525):
    """Simulate a specific configuration"""
    trades = []

    for i in range(len(df) - 1):
        row = df.iloc[i]

        if pd.isna(row['rsi']) or pd.isna(row['stoch']) or pd.isna(row['ftfc_score']):
            continue

        signal = None

        # Check UP signal
        if row['rsi'] < rsi_low and row['stoch'] < stoch_low:
            if row['ftfc_score'] > -ftfc_threshold:  # Not strongly bearish
                signal = 'UP'
        # Check DOWN signal
        elif row['rsi'] > rsi_high and row['stoch'] > stoch_high:
            if row['ftfc_score'] < ftfc_threshold:  # Not strongly bullish
                signal = 'DOWN'

        if signal:
            win = (signal == 'UP' and row['price_up']) or (signal == 'DOWN' and not row['price_up'])
            shares = bet_size / entry_price
            pnl = shares * (1 - entry_price) if win else -bet_size

            trades.append({
                'timestamp': row.name,
                'signal': signal,
                'win': win,
                'pnl': pnl
            })

    return pd.DataFrame(trades)

def evaluate_config(all_data, config):
    """Evaluate a configuration across all pairs"""
    all_trades = []

    for pair, df in all_data.items():
        trades = simulate_config(
            df,
            config['rsi_low'], config['rsi_high'],
            config['stoch_low'], config['stoch_high'],
            config['ftfc_threshold']
        )
        trades['pair'] = pair
        all_trades.append(trades)

    if not all_trades:
        return None

    combined = pd.concat(all_trades, ignore_index=True)
    combined['month'] = combined['timestamp'].dt.to_period('M')

    total_trades = len(combined)
    trades_per_day = total_trades / 730
    total_wr = combined['win'].mean() * 100
    total_pnl = combined['pnl'].sum()

    monthly = combined.groupby('month')['pnl'].sum()
    months_under_10k = (monthly < 10000).sum()
    min_month_pnl = monthly.min()

    return {
        'trades': total_trades,
        'trades_per_day': trades_per_day,
        'wr': total_wr,
        'pnl': total_pnl,
        'pnl_per_month': total_pnl / len(monthly),
        'months_under_10k': months_under_10k,
        'min_month_pnl': min_month_pnl,
        'monthly': monthly
    }

def main():
    print("=" * 70)
    print("RECHERCHE CONFIGURATION OPTIMALE")
    print("Objectifs: 60+ trades/jour ET $10k+ PnL/mois")
    print("=" * 70)

    # Load and precompute data
    pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    all_data = {}

    for pair in pairs:
        print(f"\nLoading {pair}...")
        df_15m = fetch_ohlcv(pair, '15m', 730)
        df_1h = fetch_ohlcv(pair, '1h', 730)
        df_4h = fetch_ohlcv(pair, '4h', 730)
        print(f"  15m: {len(df_15m)} | 1h: {len(df_1h)} | 4h: {len(df_4h)}")

        print("  Pre-computing indicators...")
        all_data[pair.split('/')[0]] = precompute_signals(df_15m, df_1h, df_4h)

    # Test configurations
    configs = [
        # V7 Original (no FTFC filter)
        {'name': 'V7 Original', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 99},
        # V8 Strict
        {'name': 'V8 Strict (1.0)', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 1.0},
        # V8 Relaxed variations
        {'name': 'V8 Relaxed (1.5)', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 1.5},
        {'name': 'V8 Relaxed (2.0)', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 2.0},
        {'name': 'V8 Relaxed (2.5)', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 2.5},
        # Wider RSI
        {'name': 'RSI 40/65 + FTFC 1.5', 'rsi_low': 40, 'rsi_high': 65, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 1.5},
        {'name': 'RSI 40/65 + FTFC 2.0', 'rsi_low': 40, 'rsi_high': 65, 'stoch_low': 30, 'stoch_high': 75, 'ftfc_threshold': 2.0},
        # Wider Stoch
        {'name': 'Stoch 35/70 + FTFC 1.5', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 35, 'stoch_high': 70, 'ftfc_threshold': 1.5},
        {'name': 'Stoch 35/70 + FTFC 2.0', 'rsi_low': 38, 'rsi_high': 68, 'stoch_low': 35, 'stoch_high': 70, 'ftfc_threshold': 2.0},
        # Combo wider
        {'name': 'Combo (40/65, 35/70, 1.5)', 'rsi_low': 40, 'rsi_high': 65, 'stoch_low': 35, 'stoch_high': 70, 'ftfc_threshold': 1.5},
        {'name': 'Combo (40/65, 35/70, 2.0)', 'rsi_low': 40, 'rsi_high': 65, 'stoch_low': 35, 'stoch_high': 70, 'ftfc_threshold': 2.0},
        # Very wide (more trades)
        {'name': 'Wide (42/62, 38/68, 2.0)', 'rsi_low': 42, 'rsi_high': 62, 'stoch_low': 38, 'stoch_high': 68, 'ftfc_threshold': 2.0},
        {'name': 'Wide (42/62, 38/68, 2.5)', 'rsi_low': 42, 'rsi_high': 62, 'stoch_low': 38, 'stoch_high': 68, 'ftfc_threshold': 2.5},
    ]

    print("\n" + "=" * 70)
    print("RESULTATS DES TESTS")
    print("=" * 70)

    results = []

    for config in configs:
        print(f"\nTesting: {config['name']}...")
        result = evaluate_config(all_data, config)
        if result:
            result['name'] = config['name']
            result['config'] = config
            results.append(result)

            trades_ok = "OK" if result['trades_per_day'] >= 60 else "FAIL"
            pnl_ok = "OK" if result['months_under_10k'] == 0 else "FAIL"

            print(f"  Trades/jour: {result['trades_per_day']:.0f} [{trades_ok}]")
            print(f"  Win Rate: {result['wr']:.1f}%")
            print(f"  PnL/Mois: ${result['pnl_per_month']:,.0f}")
            print(f"  Mois < $10k: {result['months_under_10k']} [{pnl_ok}]")

    # Summary table
    print("\n" + "=" * 70)
    print("TABLEAU COMPARATIF")
    print("=" * 70)

    print(f"\n{'Config':<28} {'T/J':>6} {'WR':>7} {'PnL/M':>10} {'<10k':>5} {'Status':>8}")
    print("-" * 70)

    for r in results:
        trades_ok = r['trades_per_day'] >= 60
        pnl_ok = r['months_under_10k'] == 0
        status = "VALID" if trades_ok and pnl_ok else ""

        print(f"{r['name']:<28} {r['trades_per_day']:>6.0f} {r['wr']:>6.1f}% ${r['pnl_per_month']:>8,.0f} {r['months_under_10k']:>5} {status:>8}")

    # Find valid configurations
    valid = [r for r in results if r['trades_per_day'] >= 60 and r['months_under_10k'] == 0]

    if valid:
        print("\n" + "=" * 70)
        print("CONFIGURATIONS VALIDES (60+ T/J ET 0 mois < $10k)")
        print("=" * 70)

        valid.sort(key=lambda x: x['pnl'], reverse=True)

        for r in valid:
            print(f"\n>>> {r['name']} <<<")
            print(f"  Trades/jour: {r['trades_per_day']:.0f}")
            print(f"  Win Rate: {r['wr']:.1f}%")
            print(f"  PnL Total: ${r['pnl']:,.0f}")
            print(f"  PnL/Mois: ${r['pnl_per_month']:,.0f}")
            print(f"  Min Mois: ${r['min_month_pnl']:,.0f}")
            print(f"  Config: RSI {r['config']['rsi_low']}/{r['config']['rsi_high']}, Stoch {r['config']['stoch_low']}/{r['config']['stoch_high']}, FTFC {r['config']['ftfc_threshold']}")
    else:
        print("\n" + "=" * 70)
        print("AUCUNE CONFIGURATION NE REPOND AUX DEUX CRITERES")
        print("=" * 70)

        # Find best trade-offs
        print("\nMeilleures options:")

        # Best trades with few bad months
        best_trades = [r for r in results if r['months_under_10k'] <= 2]
        if best_trades:
            best_trades.sort(key=lambda x: x['trades_per_day'], reverse=True)
            b = best_trades[0]
            print(f"\n1. Plus de trades ({b['trades_per_day']:.0f}/j) avec peu de mois faibles ({b['months_under_10k']}): {b['name']}")

        # Best PnL consistency
        best_pnl = sorted(results, key=lambda x: (x['months_under_10k'], -x['trades_per_day']))[0]
        print(f"\n2. Meilleure consistance ({best_pnl['months_under_10k']} mois < $10k): {best_pnl['name']}")
        print(f"   Trades/jour: {best_pnl['trades_per_day']:.0f}")

        # Closest to meeting both criteria
        print("\n3. Plus proche des 2 criteres:")
        for r in results:
            if r['trades_per_day'] >= 55 and r['months_under_10k'] <= 1:
                print(f"   {r['name']}: {r['trades_per_day']:.0f} T/J, {r['months_under_10k']} mois < $10k")

if __name__ == "__main__":
    main()
