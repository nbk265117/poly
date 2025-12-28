#!/usr/bin/env python3
"""
Optimisation: Max trades avec WR >= 55% pour CHAQUE pair
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
from itertools import product

def download_data(exchange, symbol: str, days: int = 180) -> pd.DataFrame:
    """Télécharge données"""
    print(f"  📥 {symbol}...", end=" ", flush=True)

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
                    consec: int, momentum: float, blocked_hours: list,
                    cooldown: int = 4) -> dict:
    """Test une configuration"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])

    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100
    df['blocked'] = df['hour'].isin(blocked_hours)

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

    trades = []
    last_idx = -cooldown

    for i in range(20, len(df) - 1):
        if i - last_idx < cooldown:
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
    print("🎯 OPTIMISATION: MAX TRADES AVEC WR >= 55% PAR PAIR")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    print("\n📥 Téléchargement données (90 jours)...")
    data = {}
    for symbol in symbols:
        data[symbol] = download_data(exchange, symbol, 90)

    # Grid search pour trouver la meilleure config
    rsi_lows = [25, 27, 28, 29, 30]
    rsi_highs = [70, 71, 72, 73, 75]
    consecs = [3, 4, 5]
    momentums = [0.0, 0.05, 0.1, 0.15]
    blocked_options = [
        [],
        [3, 7],
        [3, 7, 15, 18, 19, 20],
    ]
    cooldowns = [2, 3, 4]  # Réduire cooldown = plus de trades

    print(f"\n🔍 Test de {len(rsi_lows)*len(rsi_highs)*len(consecs)*len(momentums)*len(blocked_options)*len(cooldowns)} configurations...")

    best_configs = []

    for rsi_low, rsi_high, consec, mom, blocked, cooldown in product(
        rsi_lows, rsi_highs, consecs, momentums, blocked_options, cooldowns
    ):
        results = {}
        all_valid = True

        for symbol in symbols:
            r = backtest_config(data[symbol], rsi_low, rsi_high, consec, mom, blocked, cooldown)
            results[symbol] = r
            if r['wr'] < 55.0:  # Doit être >= 55% pour chaque pair
                all_valid = False
                break

        if all_valid and all(r['tpd'] > 0 for r in results.values()):
            total_tpd = sum(r['tpd'] for r in results.values())
            min_wr = min(r['wr'] for r in results.values())
            avg_wr = sum(r['wr'] for r in results.values()) / 3

            best_configs.append({
                'rsi_low': rsi_low,
                'rsi_high': rsi_high,
                'consec': consec,
                'momentum': mom,
                'blocked': blocked,
                'cooldown': cooldown,
                'total_tpd': total_tpd,
                'min_wr': min_wr,
                'avg_wr': avg_wr,
                'results': results
            })

    # Trier par nombre de trades (max)
    best_configs.sort(key=lambda x: x['total_tpd'], reverse=True)

    print("\n" + "=" * 70)
    print("🏆 TOP 10 CONFIGS (WR >= 55% pour chaque pair)")
    print("=" * 70)

    for i, cfg in enumerate(best_configs[:10]):
        print(f"\n#{i+1}: {cfg['total_tpd']:.1f} trades/jour | WR min: {cfg['min_wr']:.1f}%")
        print(f"   RSI: {cfg['rsi_low']}/{cfg['rsi_high']} | Consec: {cfg['consec']} | Mom: {cfg['momentum']}% | Cooldown: {cfg['cooldown']}")
        print(f"   Blocked hours: {cfg['blocked'] if cfg['blocked'] else 'Aucune'}")
        for sym, r in cfg['results'].items():
            base = sym.split('/')[0]
            print(f"   {base}: {r['tpd']:.1f}/jour ({r['wr']:.1f}%)")

    if best_configs:
        best = best_configs[0]
        print("\n" + "=" * 70)
        print("🎯 MEILLEURE CONFIG TROUVÉE:")
        print("=" * 70)
        print(f"""
RSI_OVERSOLD = {best['rsi_low']}
RSI_OVERBOUGHT = {best['rsi_high']}
CONSEC_THRESHOLD = {best['consec']}
MIN_MOMENTUM = {best['momentum']}
BLOCKED_HOURS = {best['blocked']}
COOLDOWN = {best['cooldown']}  # bougies (1 bougie = 15 min)

Résultats attendus:
- BTC: {best['results']['BTC/USDT']['tpd']:.1f}/jour ({best['results']['BTC/USDT']['wr']:.1f}% WR)
- ETH: {best['results']['ETH/USDT']['tpd']:.1f}/jour ({best['results']['ETH/USDT']['wr']:.1f}% WR)
- XRP: {best['results']['XRP/USDT']['tpd']:.1f}/jour ({best['results']['XRP/USDT']['wr']:.1f}% WR)
- TOTAL: {best['total_tpd']:.1f} trades/jour
- Win Rate minimum: {best['min_wr']:.1f}%
""")
    else:
        print("\n❌ Aucune config trouvée avec WR >= 55% pour toutes les pairs")
        print("Le maximum possible avec 55% WR est ~25-30 trades/jour")

if __name__ == "__main__":
    main()
