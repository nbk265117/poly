#!/usr/bin/env python3
"""
Analyse complète de la stratégie pour optimiser WR avec ~60 trades/jour
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import functools
print = functools.partial(print, flush=True)

def download_data(exchange, symbol, days=90):
    print(f'  📥 {symbol}...', end=' ', flush=True)
    all_data = []
    since = int((datetime.now(timezone.utc).timestamp() - days * 86400) * 1000)
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv: break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000: break
            time.sleep(0.1)
        except:
            time.sleep(1)
            break
    df = pd.DataFrame(all_data, columns=['ts','o','h','l','c','v'])
    df['dt'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    df['hour'] = df['dt'].dt.hour
    print(f'{len(df)} candles')
    return df

def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_bollinger(closes, period=20, std=2):
    sma = closes.rolling(period).mean()
    std_dev = closes.rolling(period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return (closes - lower) / (upper - lower)  # Position dans les bandes (0-1)

def calc_stochastic(df, k_period=14, d_period=3):
    low_min = df['l'].rolling(k_period).min()
    high_max = df['h'].rolling(k_period).max()
    k = 100 * (df['c'] - low_min) / (high_max - low_min)
    d = k.rolling(d_period).mean()
    return k, d

def calc_macd(closes, fast=12, slow=26, signal=9):
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calc_atr(df, period=14):
    high_low = df['h'] - df['l']
    high_close = abs(df['h'] - df['c'].shift())
    low_close = abs(df['l'] - df['c'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_volume_ratio(volume, period=20):
    avg_vol = volume.rolling(period).mean()
    return volume / avg_vol

def prepare_data(df):
    """Prépare toutes les features"""
    df = df.copy()

    # RSI avec différentes périodes
    df['rsi_7'] = calc_rsi(df['c'], 7)
    df['rsi_14'] = calc_rsi(df['c'], 14)
    df['rsi_21'] = calc_rsi(df['c'], 21)

    # Consecutive candles
    is_up = (df['c'] > df['o']).astype(int)
    is_down = (df['c'] < df['o']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    # Momentum
    df['mom_1'] = (df['c'] - df['c'].shift(1)) / df['c'].shift(1) * 100
    df['mom_3'] = (df['c'] - df['c'].shift(3)) / df['c'].shift(3) * 100
    df['mom_5'] = (df['c'] - df['c'].shift(5)) / df['c'].shift(5) * 100

    # Bollinger
    df['bb_pos'] = calc_bollinger(df['c'])

    # Stochastic
    df['stoch_k'], df['stoch_d'] = calc_stochastic(df)

    # MACD
    df['macd'], df['macd_signal'], df['macd_hist'] = calc_macd(df['c'])

    # ATR
    df['atr'] = calc_atr(df)
    df['atr_pct'] = df['atr'] / df['c'] * 100

    # Volume
    df['vol_ratio'] = calc_volume_ratio(df['v'])

    # Candle patterns
    df['body_size'] = abs(df['c'] - df['o']) / df['o'] * 100
    df['wick_upper'] = (df['h'] - df[['o', 'c']].max(axis=1)) / df['o'] * 100
    df['wick_lower'] = (df[['o', 'c']].min(axis=1) - df['l']) / df['o'] * 100

    # Target: next candle direction
    df['next_up'] = (df['c'].shift(-1) > df['o'].shift(-1)).astype(int)

    return df

def test_strategy(df, rsi_low, rsi_high, consec, mom, rsi_period='rsi_14',
                  use_bb=False, use_stoch=False, use_vol=False, blocked_hours=[]):
    """Test une configuration de stratégie"""
    df = df.copy()
    df['blocked'] = df['hour'].isin(blocked_hours)

    # Conditions de base
    rsi_col = rsi_period

    base_up = ((df['consec_down'] >= consec) | (df[rsi_col] < rsi_low))
    base_down = ((df['consec_up'] >= consec) | (df[rsi_col] > rsi_high))

    if mom > 0:
        base_up = base_up & (df['mom_3'] < -mom)
        base_down = base_down & (df['mom_3'] > mom)

    # Filtres additionnels
    if use_bb:
        base_up = base_up & (df['bb_pos'] < 0.2)
        base_down = base_down & (df['bb_pos'] > 0.8)

    if use_stoch:
        base_up = base_up & (df['stoch_k'] < 20)
        base_down = base_down & (df['stoch_k'] > 80)

    if use_vol:
        base_up = base_up & (df['vol_ratio'] > 1.0)
        base_down = base_down & (df['vol_ratio'] > 1.0)

    df['sig_up'] = base_up & (~df['blocked'])
    df['sig_dn'] = base_down & (~df['blocked'])

    # Simulate trades
    trades = []
    last_idx = -4

    for i in range(30, len(df) - 1):
        if i - last_idx < 4: continue
        if df.iloc[i]['sig_up']:
            trades.append(df.iloc[i]['next_up'] == 1)
            last_idx = i
        elif df.iloc[i]['sig_dn']:
            trades.append(df.iloc[i]['next_up'] == 0)
            last_idx = i

    if not trades:
        return {'trades': 0, 'wr': 0, 'tpd': 0}

    days = max(1, (df['dt'].max() - df['dt'].min()).days)
    return {
        'trades': len(trades),
        'wins': sum(trades),
        'wr': sum(trades) / len(trades) * 100,
        'tpd': len(trades) / days
    }

def analyze_indicator_effectiveness(df):
    """Analyse l'efficacité de chaque indicateur"""
    print("\n📊 ANALYSE EFFICACITÉ DES INDICATEURS")
    print("=" * 60)

    results = []

    # Test RSI seul avec différents seuils
    for period in ['rsi_7', 'rsi_14', 'rsi_21']:
        for low, high in [(25, 75), (30, 70), (33, 67), (35, 65)]:
            r = test_strategy(df, low, high, consec=99, mom=0, rsi_period=period)
            if r['trades'] > 0:
                results.append({
                    'indicator': f'RSI({period[-2:]}) {low}/{high}',
                    'trades': r['trades'],
                    'tpd': r['tpd'],
                    'wr': r['wr']
                })

    # Test Consecutive seul
    for consec in [2, 3, 4, 5]:
        r = test_strategy(df, rsi_low=0, rsi_high=100, consec=consec, mom=0)
        if r['trades'] > 0:
            results.append({
                'indicator': f'Consec >= {consec}',
                'trades': r['trades'],
                'tpd': r['tpd'],
                'wr': r['wr']
            })

    # Trier par WR
    results.sort(key=lambda x: x['wr'], reverse=True)

    print(f"{'Indicateur':<25} {'Trades':<10} {'TPD':<10} {'Win Rate':<10}")
    print("-" * 60)
    for r in results[:15]:
        print(f"{r['indicator']:<25} {r['trades']:<10} {r['tpd']:<10.1f} {r['wr']:<10.1f}%")

def find_best_combination(data, target_tpd=20):
    """Trouve la meilleure combinaison pour ~20 trades/jour/pair"""
    print(f"\n🔍 RECHERCHE MEILLEURE CONFIG (~{target_tpd} trades/jour/pair)")
    print("=" * 60)

    best_configs = []

    # Grid search
    for rsi_period in ['rsi_7', 'rsi_14', 'rsi_21']:
        for rsi_low in [25, 28, 30, 32, 33, 35]:
            rsi_high = 100 - rsi_low
            for consec in [2, 3, 4]:
                for mom in [0.0, 0.05, 0.1, 0.15]:
                    for use_bb in [False, True]:
                        for use_stoch in [False, True]:
                            for use_vol in [False, True]:
                                for blocked in [[], [3,7,15,18,19,20]]:

                                    all_valid = True
                                    results = {}

                                    for sym, df in data.items():
                                        r = test_strategy(df, rsi_low, rsi_high, consec, mom,
                                                         rsi_period, use_bb, use_stoch, use_vol, blocked)
                                        results[sym] = r

                                        # Check if within target range
                                        if r['tpd'] < target_tpd * 0.7 or r['tpd'] > target_tpd * 1.5:
                                            all_valid = False
                                            break

                                    if all_valid:
                                        total_tpd = sum(r['tpd'] for r in results.values())
                                        min_wr = min(r['wr'] for r in results.values())
                                        avg_wr = sum(r['wr'] for r in results.values()) / 3

                                        if min_wr > 50:  # Au moins profitable
                                            best_configs.append({
                                                'rsi_period': rsi_period,
                                                'rsi_low': rsi_low,
                                                'rsi_high': rsi_high,
                                                'consec': consec,
                                                'mom': mom,
                                                'use_bb': use_bb,
                                                'use_stoch': use_stoch,
                                                'use_vol': use_vol,
                                                'blocked': blocked,
                                                'total_tpd': total_tpd,
                                                'min_wr': min_wr,
                                                'avg_wr': avg_wr,
                                                'results': results
                                            })

    # Trier par WR moyen
    best_configs.sort(key=lambda x: x['avg_wr'], reverse=True)

    return best_configs[:20]

def analyze_by_hour(data):
    """Analyse performance par heure"""
    print("\n⏰ ANALYSE PAR HEURE (UTC)")
    print("=" * 60)

    hour_stats = {h: {'trades': 0, 'wins': 0} for h in range(24)}

    for sym, df in data.items():
        df = prepare_data(df)
        df['sig'] = ((df['consec_down'] >= 2) | (df['rsi_14'] < 33) |
                     (df['consec_up'] >= 2) | (df['rsi_14'] > 67))

        for i in range(30, len(df) - 1):
            if df.iloc[i]['sig']:
                hour = df.iloc[i]['hour']
                is_up_signal = (df.iloc[i]['consec_down'] >= 2) or (df.iloc[i]['rsi_14'] < 33)

                if is_up_signal:
                    win = df.iloc[i]['next_up'] == 1
                else:
                    win = df.iloc[i]['next_up'] == 0

                hour_stats[hour]['trades'] += 1
                hour_stats[hour]['wins'] += int(win)

    print(f"{'Heure':<8} {'Trades':<10} {'Win Rate':<12} {'Recommandation':<20}")
    print("-" * 60)

    good_hours = []
    bad_hours = []

    for h in range(24):
        trades = hour_stats[h]['trades']
        if trades > 0:
            wr = hour_stats[h]['wins'] / trades * 100
            if wr >= 54:
                rec = "✅ Bon"
                good_hours.append(h)
            elif wr >= 52:
                rec = "⚠️ Moyen"
            else:
                rec = "❌ Éviter"
                bad_hours.append(h)
            print(f"{h:02d}:00    {trades:<10} {wr:<12.1f}% {rec:<20}")

    print(f"\n💡 Heures à ÉVITER: {bad_hours}")
    print(f"💡 Meilleures heures: {good_hours[:8]}")

    return bad_hours

def main():
    print("=" * 70)
    print("🔬 ANALYSE COMPLÈTE DE LA STRATÉGIE")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    print("\n📥 Téléchargement données (90 jours)...")
    data = {}
    for sym in symbols:
        df = download_data(exchange, sym, 90)
        data[sym] = prepare_data(df)

    # 1. Analyse efficacité indicateurs
    print("\n" + "=" * 70)
    print("1️⃣ EFFICACITÉ DES INDICATEURS PAR PAIR")
    print("=" * 70)

    for sym, df in data.items():
        print(f"\n📊 {sym.split('/')[0]}:")
        analyze_indicator_effectiveness(df)

    # 2. Analyse par heure
    print("\n" + "=" * 70)
    print("2️⃣ ANALYSE PAR HEURE")
    print("=" * 70)
    bad_hours = analyze_by_hour(data)

    # 3. Recherche meilleure combinaison
    print("\n" + "=" * 70)
    print("3️⃣ MEILLEURES CONFIGURATIONS (~20 trades/jour/pair)")
    print("=" * 70)

    best = find_best_combination(data, target_tpd=20)

    if best:
        print(f"\n🏆 TOP 5 CONFIGURATIONS:")
        print("-" * 70)

        for i, cfg in enumerate(best[:5]):
            print(f"\n#{i+1}: Avg WR: {cfg['avg_wr']:.1f}% | Min WR: {cfg['min_wr']:.1f}% | TPD: {cfg['total_tpd']:.1f}")
            print(f"   RSI({cfg['rsi_period'][-2:]}): {cfg['rsi_low']}/{cfg['rsi_high']}")
            print(f"   Consec: {cfg['consec']} | Mom: {cfg['mom']}%")
            print(f"   Bollinger: {'✅' if cfg['use_bb'] else '❌'} | Stoch: {'✅' if cfg['use_stoch'] else '❌'} | Vol: {'✅' if cfg['use_vol'] else '❌'}")
            print(f"   Blocked hours: {cfg['blocked'] if cfg['blocked'] else 'None'}")
            for sym, r in cfg['results'].items():
                print(f"   {sym.split('/')[0]}: {r['tpd']:.1f}/j ({r['wr']:.1f}%)")

        # Meilleure config
        top = best[0]
        print("\n" + "=" * 70)
        print("🎯 CONFIGURATION RECOMMANDÉE")
        print("=" * 70)
        print(f"""
# Paramètres optimisés:
RSI_PERIOD = {top['rsi_period'][-2:]}
RSI_OVERSOLD = {top['rsi_low']}
RSI_OVERBOUGHT = {top['rsi_high']}
CONSEC_THRESHOLD = {top['consec']}
MIN_MOMENTUM = {top['mom']}
USE_BOLLINGER = {top['use_bb']}
USE_STOCHASTIC = {top['use_stoch']}
USE_VOLUME = {top['use_vol']}
BLOCKED_HOURS = {top['blocked']}

# Résultats attendus:
# BTC: {top['results']['BTC/USDT']['tpd']:.1f}/jour ({top['results']['BTC/USDT']['wr']:.1f}%)
# ETH: {top['results']['ETH/USDT']['tpd']:.1f}/jour ({top['results']['ETH/USDT']['wr']:.1f}%)
# XRP: {top['results']['XRP/USDT']['tpd']:.1f}/jour ({top['results']['XRP/USDT']['wr']:.1f}%)
# TOTAL: {top['total_tpd']:.1f} trades/jour
# Win Rate moyen: {top['avg_wr']:.1f}%
""")
    else:
        print("\n❌ Aucune config trouvée avec ces contraintes")

if __name__ == "__main__":
    main()
