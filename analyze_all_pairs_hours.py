#!/usr/bin/env python3
"""
Analyse des heures faibles pour chaque pair
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

SYMBOL_CONFIG = {
    'BTC': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
    'ETH': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
    'XRP': {'rsi_period': 5, 'rsi_oversold': 25, 'rsi_overbought': 75, 'stoch_period': 5, 'stoch_oversold': 20, 'stoch_overbought': 80, 'consec_threshold': 2},
    'SOL': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
}


def download_data(exchange, symbol: str, years: list) -> pd.DataFrame:
    all_data = []
    for year in years:
        print(f"  📥 {symbol} {year}...", end=" ", flush=True)
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) if year == 2025 else datetime(year, 12, 31, 23, 59, tzinfo=timezone.utc)

        since = int(start.timestamp() * 1000)
        end_ts = int(end.timestamp() * 1000)

        while since < end_ts:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
                if not ohlcv:
                    break
                all_data.extend(ohlcv)
                since = ohlcv[-1][0] + 1
                time.sleep(0.1)
            except:
                time.sleep(1)
                continue
        print("✅")

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset=['timestamp'])
    return df


def calculate_rsi(closes: pd.Series, period: int) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_stochastic(df: pd.DataFrame, period: int) -> pd.Series:
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)


def count_consecutive(df: pd.DataFrame) -> tuple:
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    consec_up = is_up.groupby(up_groups).cumsum()
    consec_down = is_down.groupby(down_groups).cumsum()
    return consec_up, consec_down


def analyze_pair(df, symbol):
    if df is None or len(df) < 50:
        return []

    base = symbol.split('/')[0]
    cfg = SYMBOL_CONFIG.get(base, SYMBOL_CONFIG['BTC'])

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], cfg['rsi_period'])
    df['stoch'] = calculate_stochastic(df, cfg['stoch_period'])
    df['consec_up'], df['consec_down'] = count_consecutive(df)
    df['hour'] = df['datetime'].dt.hour

    up_signal = (df['rsi'] < cfg['rsi_oversold']) & (df['stoch'] < cfg['stoch_oversold'])
    down_signal = (df['rsi'] > cfg['rsi_overbought']) & (df['stoch'] > cfg['stoch_overbought'])

    if cfg['consec_threshold'] > 1:
        up_signal = up_signal & (df['consec_down'] >= cfg['consec_threshold'])
        down_signal = down_signal & (df['consec_up'] >= cfg['consec_threshold'])

    df['signal_up'] = up_signal
    df['signal_down'] = down_signal

    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:
            continue

        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if row['signal_up']:
            win = next_row['close'] > next_row['open']
            trades.append({'hour': row['hour'], 'win': win})
            last_idx = i
        elif row['signal_down']:
            win = next_row['close'] < next_row['open']
            trades.append({'hour': row['hour'], 'win': win})
            last_idx = i

    return trades


def main():
    print("=" * 70)
    print("📊 ANALYSE HEURES FAIBLES PAR PAIR")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']

    results = {}

    for symbol in symbols:
        base = symbol.split('/')[0]
        print(f"\n🪙 {base}")
        df = download_data(exchange, symbol, [2024, 2025])
        trades = analyze_pair(df, symbol)

        if trades:
            trades_df = pd.DataFrame(trades)
            total_wr = trades_df['win'].sum() / len(trades_df) * 100

            # Analyse par heure
            hour_stats = trades_df.groupby('hour').agg({'win': ['sum', 'count']})
            hour_stats.columns = ['wins', 'total']
            hour_stats['wr'] = (hour_stats['wins'] / hour_stats['total'] * 100).round(1)
            hour_stats = hour_stats.sort_values('wr')

            print(f"\n   Total: {len(trades)} trades | WR Global: {total_wr:.1f}%")
            print(f"\n   {'Heure':<8} {'Trades':<8} {'WR':<8} {'Status'}")
            print("   " + "-" * 40)

            bad_hours = []
            good_hours = []
            for hour in range(24):
                if hour in hour_stats.index:
                    row = hour_stats.loc[hour]
                    wr = row['wr']
                    if wr < 53:
                        status = "🔴 BLACKLIST"
                        bad_hours.append(hour)
                    elif wr < 55:
                        status = "🟡"
                    else:
                        status = "🟢"
                        good_hours.append(hour)
                    print(f"   {hour:02d}:00    {int(row['total']):<8} {wr:.1f}%    {status}")

            results[base] = {
                'total': len(trades),
                'wr': total_wr,
                'bad_hours': sorted(bad_hours),
                'good_hours': sorted(good_hours)
            }

    # Résumé
    print("\n" + "=" * 70)
    print("📋 RÉSUMÉ BLACKLIST RECOMMANDÉES")
    print("=" * 70)

    for base, data in results.items():
        bad = data['bad_hours']
        print(f"\n{base}:")
        print(f"   WR Global: {data['wr']:.1f}%")
        print(f"   Heures faibles (WR < 53%): {bad if bad else 'Aucune'}")
        print(f"   Nb heures à bloquer: {len(bad)}")

        # Calcul impact
        if bad:
            # Estimation trades perdus
            trades_lost_pct = len(bad) / 24 * 100
            print(f"   Impact: -{trades_lost_pct:.0f}% trades")

    # Config finale
    print("\n" + "=" * 70)
    print("⚙️ CONFIG RECOMMANDÉE POUR bot_simple.py")
    print("=" * 70)

    for base, data in results.items():
        bad = data['bad_hours']
        print(f"\n'{base}': {{'blocked_hours': {bad}}},")


if __name__ == "__main__":
    main()
