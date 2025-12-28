#!/usr/bin/env python3
"""
Optimisation pour 60 trades/jour (20/pair)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

def download_data(exchange, symbol: str, days: int = 90) -> pd.DataFrame:
    """Télécharge données récentes"""
    print(f"  📥 {symbol}...", end=" ")

    all_data = []
    since = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break
            time.sleep(0.1)
        except:
            break

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['hour'] = df['datetime'].dt.hour
    print(f"{len(df)} bougies")
    return df

def calculate_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def backtest_config(df: pd.DataFrame, rsi_low: int, rsi_high: int,
                    consec: int, momentum: float, blocked_hours: list) -> dict:
    """Test une configuration"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])

    # Consecutive candles
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    # Momentum
    df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

    # Blocked hours
    df['blocked'] = df['hour'].isin(blocked_hours)

    # Signals
    df['signal_up'] = (
        ((df['consec_down'] >= consec) | (df['rsi'] < rsi_low)) &
        (df['momentum'] < -momentum) &
        (~df['blocked'])
    )
    df['signal_down'] = (
        ((df['consec_up'] >= consec) | (df['rsi'] > rsi_high)) &
        (df['momentum'] > momentum) &
        (~df['blocked'])
    )

    # Simulate trades with cooldown
    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:
            continue

        if df.iloc[i]['signal_up']:
            win = df.iloc[i+1]['close'] > df.iloc[i+1]['open']
            trades.append({'signal': 'UP', 'win': win})
            last_idx = i
        elif df.iloc[i]['signal_down']:
            win = df.iloc[i+1]['close'] < df.iloc[i+1]['open']
            trades.append({'signal': 'DOWN', 'win': win})
            last_idx = i

    if not trades:
        return {'trades': 0, 'wr': 0, 'tpd': 0}

    wins = sum(1 for t in trades if t['win'])
    days = (df['datetime'].max() - df['datetime'].min()).days or 1

    return {
        'trades': len(trades),
        'wins': wins,
        'wr': wins / len(trades) * 100,
        'tpd': len(trades) / days
    }

def main():
    print("=" * 70)
    print("🔧 OPTIMISATION POUR 60 TRADES/JOUR")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    # Télécharger données (90 jours)
    print("\n📥 Téléchargement données (90 jours)...")
    data = {}
    for symbol in symbols:
        data[symbol] = download_data(exchange, symbol, 90)

    # Configurations à tester
    configs = [
        # (rsi_low, rsi_high, consec, momentum, blocked_hours, name)
        (25, 75, 5, 0.2, [3,7,15,18,19,20], "Actuelle (strict)"),
        (30, 70, 4, 0.15, [3,7,15,18,19,20], "Medium"),
        (30, 70, 3, 0.1, [3,7,15,18,19,20], "Relaxed"),
        (32, 68, 3, 0.1, [], "Relaxed + No blocked"),
        (35, 65, 3, 0.05, [], "Very relaxed"),
        (35, 65, 2, 0.05, [], "Ultra relaxed"),
        (30, 70, 3, 0.0, [], "No momentum filter"),
        (33, 67, 3, 0.08, [], "Balanced 60tpd"),
        (32, 68, 2, 0.1, [], "Consec=2 focus"),
        (35, 65, 3, 0.0, [], "Max trades"),
    ]

    print("\n" + "=" * 70)
    print(f"{'Config':<25} {'BTC':<12} {'ETH':<12} {'XRP':<12} {'Total TPD':<12} {'Avg WR':<10}")
    print("=" * 70)

    best_config = None
    best_score = 0

    for rsi_low, rsi_high, consec, mom, blocked, name in configs:
        results = []
        for symbol in symbols:
            r = backtest_config(data[symbol], rsi_low, rsi_high, consec, mom, blocked)
            results.append(r)

        total_tpd = sum(r['tpd'] for r in results)
        avg_wr = sum(r['wr'] for r in results) / 3

        btc_str = f"{results[0]['tpd']:.1f}/j {results[0]['wr']:.0f}%"
        eth_str = f"{results[1]['tpd']:.1f}/j {results[1]['wr']:.0f}%"
        xrp_str = f"{results[2]['tpd']:.1f}/j {results[2]['wr']:.0f}%"

        print(f"{name:<25} {btc_str:<12} {eth_str:<12} {xrp_str:<12} {total_tpd:<12.1f} {avg_wr:.1f}%")

        # Score: proche de 60 TPD avec WR > 53%
        if avg_wr >= 53:
            score = min(total_tpd, 60) - abs(total_tpd - 60) * 0.5
            if score > best_score:
                best_score = score
                best_config = (rsi_low, rsi_high, consec, mom, blocked, name, total_tpd, avg_wr)

    print("=" * 70)

    if best_config:
        rsi_low, rsi_high, consec, mom, blocked, name, tpd, wr = best_config
        print(f"\n🎯 MEILLEURE CONFIG POUR ~60 TRADES/JOUR:")
        print(f"   Nom: {name}")
        print(f"   RSI: {rsi_low}/{rsi_high}")
        print(f"   Consécutives: {consec}")
        print(f"   Momentum: {mom}%")
        print(f"   Heures bloquées: {blocked if blocked else 'Aucune'}")
        print(f"   → {tpd:.1f} trades/jour | {wr:.1f}% Win Rate")

    # Test config personnalisée pour 60 trades
    print("\n" + "=" * 70)
    print("🔬 TEST CONFIG PERSONNALISÉE POUR 60 TPD")
    print("=" * 70)

    # Fine-tuning pour exactement ~60 trades/jour
    custom_configs = [
        (33, 67, 2, 0.08, [], "Custom A"),
        (34, 66, 2, 0.05, [], "Custom B"),
        (32, 68, 2, 0.05, [], "Custom C"),
        (33, 67, 2, 0.0, [], "Custom D (no mom)"),
        (30, 70, 2, 0.1, [], "Custom E"),
        (32, 68, 3, 0.0, [], "Custom F"),
    ]

    for rsi_low, rsi_high, consec, mom, blocked, name in custom_configs:
        results = []
        for symbol in symbols:
            r = backtest_config(data[symbol], rsi_low, rsi_high, consec, mom, blocked)
            results.append(r)

        total_tpd = sum(r['tpd'] for r in results)
        avg_wr = sum(r['wr'] for r in results) / 3

        print(f"{name}: RSI {rsi_low}/{rsi_high}, Consec={consec}, Mom={mom}%")
        print(f"   BTC: {results[0]['tpd']:.1f}/j ({results[0]['wr']:.1f}%)")
        print(f"   ETH: {results[1]['tpd']:.1f}/j ({results[1]['wr']:.1f}%)")
        print(f"   XRP: {results[2]['tpd']:.1f}/j ({results[2]['wr']:.1f}%)")
        print(f"   TOTAL: {total_tpd:.1f}/jour | WR: {avg_wr:.1f}%")
        print()

if __name__ == "__main__":
    main()
