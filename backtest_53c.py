#!/usr/bin/env python3
"""
Backtest avec prix entrée 53¢ - Stratégie HYBRID
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import json

# CONFIG HYBRIDE (même que bot_simple.py)
SYMBOL_CONFIG = {
    'BTC': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
    },
    'ETH': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
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

ENTRY_PRICE = 0.53  # 53 centimes
SHARES = 5


def download_data(exchange, symbol: str, year: int) -> pd.DataFrame:
    """Télécharge les données 15m pour une année"""
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
        except Exception as e:
            time.sleep(1)
            continue

    if not all_data:
        print("❌")
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset=['timestamp'])
    print(f"✅ {len(df)} bougies")
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


def backtest(df: pd.DataFrame, symbol: str) -> dict:
    if df is None or len(df) < 50:
        return None

    base = symbol.split('/')[0]
    cfg = SYMBOL_CONFIG.get(base, SYMBOL_CONFIG['BTC'])

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], cfg['rsi_period'])
    df['stoch'] = calculate_stochastic(df, cfg['stoch_period'])
    df['consec_up'], df['consec_down'] = count_consecutive(df)

    # Signaux
    up_signal = (df['rsi'] < cfg['rsi_oversold']) & (df['stoch'] < cfg['stoch_oversold'])
    down_signal = (df['rsi'] > cfg['rsi_overbought']) & (df['stoch'] > cfg['stoch_overbought'])

    if cfg['consec_threshold'] > 1:
        up_signal = up_signal & (df['consec_down'] >= cfg['consec_threshold'])
        down_signal = down_signal & (df['consec_up'] >= cfg['consec_threshold'])

    df['signal_up'] = up_signal
    df['signal_down'] = down_signal

    # Simuler trades avec cooldown
    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:  # Cooldown 1h (4 bougies)
            continue

        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if row['signal_up']:
            win = next_row['close'] > next_row['open']
            trades.append({'signal': 'UP', 'win': win, 'datetime': row['datetime']})
            last_idx = i
        elif row['signal_down']:
            win = next_row['close'] < next_row['open']
            trades.append({'signal': 'DOWN', 'win': win, 'datetime': row['datetime']})
            last_idx = i

    if not trades:
        return None

    wins = sum(1 for t in trades if t['win'])
    total = len(trades)
    win_rate = wins / total * 100

    # PnL avec 53¢
    bet_cost = SHARES * ENTRY_PRICE  # $2.65
    potential_win = SHARES - bet_cost  # $2.35

    pnl = sum([potential_win if t['win'] else -bet_cost for t in trades])

    days = (df['datetime'].max() - df['datetime'].min()).days or 1

    return {
        'symbol': base,
        'total': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': round(win_rate, 1),
        'pnl': round(pnl, 2),
        'trades_per_day': round(total / days, 1),
        'days': days,
        'trades': trades
    }


def main():
    print("=" * 60)
    print(f"📊 BACKTEST HYBRID @ {ENTRY_PRICE*100:.0f}¢ ENTRY")
    print("=" * 60)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    years = [2024, 2025]

    results = {'years': {}, 'summary': {}, 'entry_price': ENTRY_PRICE}

    for year in years:
        print(f"\n📅 {year}")
        print("-" * 40)

        year_data = {'pairs': {}, 'total_trades': 0, 'total_wins': 0, 'total_pnl': 0}

        for symbol in symbols:
            df = download_data(exchange, symbol, year)
            result = backtest(df, symbol)

            if result:
                base = result['symbol']
                year_data['pairs'][base] = {
                    'trades': result['total'],
                    'win_rate': result['win_rate'],
                    'pnl': result['pnl'],
                    'tpd': result['trades_per_day']
                }
                year_data['total_trades'] += result['total']
                year_data['total_wins'] += result['wins']
                year_data['total_pnl'] += result['pnl']

                print(f"  {base}: {result['total']} trades | WR {result['win_rate']:.1f}% | PnL ${result['pnl']:+.2f}")

        if year_data['total_trades'] > 0:
            year_data['global_wr'] = round(year_data['total_wins'] / year_data['total_trades'] * 100, 1)
        else:
            year_data['global_wr'] = 0

        results['years'][str(year)] = year_data
        print(f"\n  📊 TOTAL {year}: {year_data['total_trades']} trades | WR {year_data['global_wr']:.1f}% | PnL ${year_data['total_pnl']:+.2f}")

    # Summary
    all_trades = sum(y['total_trades'] for y in results['years'].values())
    all_wins = sum(y['total_wins'] for y in results['years'].values())
    all_pnl = sum(y['total_pnl'] for y in results['years'].values())

    results['summary'] = {
        'total_trades': all_trades,
        'win_rate': round(all_wins / all_trades * 100, 1) if all_trades > 0 else 0,
        'total_pnl': round(all_pnl, 2),
        'entry_price': ENTRY_PRICE,
        'shares': SHARES,
        'bet_cost': round(SHARES * ENTRY_PRICE, 2),
        'potential_win': round(SHARES - SHARES * ENTRY_PRICE, 2)
    }

    print("\n" + "=" * 60)
    print(f"🎯 RÉSUMÉ GLOBAL (2024-2025) @ {ENTRY_PRICE*100:.0f}¢")
    print("=" * 60)
    print(f"  Trades: {all_trades}")
    print(f"  Win Rate: {results['summary']['win_rate']:.1f}%")
    print(f"  PnL Total: ${all_pnl:+.2f}")
    print(f"  Coût/trade: ${results['summary']['bet_cost']:.2f}")
    print(f"  Gain/trade: ${results['summary']['potential_win']:.2f}")
    print("=" * 60)

    # Save JSON for stats.html
    with open('docs/backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("\n✅ Résultats sauvegardés dans docs/backtest_results.json")

    return results


if __name__ == "__main__":
    main()
