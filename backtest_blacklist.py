#!/usr/bin/env python3
"""
Backtest avec blacklists par pair - Config identique à bot_simple.py
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

# CONFIG IDENTIQUE À bot_simple.py
SYMBOL_CONFIG = {
    'BTC': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'blocked_hours': [4, 14, 15],
    },
    'ETH': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'blocked_hours': [0, 6, 7, 14, 23],
    },
    'XRP': {
        'rsi_period': 5,
        'rsi_oversold': 25,
        'rsi_overbought': 75,
        'stoch_period': 5,
        'stoch_oversold': 20,
        'stoch_overbought': 80,
        'consec_threshold': 2,
        'blocked_hours': [1, 4, 7, 13, 16, 18, 19, 21],
    },
    'SOL': {
        'rsi_period': 7,
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_period': 5,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'blocked_hours': [0, 1, 4, 5, 6, 7, 8, 14, 15, 17, 19, 22, 23],
    }
}

ENTRY_PRICE = 0.53
SHARES = 5


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


def backtest(df: pd.DataFrame, symbol: str) -> dict:
    if df is None or len(df) < 50:
        return None

    base = symbol.split('/')[0]
    cfg = SYMBOL_CONFIG.get(base)

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], cfg['rsi_period'])
    df['stoch'] = calculate_stochastic(df, cfg['stoch_period'])
    df['consec_up'], df['consec_down'] = count_consecutive(df)
    df['hour'] = df['datetime'].dt.hour

    # Signaux avec blacklist
    blocked = cfg['blocked_hours']

    up_signal = (
        (df['rsi'] < cfg['rsi_oversold']) &
        (df['stoch'] < cfg['stoch_oversold']) &
        (~df['hour'].isin(blocked))
    )
    down_signal = (
        (df['rsi'] > cfg['rsi_overbought']) &
        (df['stoch'] > cfg['stoch_overbought']) &
        (~df['hour'].isin(blocked))
    )

    if cfg['consec_threshold'] > 1:
        up_signal = up_signal & (df['consec_down'] >= cfg['consec_threshold'])
        down_signal = down_signal & (df['consec_up'] >= cfg['consec_threshold'])

    df['signal_up'] = up_signal
    df['signal_down'] = down_signal

    # Simuler trades
    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:
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

    # PnL @ 53¢
    bet_cost = SHARES * ENTRY_PRICE
    potential_win = SHARES - bet_cost
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
        'days': days
    }


def main():
    print("=" * 70)
    print(f"📊 BACKTEST 4 PAIRS + BLACKLIST @ {ENTRY_PRICE*100:.0f}¢")
    print("=" * 70)
    print("Blacklists:")
    for sym, cfg in SYMBOL_CONFIG.items():
        print(f"  {sym}: {cfg['blocked_hours']}")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']
    years = [2024, 2025]

    results = {'2024': {}, '2025': {}}
    all_results = []

    for year in years:
        print(f"\n📅 {year}")
        print("-" * 40)

        year_trades = 0
        year_wins = 0
        year_pnl = 0

        for symbol in symbols:
            df = download_data(exchange, symbol, year)
            result = backtest(df, symbol)

            if result:
                base = result['symbol']
                results[str(year)][base] = result
                all_results.append({**result, 'year': year})

                year_trades += result['total']
                year_wins += result['wins']
                year_pnl += result['pnl']

                print(f"  {base}: {result['total']} trades | {result['trades_per_day']:.1f}/j | WR {result['win_rate']:.1f}% | PnL ${result['pnl']:+.2f}")

        if year_trades > 0:
            year_wr = year_wins / year_trades * 100
            year_tpd = year_trades / 365
            print(f"\n  📊 TOTAL {year}: {year_trades} trades ({year_tpd:.1f}/j) | WR {year_wr:.1f}% | PnL ${year_pnl:+.2f}")

    # Résumé global
    total_trades = sum(r['total'] for r in all_results)
    total_wins = sum(r['wins'] for r in all_results)
    total_pnl = sum(r['pnl'] for r in all_results)
    global_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
    global_tpd = total_trades / 730

    print("\n" + "=" * 70)
    print(f"🎯 RÉSUMÉ GLOBAL 2024-2025 @ {ENTRY_PRICE*100:.0f}¢ + BLACKLIST")
    print("=" * 70)

    # Par pair
    for sym in ['BTC', 'ETH', 'XRP', 'SOL']:
        sym_results = [r for r in all_results if r['symbol'] == sym]
        if sym_results:
            sym_trades = sum(r['total'] for r in sym_results)
            sym_wins = sum(r['wins'] for r in sym_results)
            sym_pnl = sum(r['pnl'] for r in sym_results)
            sym_wr = sym_wins / sym_trades * 100
            sym_tpd = sym_trades / 730
            blocked = len(SYMBOL_CONFIG[sym]['blocked_hours'])
            print(f"  {sym}: {sym_trades} trades ({sym_tpd:.1f}/j) | WR {sym_wr:.1f}% | PnL ${sym_pnl:+.2f} | Blacklist {blocked}h")

    print(f"\n  {'='*60}")
    print(f"  TOTAL: {total_trades} trades ({global_tpd:.1f}/jour)")
    print(f"  Win Rate: {global_wr:.1f}%")
    print(f"  PnL Total: ${total_pnl:+.2f}")
    print(f"  Coût/trade: ${SHARES * ENTRY_PRICE:.2f}")
    print(f"  Gain/win: ${SHARES - SHARES * ENTRY_PRICE:.2f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
