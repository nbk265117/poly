#!/usr/bin/env python3
"""
Test avec SOL comme 4ème pair
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

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


def backtest(df, symbol, config, blocked_hours=[]):
    if df is None or len(df) < 50:
        return []

    base = symbol.split('/')[0]
    cfg = config.get(base, config['BTC'])

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

    if blocked_hours:
        mask = ~df['hour'].isin(blocked_hours)
        up_signal = up_signal & mask
        down_signal = down_signal & mask

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
            trades.append({'symbol': base, 'win': win, 'hour': row['hour']})
            last_idx = i
        elif row['signal_down']:
            win = next_row['close'] < next_row['open']
            trades.append({'symbol': base, 'win': win, 'hour': row['hour']})
            last_idx = i

    return trades


def main():
    print("=" * 70)
    print("📊 TEST AVEC 4 PAIRS (BTC, ETH, XRP, SOL)")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']

    # Download
    df_dict = {}
    for symbol in symbols:
        df_dict[symbol] = download_data(exchange, symbol, [2024, 2025])

    # Config actuelle + SOL
    config = {
        'BTC': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
        'ETH': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
        'XRP': {'rsi_period': 5, 'rsi_oversold': 25, 'rsi_overbought': 75, 'stoch_period': 5, 'stoch_oversold': 20, 'stoch_overbought': 80, 'consec_threshold': 2},
        'SOL': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
    }

    print("\n" + "=" * 70)
    print("📊 RÉSULTATS PAR PAIR (Config actuelle)")
    print("=" * 70)

    all_trades = []
    for symbol in symbols:
        trades = backtest(df_dict[symbol], symbol, config)
        all_trades.extend(trades)

        if trades:
            wins = sum(1 for t in trades if t['win'])
            wr = wins / len(trades) * 100
            tpd = len(trades) / 730
            print(f"\n{symbol.split('/')[0]}:")
            print(f"  Trades: {len(trades)} ({tpd:.1f}/jour)")
            print(f"  Win Rate: {wr:.1f}%")

    trades_df = pd.DataFrame(all_trades)
    total = len(trades_df)
    wins = trades_df['win'].sum()
    wr = wins / total * 100
    tpd = total / 730

    print(f"\n{'='*70}")
    print(f"🎯 TOTAL 4 PAIRS: {total} trades ({tpd:.1f}/jour) | WR {wr:.1f}%")
    print("=" * 70)

    # Avec blacklist heures faibles
    print("\n📊 AVEC BLACKLIST HEURES (4, 7, 19 UTC)")
    print("-" * 50)

    all_trades_filtered = []
    for symbol in symbols:
        trades = backtest(df_dict[symbol], symbol, config, blocked_hours=[4, 7, 19])
        all_trades_filtered.extend(trades)

    if all_trades_filtered:
        trades_df = pd.DataFrame(all_trades_filtered)
        total = len(trades_df)
        wins = trades_df['win'].sum()
        wr = wins / total * 100
        tpd = total / 730
        print(f"  TOTAL: {total} trades ({tpd:.1f}/jour) | WR {wr:.1f}%")

    # Analyse par heure pour SOL
    print("\n⏰ WIN RATE SOL PAR HEURE")
    print("-" * 50)
    sol_trades = [t for t in all_trades if t['symbol'] == 'SOL']
    if sol_trades:
        sol_df = pd.DataFrame(sol_trades)
        hour_stats = sol_df.groupby('hour').agg({'win': ['sum', 'count']})
        hour_stats.columns = ['wins', 'total']
        hour_stats['wr'] = (hour_stats['wins'] / hour_stats['total'] * 100).round(1)
        hour_stats = hour_stats.sort_values('wr')

        bad_hours = []
        for hour in hour_stats.index:
            row = hour_stats.loc[hour]
            if row['wr'] < 53:
                bad_hours.append(int(hour))

        print(f"Heures faibles SOL (WR < 53%): {bad_hours}")


if __name__ == "__main__":
    main()
