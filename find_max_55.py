#!/usr/bin/env python3
"""
Trouve le MAX de trades possible avec WR >= 55%
"""
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import functools
print = functools.partial(print, flush=True)

def download_data(exchange, symbol: str, days: int = 60) -> pd.DataFrame:
    print(f"  📥 {symbol}...", end=" ")
    all_data = []
    since = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv or len(ohlcv) == 0:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break
            time.sleep(0.15)
        except Exception as e:
            time.sleep(1)
            break

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df['hour'] = df['datetime'].dt.hour
    print(f"{len(df)} bougies")
    return df

def calculate_rsi(closes):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def test_config(df, rsi_low, rsi_high, consec, mom, blocked, cooldown):
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
            trades.append(df.iloc[i+1]['close'] > df.iloc[i+1]['open'])
            last_idx = i
        elif df.iloc[i]['signal_down']:
            trades.append(df.iloc[i+1]['close'] < df.iloc[i+1]['open'])
            last_idx = i

    if not trades:
        return {'trades': 0, 'wr': 0, 'tpd': 0}

    days = max(1, (df['datetime'].max() - df['datetime'].min()).days)
    return {'trades': len(trades), 'wr': sum(trades)/len(trades)*100, 'tpd': len(trades)/days}

def main():
    print("=" * 60)
    print("🎯 RECHERCHE EXHAUSTIVE: MAX TRADES + 55% WR")
    print("=" * 60)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    print("\n📥 Téléchargement...")
    data = {}
    for sym in symbols:
        data[sym] = download_data(exchange, sym, 60)

    # Test de la config actuelle
    print("\n📊 Config ACTUELLE (RSI 25/75, Consec 5, Mom 0.2%):")
    for sym in symbols:
        r = test_config(data[sym], 25, 75, 5, 0.2, [3,7,15,18,19,20], 4)
        print(f"   {sym.split('/')[0]}: {r['tpd']:.1f}/jour ({r['wr']:.1f}%)")

    # Grid search exhaustif
    print("\n🔍 Recherche exhaustive...")

    results_all = []

    for rsi_low in [24, 25, 26, 27, 28, 29, 30]:
        for rsi_high in [70, 71, 72, 73, 74, 75, 76]:
            for consec in [3, 4, 5]:
                for mom in [0.1, 0.15, 0.2, 0.25]:
                    for cooldown in [2, 3, 4]:
                        for blocked in [[], [3,7,15,18,19,20]]:

                            res = {}
                            all_ok = True
                            for sym in symbols:
                                r = test_config(data[sym], rsi_low, rsi_high, consec, mom, blocked, cooldown)
                                res[sym] = r
                                if r['wr'] < 55.0:
                                    all_ok = False
                                    break

                            if all_ok:
                                total_tpd = sum(r['tpd'] for r in res.values())
                                min_wr = min(r['wr'] for r in res.values())
                                results_all.append({
                                    'rsi_low': rsi_low, 'rsi_high': rsi_high,
                                    'consec': consec, 'mom': mom,
                                    'blocked': blocked, 'cooldown': cooldown,
                                    'total_tpd': total_tpd, 'min_wr': min_wr,
                                    'results': res
                                })

    results_all.sort(key=lambda x: x['total_tpd'], reverse=True)

    print(f"\n✅ {len(results_all)} configs valides trouvées (WR >= 55% par pair)")

    if results_all:
        print("\n🏆 TOP 5 CONFIGS:")
        print("=" * 60)

        for i, cfg in enumerate(results_all[:5]):
            print(f"\n#{i+1}: {cfg['total_tpd']:.1f} trades/jour")
            print(f"   RSI: {cfg['rsi_low']}/{cfg['rsi_high']} | Consec: {cfg['consec']} | Mom: {cfg['mom']}%")
            print(f"   Blocked: {cfg['blocked']} | Cooldown: {cfg['cooldown']}")
            for sym, r in cfg['results'].items():
                print(f"   {sym.split('/')[0]}: {r['tpd']:.1f}/j ({r['wr']:.1f}%)")

        best = results_all[0]
        print("\n" + "=" * 60)
        print("🎯 MEILLEURE CONFIG À APPLIQUER:")
        print("=" * 60)
        print(f"""
RSI_OVERSOLD = {best['rsi_low']}
RSI_OVERBOUGHT = {best['rsi_high']}
CONSEC_THRESHOLD = {best['consec']}
MIN_MOMENTUM = {best['mom']}
BLOCKED_HOURS = {best['blocked']}

# Résultats attendus:
# BTC: {best['results']['BTC/USDT']['tpd']:.1f}/jour ({best['results']['BTC/USDT']['wr']:.1f}%)
# ETH: {best['results']['ETH/USDT']['tpd']:.1f}/jour ({best['results']['ETH/USDT']['wr']:.1f}%)
# XRP: {best['results']['XRP/USDT']['tpd']:.1f}/jour ({best['results']['XRP/USDT']['wr']:.1f}%)
# TOTAL: {best['total_tpd']:.1f} trades/jour
""")
    else:
        print("\n❌ Aucune config avec WR >= 55% pour les 3 pairs")

        # Tester sans XRP
        print("\n🔄 Test avec seulement BTC + ETH...")
        for rsi_low in [28, 29, 30]:
            for rsi_high in [70, 71, 72]:
                for consec in [3, 4]:
                    for mom in [0.1, 0.15]:
                        for cooldown in [2, 3]:
                            btc = test_config(data['BTC/USDT'], rsi_low, rsi_high, consec, mom, [], cooldown)
                            eth = test_config(data['ETH/USDT'], rsi_low, rsi_high, consec, mom, [], cooldown)

                            if btc['wr'] >= 55 and eth['wr'] >= 55:
                                total = btc['tpd'] + eth['tpd']
                                if total > 30:  # Plus de 15/pair
                                    print(f"   RSI {rsi_low}/{rsi_high}, C={consec}, M={mom}, CD={cooldown}")
                                    print(f"   BTC: {btc['tpd']:.1f}/j ({btc['wr']:.1f}%) | ETH: {eth['tpd']:.1f}/j ({eth['wr']:.1f}%)")
                                    print(f"   Total: {total:.1f}/jour")

if __name__ == "__main__":
    main()
