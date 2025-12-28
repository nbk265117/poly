#!/usr/bin/env python3
"""
Trouver la meilleure config pour 60+ trades/jour avec WR max
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


def test_config(df_dict, config, blocked_hours=[], blocked_days=[]):
    """Test une config sur toutes les pairs"""
    all_trades = []

    for symbol, df in df_dict.items():
        if df is None or len(df) < 50:
            continue

        base = symbol.split('/')[0]
        cfg = config.get(base, config['BTC'])

        df = df.copy()
        df['rsi'] = calculate_rsi(df['close'], cfg['rsi_period'])
        df['stoch'] = calculate_stochastic(df, cfg['stoch_period'])
        df['consec_up'], df['consec_down'] = count_consecutive(df)
        df['hour'] = df['datetime'].dt.hour
        df['dayofweek'] = df['datetime'].dt.dayofweek

        # Signaux
        up_signal = (df['rsi'] < cfg['rsi_oversold']) & (df['stoch'] < cfg['stoch_oversold'])
        down_signal = (df['rsi'] > cfg['rsi_overbought']) & (df['stoch'] > cfg['stoch_overbought'])

        if cfg['consec_threshold'] > 1:
            up_signal = up_signal & (df['consec_down'] >= cfg['consec_threshold'])
            down_signal = down_signal & (df['consec_up'] >= cfg['consec_threshold'])

        # Blacklist
        if blocked_hours:
            mask = ~df['hour'].isin(blocked_hours)
            up_signal = up_signal & mask
            down_signal = down_signal & mask
        if blocked_days:
            mask = ~df['dayofweek'].isin(blocked_days)
            up_signal = up_signal & mask
            down_signal = down_signal & mask

        df['signal_up'] = up_signal
        df['signal_down'] = down_signal

        last_idx = -4
        for i in range(20, len(df) - 1):
            if i - last_idx < 4:
                continue

            row = df.iloc[i]
            next_row = df.iloc[i + 1]

            if row['signal_up']:
                win = next_row['close'] > next_row['open']
                all_trades.append({'symbol': base, 'win': win})
                last_idx = i
            elif row['signal_down']:
                win = next_row['close'] < next_row['open']
                all_trades.append({'symbol': base, 'win': win})
                last_idx = i

    if not all_trades:
        return 0, 0, 0

    trades_df = pd.DataFrame(all_trades)
    total = len(trades_df)
    wins = trades_df['win'].sum()
    wr = wins / total * 100
    tpd = total / 730  # ~2 years

    return total, tpd, wr


def main():
    print("=" * 70)
    print("🔍 RECHERCHE CONFIG OPTIMALE: 60+ trades/jour, WR max")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    # Download data
    df_dict = {}
    for symbol in symbols:
        df_dict[symbol] = download_data(exchange, symbol, [2024, 2025])

    # Configs à tester
    configs = [
        {
            'name': 'ACTUEL (35/65 + 30/70)',
            'config': {
                'BTC': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
                'ETH': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec_threshold': 1},
                'XRP': {'rsi_period': 5, 'rsi_oversold': 25, 'rsi_overbought': 75, 'stoch_period': 5, 'stoch_oversold': 20, 'stoch_overbought': 80, 'consec_threshold': 2},
            }
        },
        {
            'name': 'ÉLARGI (40/60 + 35/65)',
            'config': {
                'BTC': {'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 60, 'stoch_period': 5, 'stoch_oversold': 35, 'stoch_overbought': 65, 'consec_threshold': 1},
                'ETH': {'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 60, 'stoch_period': 5, 'stoch_oversold': 35, 'stoch_overbought': 65, 'consec_threshold': 1},
                'XRP': {'rsi_period': 5, 'rsi_oversold': 30, 'rsi_overbought': 70, 'stoch_period': 5, 'stoch_oversold': 25, 'stoch_overbought': 75, 'consec_threshold': 2},
            }
        },
        {
            'name': 'TRÈS ÉLARGI (42/58 + 38/62)',
            'config': {
                'BTC': {'rsi_period': 7, 'rsi_oversold': 42, 'rsi_overbought': 58, 'stoch_period': 5, 'stoch_oversold': 38, 'stoch_overbought': 62, 'consec_threshold': 1},
                'ETH': {'rsi_period': 7, 'rsi_oversold': 42, 'rsi_overbought': 58, 'stoch_period': 5, 'stoch_oversold': 38, 'stoch_overbought': 62, 'consec_threshold': 1},
                'XRP': {'rsi_period': 5, 'rsi_oversold': 32, 'rsi_overbought': 68, 'stoch_period': 5, 'stoch_oversold': 28, 'stoch_overbought': 72, 'consec_threshold': 2},
            }
        },
        {
            'name': 'RSI SEUL (40/60, pas de Stoch)',
            'config': {
                'BTC': {'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 60, 'stoch_period': 5, 'stoch_oversold': 0, 'stoch_overbought': 100, 'consec_threshold': 1},
                'ETH': {'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 60, 'stoch_period': 5, 'stoch_oversold': 0, 'stoch_overbought': 100, 'consec_threshold': 1},
                'XRP': {'rsi_period': 5, 'rsi_oversold': 30, 'rsi_overbought': 70, 'stoch_period': 5, 'stoch_oversold': 0, 'stoch_overbought': 100, 'consec_threshold': 1},
            }
        },
    ]

    # Blacklist options
    blacklists = [
        {'name': 'Sans blacklist', 'hours': [], 'days': []},
        {'name': 'Heures faibles (4,7,19)', 'hours': [4, 7, 19], 'days': []},
        {'name': 'Heures matin (0-6)', 'hours': [0, 1, 2, 3, 4, 5, 6], 'days': []},
        {'name': 'Weekend seul', 'hours': [], 'days': [0, 1, 2, 3, 4]},  # Only Sat/Sun
        {'name': 'Lundi+Vendredi blacklist', 'hours': [], 'days': [0, 4]},
    ]

    print("\n📊 TEST DES CONFIGURATIONS")
    print("=" * 70)

    results = []

    for cfg_item in configs:
        print(f"\n🔧 {cfg_item['name']}")
        print("-" * 50)

        for bl in blacklists:
            total, tpd, wr = test_config(df_dict, cfg_item['config'], bl['hours'], bl['days'])
            status = "✅" if tpd >= 60 and wr >= 55 else ("🟡" if tpd >= 50 else "❌")
            print(f"  {bl['name']:<30} {tpd:>5.1f}/j  WR {wr:>5.1f}%  {status}")

            results.append({
                'config': cfg_item['name'],
                'blacklist': bl['name'],
                'tpd': tpd,
                'wr': wr,
                'total': total
            })

    # Trouver la meilleure config
    print("\n" + "=" * 70)
    print("🏆 MEILLEURES CONFIGS (60+ trades/jour)")
    print("=" * 70)

    results_df = pd.DataFrame(results)
    good_results = results_df[results_df['tpd'] >= 60].sort_values('wr', ascending=False)

    if len(good_results) > 0:
        for _, row in good_results.head(5).iterrows():
            print(f"\n  {row['config']} + {row['blacklist']}")
            print(f"    → {row['tpd']:.1f} trades/jour | WR {row['wr']:.1f}%")
    else:
        print("\n  ❌ Aucune config atteint 60 trades/jour avec les filtres actuels")
        print("\n  Meilleures alternatives:")
        best = results_df.sort_values('tpd', ascending=False).head(3)
        for _, row in best.iterrows():
            print(f"    {row['config']} + {row['blacklist']}: {row['tpd']:.1f}/j, WR {row['wr']:.1f}%")


if __name__ == "__main__":
    main()
