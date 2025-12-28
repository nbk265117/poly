#!/usr/bin/env python3
"""
Trouve la meilleure config: max trades avec WR >= 55% par pair
"""
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

# Forcer le flush pour voir la sortie
import functools
print = functools.partial(print, flush=True)

def download_data(exchange, symbol: str, days: int = 60) -> pd.DataFrame:
    print(f"  📥 {symbol}...", end=" ")

    all_data = []
    since = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)

    retries = 0
    while since < end_ts and retries < 3:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            time.sleep(0.2)
            retries = 0
        except Exception as e:
            retries += 1
            print(f"retry {retries}...", end=" ")
            time.sleep(2)
            continue

    if not all_data:
        print("ERREUR")
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['hour'] = df['datetime'].dt.hour
    df = df.drop_duplicates(subset=['timestamp'])
    print(f"{len(df)} bougies")
    return df

def calculate_rsi(closes: pd.Series) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def test_config(df, rsi_low, rsi_high, consec, mom, blocked, cooldown):
    if df is None:
        return None

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])

    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()
    df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100
    df['blocked'] = df['hour'].isin(blocked)

    df['signal_up'] = (
        ((df['consec_down'] >= consec) | (df['rsi'] < rsi_low)) &
        (df['momentum'] < -mom) &
        (~df['blocked'])
    )
    df['signal_down'] = (
        ((df['consec_up'] >= consec) | (df['rsi'] > rsi_high)) &
        (df['momentum'] > mom) &
        (~df['blocked'])
    )

    trades = []
    last_idx = -cooldown

    for i in range(20, len(df) - 1):
        if i - last_idx < cooldown:
            continue
        if df.iloc[i]['signal_up']:
            win = df.iloc[i+1]['close'] > df.iloc[i+1]['open']
            trades.append(win)
            last_idx = i
        elif df.iloc[i]['signal_down']:
            win = df.iloc[i+1]['close'] < df.iloc[i+1]['open']
            trades.append(win)
            last_idx = i

    if not trades:
        return {'trades': 0, 'wr': 0, 'tpd': 0}

    days = (df['datetime'].max() - df['datetime'].min()).days or 1
    return {
        'trades': len(trades),
        'wr': sum(trades) / len(trades) * 100,
        'tpd': len(trades) / days
    }

def main():
    print("=" * 60)
    print("🎯 RECHERCHE: MAX TRADES AVEC WR >= 55%")
    print("=" * 60)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    print("\n📥 Téléchargement (60 jours)...")
    data = {}
    for sym in symbols:
        data[sym] = download_data(exchange, sym, 60)

    # Configs à tester (optimisées pour équilibre)
    configs = [
        # (rsi_low, rsi_high, consec, mom, blocked, cooldown)
        (25, 75, 5, 0.2, [3,7,15,18,19,20], 4),  # Actuelle
        (27, 73, 4, 0.15, [3,7,15,18,19,20], 4),
        (28, 72, 4, 0.1, [3,7,15,18,19,20], 4),
        (29, 71, 4, 0.1, [3,7], 4),
        (30, 70, 4, 0.1, [], 4),
        (30, 70, 3, 0.1, [], 4),
        (28, 72, 3, 0.1, [], 4),
        (27, 73, 3, 0.1, [], 4),
        (28, 72, 3, 0.1, [], 3),  # Cooldown réduit
        (27, 73, 3, 0.1, [], 3),
        (28, 72, 3, 0.15, [], 3),
        (29, 71, 3, 0.1, [], 3),
        (30, 70, 3, 0.15, [], 3),
        (28, 72, 4, 0.1, [], 3),
        (27, 73, 4, 0.1, [], 3),
        (28, 72, 3, 0.05, [], 3),
        (29, 71, 3, 0.05, [], 3),
        (30, 70, 3, 0.05, [], 3),
        (28, 72, 3, 0.1, [], 2),  # Cooldown=2
        (29, 71, 3, 0.1, [], 2),
        (30, 70, 3, 0.1, [], 2),
        (28, 72, 3, 0.15, [], 2),
        (29, 71, 4, 0.1, [], 2),
        (30, 70, 4, 0.1, [], 2),
    ]

    print(f"\n🔍 Test de {len(configs)} configurations...")
    print("=" * 60)

    valid_configs = []

    for cfg in configs:
        rsi_low, rsi_high, consec, mom, blocked, cooldown = cfg
        results = {}
        all_valid = True

        for sym in symbols:
            r = test_config(data[sym], rsi_low, rsi_high, consec, mom, blocked, cooldown)
            if r is None or r['wr'] < 55.0:
                all_valid = False
                break
            results[sym] = r

        if all_valid:
            total_tpd = sum(r['tpd'] for r in results.values())
            min_wr = min(r['wr'] for r in results.values())

            valid_configs.append({
                'config': cfg,
                'total_tpd': total_tpd,
                'min_wr': min_wr,
                'results': results
            })

    # Trier par trades/jour
    valid_configs.sort(key=lambda x: x['total_tpd'], reverse=True)

    print(f"\n✅ {len(valid_configs)} configs avec WR >= 55% pour chaque pair")
    print("=" * 60)

    for i, v in enumerate(valid_configs[:5]):
        cfg = v['config']
        print(f"\n#{i+1}: {v['total_tpd']:.1f} trades/jour | Min WR: {v['min_wr']:.1f}%")
        print(f"   RSI: {cfg[0]}/{cfg[1]} | Consec: {cfg[2]} | Mom: {cfg[3]}% | Blocked: {cfg[4]} | Cooldown: {cfg[5]}")
        for sym, r in v['results'].items():
            base = sym.split('/')[0]
            print(f"   {base}: {r['tpd']:.1f}/jour ({r['wr']:.1f}%)")

    if valid_configs:
        best = valid_configs[0]
        cfg = best['config']
        print("\n" + "=" * 60)
        print("🏆 MEILLEURE CONFIG:")
        print("=" * 60)
        print(f"""
# À mettre dans bot_simple.py:
RSI_OVERSOLD = {cfg[0]}
RSI_OVERBOUGHT = {cfg[1]}
CONSEC_THRESHOLD = {cfg[2]}
MIN_MOMENTUM = {cfg[3]}
BLOCKED_HOURS = {cfg[4]}
COOLDOWN_CANDLES = {cfg[5]}  # À ajouter

# Résultats:
# BTC: {best['results']['BTC/USDT']['tpd']:.1f}/jour ({best['results']['BTC/USDT']['wr']:.1f}%)
# ETH: {best['results']['ETH/USDT']['tpd']:.1f}/jour ({best['results']['ETH/USDT']['wr']:.1f}%)
# XRP: {best['results']['XRP/USDT']['tpd']:.1f}/jour ({best['results']['XRP/USDT']['wr']:.1f}%)
# TOTAL: {best['total_tpd']:.1f} trades/jour
""")
    else:
        print("\n❌ Impossible d'atteindre 55% WR pour chaque pair avec plus de trades")
        print("Le maximum est ~12 trades/jour avec la config actuelle")

if __name__ == "__main__":
    main()
