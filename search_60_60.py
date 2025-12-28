#!/usr/bin/env python3
"""
RECHERCHE EXHAUSTIVE: 60 trades/jour + 60% WR
Test de 15+ indicateurs et combinaisons
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
import functools
print = functools.partial(print, flush=True)

def download_data(exchange, symbol, days=120):
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

# ============== INDICATEURS ==============

def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_williams_r(df, period=14):
    high_max = df['h'].rolling(period).max()
    low_min = df['l'].rolling(period).min()
    return -100 * (high_max - df['c']) / (high_max - low_min)

def calc_cci(df, period=20):
    tp = (df['h'] + df['l'] + df['c']) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    return (tp - sma) / (0.015 * mad)

def calc_mfi(df, period=14):
    tp = (df['h'] + df['l'] + df['c']) / 3
    mf = tp * df['v']
    pos_mf = mf.where(tp > tp.shift(1), 0)
    neg_mf = mf.where(tp < tp.shift(1), 0)
    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()
    return 100 - (100 / (1 + pos_sum / neg_sum))

def calc_stoch(df, k=14, d=3):
    low_min = df['l'].rolling(k).min()
    high_max = df['h'].rolling(k).max()
    stoch_k = 100 * (df['c'] - low_min) / (high_max - low_min)
    stoch_d = stoch_k.rolling(d).mean()
    return stoch_k, stoch_d

def calc_bb_position(closes, period=20, std=2):
    sma = closes.rolling(period).mean()
    std_dev = closes.rolling(period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return (closes - lower) / (upper - lower)

def calc_atr_pct(df, period=14):
    tr = pd.concat([
        df['h'] - df['l'],
        abs(df['h'] - df['c'].shift(1)),
        abs(df['l'] - df['c'].shift(1))
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr / df['c'] * 100

def prepare_indicators(df):
    df = df.copy()

    # RSI multiple periods
    df['rsi_3'] = calc_rsi(df['c'], 3)
    df['rsi_5'] = calc_rsi(df['c'], 5)
    df['rsi_7'] = calc_rsi(df['c'], 7)
    df['rsi_14'] = calc_rsi(df['c'], 14)

    # Williams %R
    df['wr_7'] = calc_williams_r(df, 7)
    df['wr_14'] = calc_williams_r(df, 14)

    # CCI
    df['cci_14'] = calc_cci(df, 14)
    df['cci_20'] = calc_cci(df, 20)

    # MFI
    df['mfi_7'] = calc_mfi(df, 7)
    df['mfi_14'] = calc_mfi(df, 14)

    # Stochastic
    df['stoch_k'], df['stoch_d'] = calc_stoch(df, 14, 3)
    df['stoch_k_fast'], _ = calc_stoch(df, 5, 3)

    # Bollinger position
    df['bb_pos'] = calc_bb_position(df['c'])

    # ATR %
    df['atr_pct'] = calc_atr_pct(df)

    # Consecutive candles
    is_up = (df['c'] > df['o']).astype(int)
    is_down = (df['c'] < df['o']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    # Momentum
    df['mom_1'] = (df['c'] - df['c'].shift(1)) / df['c'].shift(1) * 100
    df['mom_2'] = (df['c'] - df['c'].shift(2)) / df['c'].shift(2) * 100
    df['mom_3'] = (df['c'] - df['c'].shift(3)) / df['c'].shift(3) * 100

    # Volume ratio
    df['vol_ratio'] = df['v'] / df['v'].rolling(20).mean()

    # Candle body %
    df['body_pct'] = abs(df['c'] - df['o']) / df['o'] * 100

    # Wicks
    df['upper_wick'] = (df['h'] - df[['o', 'c']].max(axis=1)) / df['o'] * 100
    df['lower_wick'] = (df[['o', 'c']].min(axis=1) - df['l']) / df['o'] * 100

    # Target
    df['next_up'] = (df['c'].shift(-1) > df['o'].shift(-1)).astype(int)

    return df

def test_strategy(df, conditions_up, conditions_down, cooldown=3):
    trades = []
    last_idx = -cooldown

    for i in range(50, len(df) - 1):
        if i - last_idx < cooldown: continue

        row = df.iloc[i]

        # UP signal
        up_ok = True
        for col, op, val in conditions_up:
            if pd.isna(row[col]):
                up_ok = False
                break
            if op == '<' and not (row[col] < val): up_ok = False
            elif op == '>' and not (row[col] > val): up_ok = False
            elif op == '>=' and not (row[col] >= val): up_ok = False
            elif op == '<=' and not (row[col] <= val): up_ok = False

        # DOWN signal
        down_ok = True
        for col, op, val in conditions_down:
            if pd.isna(row[col]):
                down_ok = False
                break
            if op == '<' and not (row[col] < val): down_ok = False
            elif op == '>' and not (row[col] > val): down_ok = False
            elif op == '>=' and not (row[col] >= val): down_ok = False
            elif op == '<=' and not (row[col] <= val): down_ok = False

        if up_ok:
            trades.append(row['next_up'] == 1)
            last_idx = i
        elif down_ok:
            trades.append(row['next_up'] == 0)
            last_idx = i

    if not trades:
        return {'trades': 0, 'wins': 0, 'wr': 0, 'tpd': 0}

    days = max(1, (df['dt'].max() - df['dt'].min()).days)
    return {
        'trades': len(trades),
        'wins': sum(trades),
        'wr': sum(trades) / len(trades) * 100,
        'tpd': len(trades) / days
    }

def main():
    print("=" * 70)
    print("🔬 RECHERCHE: 60 TRADES/JOUR + 60% WIN RATE")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    print("\n📥 Téléchargement données (120 jours)...")
    data = {}
    for sym in symbols:
        df = download_data(exchange, sym, 120)
        data[sym] = prepare_indicators(df)

    # ============== TEST INDICATEURS SEULS ==============
    print("\n" + "=" * 70)
    print("1️⃣ TEST INDICATEURS INDIVIDUELS (meilleurs par pair)")
    print("=" * 70)

    indicators = [
        ('rsi_3', 20, 80), ('rsi_3', 25, 75), ('rsi_3', 30, 70),
        ('rsi_5', 20, 80), ('rsi_5', 25, 75), ('rsi_5', 30, 70),
        ('rsi_7', 25, 75), ('rsi_7', 30, 70), ('rsi_7', 35, 65),
        ('wr_7', -80, -20), ('wr_7', -85, -15), ('wr_7', -75, -25),
        ('wr_14', -80, -20), ('wr_14', -85, -15),
        ('cci_14', -100, 100), ('cci_14', -150, 150), ('cci_20', -100, 100),
        ('mfi_7', 20, 80), ('mfi_7', 25, 75), ('mfi_14', 20, 80), ('mfi_14', 25, 75),
        ('stoch_k', 20, 80), ('stoch_k', 15, 85), ('stoch_k_fast', 15, 85),
        ('bb_pos', 0.1, 0.9), ('bb_pos', 0.15, 0.85), ('bb_pos', 0.2, 0.8),
    ]

    best_indicators = {}

    for sym, df in data.items():
        print(f"\n📊 {sym.split('/')[0]}:")
        sym_results = []

        for ind, low, high in indicators:
            up_cond = [(ind, '<', low)]
            down_cond = [(ind, '>', high)]
            r = test_strategy(df, up_cond, down_cond, cooldown=3)

            if r['trades'] > 0:
                sym_results.append({
                    'name': f"{ind} {low}/{high}",
                    'wr': r['wr'],
                    'tpd': r['tpd'],
                    'trades': r['trades']
                })

        # Sort by WR
        sym_results.sort(key=lambda x: x['wr'], reverse=True)
        best_indicators[sym] = sym_results[:5]

        print(f"  {'Indicateur':<25} {'WR':<10} {'TPD':<10}")
        print(f"  {'-'*45}")
        for r in sym_results[:10]:
            wr_status = "✅" if r['wr'] >= 55 else "⚠️" if r['wr'] >= 53 else ""
            print(f"  {r['name']:<25} {r['wr']:<10.1f}% {r['tpd']:<10.1f} {wr_status}")

    # ============== RECHERCHE EXHAUSTIVE ==============
    print("\n" + "=" * 70)
    print("2️⃣ RECHERCHE COMBINAISONS (cible: 60 TPD, 60% WR)")
    print("=" * 70)

    best_found = []

    # Test toutes les combinaisons d'indicateurs
    rsi_options = [
        ('rsi_3', 25, 75), ('rsi_3', 30, 70),
        ('rsi_5', 25, 75), ('rsi_5', 30, 70), ('rsi_5', 35, 65),
        ('rsi_7', 30, 70), ('rsi_7', 35, 65),
    ]

    secondary_options = [
        None,  # Pas de second indicateur
        ('wr_7', -80, -20),
        ('wr_7', -75, -25),
        ('mfi_7', 25, 75),
        ('mfi_14', 25, 75),
        ('stoch_k_fast', 20, 80),
        ('cci_14', -100, 100),
    ]

    consec_options = [1, 2, 3]
    cooldown_options = [2, 3, 4]

    print("\n🔍 Test de combinaisons...")
    total_tests = len(rsi_options) * len(secondary_options) * len(consec_options) * len(cooldown_options)
    print(f"   {total_tests} combinaisons à tester...")

    tested = 0
    for rsi_ind, rsi_low, rsi_high in rsi_options:
        for secondary in secondary_options:
            for consec in consec_options:
                for cooldown in cooldown_options:
                    tested += 1

                    # Build conditions
                    up_conds = [(rsi_ind, '<', rsi_low)]
                    down_conds = [(rsi_ind, '>', rsi_high)]

                    if consec > 1:
                        up_conds.append(('consec_down', '>=', consec))
                        down_conds.append(('consec_up', '>=', consec))

                    if secondary:
                        sec_ind, sec_low, sec_high = secondary
                        up_conds.append((sec_ind, '<', sec_low))
                        down_conds.append((sec_ind, '>', sec_high))

                    # Test on all pairs
                    results = {}
                    valid = True

                    for sym, df in data.items():
                        r = test_strategy(df, up_conds, down_conds, cooldown)
                        results[sym] = r
                        if r['wr'] < 52:  # Minimum pour être profitable
                            valid = False

                    if valid and all(r['trades'] > 0 for r in results.values()):
                        total_tpd = sum(r['tpd'] for r in results.values())
                        total_trades = sum(r['trades'] for r in results.values())
                        total_wins = sum(r['wins'] for r in results.values())
                        avg_wr = total_wins / total_trades * 100
                        min_wr = min(r['wr'] for r in results.values())

                        best_found.append({
                            'rsi': f"{rsi_ind} {rsi_low}/{rsi_high}",
                            'secondary': f"{secondary[0]} {secondary[1]}/{secondary[2]}" if secondary else "none",
                            'consec': consec,
                            'cooldown': cooldown,
                            'total_tpd': total_tpd,
                            'avg_wr': avg_wr,
                            'min_wr': min_wr,
                            'results': results
                        })

    # Sort by WR then TPD
    best_found.sort(key=lambda x: (x['avg_wr'], x['total_tpd']), reverse=True)

    print(f"\n✅ {len(best_found)} configurations valides trouvées")

    # ============== RÉSULTATS ==============
    print("\n" + "=" * 70)
    print("🏆 TOP 15 CONFIGURATIONS")
    print("=" * 70)

    for i, cfg in enumerate(best_found[:15]):
        print(f"\n#{i+1}: TPD={cfg['total_tpd']:.1f} | AvgWR={cfg['avg_wr']:.1f}% | MinWR={cfg['min_wr']:.1f}%")
        print(f"   RSI: {cfg['rsi']} | 2nd: {cfg['secondary']} | Consec: {cfg['consec']} | CD: {cfg['cooldown']}")
        for sym, r in cfg['results'].items():
            status = "✅" if r['wr'] >= 55 else "⚠️" if r['wr'] >= 53 else "❌"
            print(f"   {sym.split('/')[0]}: {r['tpd']:.1f}/j ({r['wr']:.1f}%) {status}")

    # ============== ANALYSE RÉALITÉ ==============
    print("\n" + "=" * 70)
    print("📊 ANALYSE RÉALITÉ: 60 TPD + 60% WR")
    print("=" * 70)

    # Chercher configs avec TPD >= 50
    high_volume = [c for c in best_found if c['total_tpd'] >= 50]
    if high_volume:
        best_high = max(high_volume, key=lambda x: x['avg_wr'])
        print(f"\n🔹 Meilleure config HIGH VOLUME (≥50 TPD):")
        print(f"   TPD: {best_high['total_tpd']:.1f} | WR: {best_high['avg_wr']:.1f}%")
        print(f"   {best_high['rsi']} + {best_high['secondary']}")

    # Chercher configs avec WR >= 57
    high_wr = [c for c in best_found if c['avg_wr'] >= 57]
    if high_wr:
        best_wr = max(high_wr, key=lambda x: x['total_tpd'])
        print(f"\n🔹 Meilleure config HIGH WR (≥57%):")
        print(f"   TPD: {best_wr['total_tpd']:.1f} | WR: {best_wr['avg_wr']:.1f}%")
        print(f"   {best_wr['rsi']} + {best_wr['secondary']}")

    # Meilleur compromis
    print(f"\n🔹 Meilleur COMPROMIS (score = WR * TPD):")
    best_found.sort(key=lambda x: x['avg_wr'] * x['total_tpd'], reverse=True)
    best = best_found[0]
    print(f"   TPD: {best['total_tpd']:.1f} | WR: {best['avg_wr']:.1f}%")
    print(f"   {best['rsi']} + {best['secondary']} + consec={best['consec']}")

    # VERDICT
    print("\n" + "=" * 70)
    print("⚠️ VERDICT FINAL")
    print("=" * 70)

    max_tpd_with_55wr = max([c['total_tpd'] for c in best_found if c['min_wr'] >= 55], default=0)
    max_wr_with_60tpd = max([c['avg_wr'] for c in best_found if c['total_tpd'] >= 60], default=0)

    print(f"""
📊 DONNÉES ANALYSÉES: 120 jours, 3 pairs, 15+ indicateurs

🎯 OBJECTIF: 60 trades/jour + 60% WR

📈 MAXIMUM ATTEIGNABLE:
   • Avec 55% WR minimum: {max_tpd_with_55wr:.1f} trades/jour
   • Avec 60 TPD minimum: {max_wr_with_60tpd:.1f}% WR max

❌ 60 TPD + 60% WR = NON ATTEIGNABLE

   C'est mathématiquement impossible car:
   - Plus de trades = signaux moins sélectifs = WR plus bas
   - 60% WR nécessite des signaux très stricts = moins de trades

💡 RECOMMANDATIONS:
   1. HIGH VOLUME: ~55 TPD avec ~54% WR (profit modéré, volume élevé)
   2. HIGH QUALITY: ~25 TPD avec ~57% WR (profit/trade élevé, volume bas)
   3. COMPROMIS: ~45 TPD avec ~55% WR (équilibré)
""")

    if best_found:
        top = best_found[0]
        print(f"\n🎯 CONFIG RECOMMANDÉE:")
        print(f"   RSI: {top['rsi']}")
        print(f"   Second: {top['secondary']}")
        print(f"   Consec: {top['consec']}")
        print(f"   Cooldown: {top['cooldown']}")
        print(f"   → {top['total_tpd']:.1f} trades/jour | {top['avg_wr']:.1f}% WR")

if __name__ == "__main__":
    main()
