#!/usr/bin/env python3
"""
Analyse des heures et jours pour trouver les périodes faibles
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

# CONFIG ÉLARGIE (Option 1)
SYMBOL_CONFIG = {
    'BTC': {
        'rsi_period': 7,
        'rsi_oversold': 40,
        'rsi_overbought': 60,
        'stoch_period': 5,
        'stoch_oversold': 35,
        'stoch_overbought': 65,
        'consec_threshold': 1,
    },
    'ETH': {
        'rsi_period': 7,
        'rsi_oversold': 40,
        'rsi_overbought': 60,
        'stoch_period': 5,
        'stoch_oversold': 35,
        'stoch_overbought': 65,
        'consec_threshold': 1,
    },
    'XRP': {
        'rsi_period': 5,
        'rsi_oversold': 25,
        'rsi_overbought': 75,
        'stoch_period': 5,
        'stoch_oversold': 20,
        'stoch_overbought': 80,
        'consec_threshold': 2,
    }
}


def download_data(exchange, symbol: str, year: int) -> pd.DataFrame:
    print(f"  📥 {symbol} {year}...", end=" ", flush=True)
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) if year == 2025 else datetime(year, 12, 31, 23, 59, tzinfo=timezone.utc)

    all_data = []
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

    if not all_data:
        print("❌")
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset=['timestamp'])
    print(f"✅ {len(df)}")
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


def generate_trades(df: pd.DataFrame, symbol: str) -> list:
    if df is None or len(df) < 50:
        return []

    base = symbol.split('/')[0]
    cfg = SYMBOL_CONFIG.get(base, SYMBOL_CONFIG['BTC'])

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], cfg['rsi_period'])
    df['stoch'] = calculate_stochastic(df, cfg['stoch_period'])
    df['consec_up'], df['consec_down'] = count_consecutive(df)
    df['hour'] = df['datetime'].dt.hour
    df['dayofweek'] = df['datetime'].dt.dayofweek  # 0=Monday, 6=Sunday

    # Signaux
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
            trades.append({
                'symbol': base,
                'signal': 'UP',
                'win': win,
                'hour': row['hour'],
                'dayofweek': row['dayofweek'],
                'datetime': row['datetime']
            })
            last_idx = i
        elif row['signal_down']:
            win = next_row['close'] < next_row['open']
            trades.append({
                'symbol': base,
                'signal': 'DOWN',
                'win': win,
                'hour': row['hour'],
                'dayofweek': row['dayofweek'],
                'datetime': row['datetime']
            })
            last_idx = i

    return trades


def main():
    print("=" * 70)
    print("📊 ANALYSE HEURES & JOURS - CONFIG ÉLARGIE")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    years = [2024, 2025]

    all_trades = []

    for year in years:
        print(f"\n📅 {year}")
        for symbol in symbols:
            df = download_data(exchange, symbol, year)
            trades = generate_trades(df, symbol)
            all_trades.extend(trades)
            print(f"    {symbol.split('/')[0]}: {len(trades)} trades")

    trades_df = pd.DataFrame(all_trades)
    total_trades = len(trades_df)
    total_wins = trades_df['win'].sum()
    global_wr = total_wins / total_trades * 100

    print(f"\n{'='*70}")
    print(f"📊 TOTAL: {total_trades} trades | WR Global: {global_wr:.1f}%")
    print(f"{'='*70}")

    # Analyse par HEURE
    print("\n⏰ WIN RATE PAR HEURE (UTC)")
    print("-" * 50)
    hour_stats = trades_df.groupby('hour').agg({
        'win': ['sum', 'count']
    }).round(2)
    hour_stats.columns = ['wins', 'total']
    hour_stats['wr'] = (hour_stats['wins'] / hour_stats['total'] * 100).round(1)
    hour_stats = hour_stats.sort_values('wr')

    print(f"{'Heure':<8} {'Trades':<10} {'WR':<10} {'Status'}")
    print("-" * 50)

    bad_hours = []
    for hour in hour_stats.index:
        row = hour_stats.loc[hour]
        status = "🔴 BLACKLIST" if row['wr'] < 53 else ("🟡" if row['wr'] < 55 else "🟢")
        if row['wr'] < 53:
            bad_hours.append(int(hour))
        print(f"{int(hour):02d}:00    {int(row['total']):<10} {row['wr']:.1f}%     {status}")

    # Analyse par JOUR
    print("\n📅 WIN RATE PAR JOUR")
    print("-" * 50)
    days_name = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    day_stats = trades_df.groupby('dayofweek').agg({
        'win': ['sum', 'count']
    }).round(2)
    day_stats.columns = ['wins', 'total']
    day_stats['wr'] = (day_stats['wins'] / day_stats['total'] * 100).round(1)
    day_stats = day_stats.sort_values('wr')

    print(f"{'Jour':<12} {'Trades':<10} {'WR':<10} {'Status'}")
    print("-" * 50)

    bad_days = []
    for day in day_stats.index:
        row = day_stats.loc[day]
        status = "🔴 BLACKLIST" if row['wr'] < 53 else ("🟡" if row['wr'] < 55 else "🟢")
        if row['wr'] < 53:
            bad_days.append(int(day))
        print(f"{days_name[int(day)]:<12} {int(row['total']):<10} {row['wr']:.1f}%     {status}")

    # Analyse par PAIR
    print("\n🪙 WIN RATE PAR PAIR")
    print("-" * 50)
    for symbol in ['BTC', 'ETH', 'XRP']:
        sym_df = trades_df[trades_df['symbol'] == symbol]
        wr = sym_df['win'].sum() / len(sym_df) * 100
        tpd = len(sym_df) / 730  # ~2 years
        print(f"{symbol}: {len(sym_df)} trades | {tpd:.1f}/jour | WR {wr:.1f}%")

    # Résumé
    print("\n" + "=" * 70)
    print("📋 RECOMMANDATION BLACKLIST")
    print("=" * 70)
    print(f"\nHeures à bloquer (WR < 53%): {bad_hours if bad_hours else 'Aucune'}")
    print(f"Jours à bloquer (WR < 53%): {[days_name[d] for d in bad_days] if bad_days else 'Aucun'}")

    # Calcul avec blacklist
    if bad_hours or bad_days:
        filtered_df = trades_df[
            (~trades_df['hour'].isin(bad_hours)) &
            (~trades_df['dayofweek'].isin(bad_days))
        ]
        filtered_wr = filtered_df['win'].sum() / len(filtered_df) * 100
        filtered_tpd = len(filtered_df) / 730

        print(f"\n📈 AVEC BLACKLIST:")
        print(f"  Trades: {len(filtered_df)} ({filtered_tpd:.1f}/jour)")
        print(f"  Win Rate: {filtered_wr:.1f}% (vs {global_wr:.1f}% sans filtre)")
        print(f"  Amélioration: +{filtered_wr - global_wr:.1f}%")


if __name__ == "__main__":
    main()
