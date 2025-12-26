#!/usr/bin/env python3
"""
Analyse avancée - Recherche de patterns avec win rate > 55%
"""

import pandas as pd
import numpy as np

print("=" * 80)
print("ANALYSE AVANCÉE - RECHERCHE D'EDGE")
print("=" * 80)

df = pd.read_csv('/Users/mac/poly/data/historical/BTC_USDT_15m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Direction prochaine bougie
df['next_close'] = df['close'].shift(-1)
df['next_up'] = df['next_close'] > df['close']

# Indicateurs de base
df['EMA8'] = df['close'].ewm(span=8, adjust=False).mean()
df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()

delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
df['RSI'] = 100 - (100 / (1 + gain.ewm(span=14).mean() / loss.ewm(span=14).mean()))

df['VOL_MA'] = df['volume'].rolling(20).mean()
df['VOL_RATIO'] = df['volume'] / df['VOL_MA']

# === PATTERNS ANTI-TENDANCE ===
print("\n" + "=" * 80)
print("1. PATTERNS ANTI-TENDANCE (RETOURNEMENT)")
print("=" * 80)

# Séquences de bougies
df['up'] = df['close'] > df['open']
df['consec_up'] = df['up'].rolling(3).sum()
df['consec_down'] = (~df['up']).rolling(3).sum()

def test_condition(df, cond, name, predict_up=True):
    """Test une condition"""
    subset = df[cond].dropna()
    if len(subset) < 100:
        return None

    if predict_up:
        wr = subset['next_up'].mean() * 100
    else:
        wr = (1 - subset['next_up'].mean()) * 100

    trades_day = len(subset) / 719
    return wr, len(subset), trades_day

print("\n{:<45} {:>8} {:>8} {:>10}".format("CONDITION", "WIN %", "TRADES", "T/JOUR"))
print("-" * 75)

# Après 3 bougies DOWN consécutives -> prédire UP (retournement)
cond = df['consec_down'] == 3
result = test_condition(df, cond, "3 DOWN consécutives → UP")
if result:
    print(f"{'3 DOWN consécutives → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Après 4 bougies DOWN
df['consec_down_4'] = (~df['up']).rolling(4).sum()
cond = df['consec_down_4'] == 4
result = test_condition(df, cond, "4 DOWN → UP")
if result:
    print(f"{'4 DOWN consécutives → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Après 5 bougies DOWN
df['consec_down_5'] = (~df['up']).rolling(5).sum()
cond = df['consec_down_5'] == 5
result = test_condition(df, cond, "5 DOWN → UP")
if result:
    print(f"{'5 DOWN consécutives → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# RSI survendu extrême -> prédire UP
cond = df['RSI'] < 20
result = test_condition(df, cond, "RSI < 20 → UP")
if result:
    print(f"{'RSI < 20 (Survendu) → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

cond = df['RSI'] < 25
result = test_condition(df, cond, "RSI < 25 → UP")
if result:
    print(f"{'RSI < 25 → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# RSI suracheté extrême -> prédire DOWN
cond = df['RSI'] > 80
result = test_condition(df, cond, "RSI > 80 → DOWN", predict_up=False)
if result:
    print(f"{'RSI > 80 (Suracheté) → Prédire DOWN':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

cond = df['RSI'] > 75
result = test_condition(df, cond, "RSI > 75 → DOWN", predict_up=False)
if result:
    print(f"{'RSI > 75 → Prédire DOWN':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# === CONTINUATION FORTE ===
print("\n" + "=" * 80)
print("2. CONTINUATION FORTE (SUITE DE TENDANCE)")
print("=" * 80)

print("\n{:<45} {:>8} {:>8} {:>10}".format("CONDITION", "WIN %", "TRADES", "T/JOUR"))
print("-" * 75)

# Après 3 UP consécutives -> prédire UP (continuation)
cond = df['consec_up'] == 3
result = test_condition(df, cond, "3 UP → UP")
if result:
    print(f"{'3 UP consécutives → Prédire UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Fort momentum + RSI pas extrême -> prédire continuation
df['momentum'] = (df['close'] - df['close'].shift(5)) / df['close'].shift(5) * 100
cond = (df['momentum'] > 1) & (df['RSI'] < 70)
result = test_condition(df, cond, "Momentum > 1% + RSI < 70")
if result:
    print(f"{'Momentum > 1% + RSI < 70 → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

cond = (df['momentum'] > 0.5) & (df['RSI'] > 55) & (df['RSI'] < 70)
result = test_condition(df, cond, "Mom > 0.5% + RSI 55-70")
if result:
    print(f"{'Mom > 0.5% + RSI 55-70 → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# === PATTERNS DE BOUGIES ===
print("\n" + "=" * 80)
print("3. PATTERNS DE BOUGIES SPÉCIFIQUES")
print("=" * 80)

# Calculs pour patterns
df['body'] = abs(df['close'] - df['open'])
df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
df['range'] = df['high'] - df['low']

print("\n{:<45} {:>8} {:>8} {:>10}".format("CONDITION", "WIN %", "TRADES", "T/JOUR"))
print("-" * 75)

# Hammer (longue mèche basse, bougie bullish)
cond = (df['lower_wick'] > df['body'] * 2) & (df['close'] > df['open']) & (df['upper_wick'] < df['body'] * 0.5)
result = test_condition(df, cond, "Hammer → UP")
if result:
    print(f"{'Hammer (mèche basse 2x corps) → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Hammer avec confirmation RSI
cond = (df['lower_wick'] > df['body'] * 2) & (df['close'] > df['open']) & (df['RSI'] < 50)
result = test_condition(df, cond, "Hammer + RSI < 50")
if result:
    print(f"{'Hammer + RSI < 50 → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Engulfing bullish (grosse bougie verte après rouge)
df['prev_body'] = df['body'].shift(1)
df['prev_up'] = df['up'].shift(1)
cond = (df['up']) & (~df['prev_up']) & (df['body'] > df['prev_body'] * 1.5)
result = test_condition(df, cond, "Engulfing Bullish → UP")
if result:
    print(f"{'Engulfing Bullish → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Grande bougie verte (fort momentum instantané)
df['body_pct'] = df['body'] / df['open'] * 100
cond = (df['up']) & (df['body_pct'] > 0.5)
result = test_condition(df, cond, "Grande bougie verte > 0.5%")
if result:
    print(f"{'Grande bougie verte > 0.5% → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

cond = (df['up']) & (df['body_pct'] > 0.8)
result = test_condition(df, cond, "Grande bougie verte > 0.8%")
if result:
    print(f"{'Grande bougie verte > 0.8% → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# === VOLATILITÉ ===
print("\n" + "=" * 80)
print("4. CONDITIONS DE VOLATILITÉ")
print("=" * 80)

df['ATR'] = df['range'].rolling(14).mean()
df['ATR_pct'] = df['ATR'] / df['close'] * 100

print("\n{:<45} {:>8} {:>8} {:>10}".format("CONDITION", "WIN %", "TRADES", "T/JOUR"))
print("-" * 75)

# Faible volatilité + tendance haussière
cond = (df['ATR_pct'] < 1) & (df['close'] > df['EMA21'])
result = test_condition(df, cond, "Low Vol + EMA21")
if result:
    print(f"{'ATR < 1% + Prix > EMA21 → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# Haute volatilité + continuation
cond = (df['ATR_pct'] > 2) & (df['momentum'] > 0.5)
result = test_condition(df, cond, "High Vol + Momentum")
if result:
    print(f"{'ATR > 2% + Momentum > 0.5% → UP':<45} {result[0]:>7.1f}% {result[1]:>8} {result[2]:>10.1f}")

# === HEURES SPÉCIFIQUES ===
print("\n" + "=" * 80)
print("5. HEURES DE TRADING (UTC)")
print("=" * 80)

df['hour'] = df['timestamp'].dt.hour

print("\n{:<20} {:>8} {:>8}".format("HEURE (UTC)", "WIN UP %", "TRADES"))
print("-" * 40)

for hour in range(24):
    subset = df[df['hour'] == hour].dropna()
    if len(subset) > 100:
        wr = subset['next_up'].mean() * 100
        status = "✅" if wr > 52.63 else ""
        print(f"  {hour:02d}:00 - {hour:02d}:59       {wr:>7.1f}%    {len(subset)} {status}")

# === JOURS DE LA SEMAINE ===
print("\n" + "=" * 80)
print("6. JOURS DE LA SEMAINE")
print("=" * 80)

df['dayofweek'] = df['timestamp'].dt.dayofweek
days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

print("\n{:<15} {:>8} {:>8}".format("JOUR", "WIN UP %", "TRADES"))
print("-" * 35)

for dow in range(7):
    subset = df[df['dayofweek'] == dow].dropna()
    if len(subset) > 100:
        wr = subset['next_up'].mean() * 100
        status = "✅" if wr > 52.63 else ""
        print(f"  {days[dow]:<12} {wr:>7.1f}%    {len(subset)} {status}")

# === COMBINAISONS OPTIMALES ===
print("\n" + "=" * 80)
print("7. RECHERCHE EXHAUSTIVE - MEILLEURES COMBINAISONS")
print("=" * 80)

df_clean = df.dropna()
results = []

# Test de toutes les combinaisons possibles
for rsi_low in [20, 25, 30, 35, 40]:
    for rsi_high in [60, 65, 70, 75, 80]:
        if rsi_low >= rsi_high:
            continue
        for mom_thresh in [0, 0.1, 0.2, 0.3, 0.5]:
            for vol_thresh in [0.5, 1.0, 1.5, 2.0]:
                cond = (
                    (df_clean['RSI'] > rsi_low) &
                    (df_clean['RSI'] < rsi_high) &
                    (df_clean['momentum'] > mom_thresh) &
                    (df_clean['VOL_RATIO'] > vol_thresh)
                )
                subset = df_clean[cond]
                if len(subset) >= 500:  # Minimum 500 trades pour significativité
                    wr = subset['next_up'].mean() * 100
                    tpd = len(subset) / 719
                    if wr > 51:  # Seulement les prometteurs
                        results.append({
                            'rsi_low': rsi_low,
                            'rsi_high': rsi_high,
                            'momentum': mom_thresh,
                            'volume': vol_thresh,
                            'win_rate': wr,
                            'trades': len(subset),
                            'trades_day': tpd
                        })

# Trier par win rate
results = sorted(results, key=lambda x: x['win_rate'], reverse=True)

print("\nTop 10 combinaisons (min 500 trades) :")
print("-" * 80)
print("{:<40} {:>8} {:>8} {:>10}".format("CONDITION", "WIN %", "TRADES", "T/JOUR"))
for r in results[:10]:
    name = f"RSI {r['rsi_low']}-{r['rsi_high']} + Mom>{r['momentum']} + Vol>{r['volume']}"
    status = "✅" if r['win_rate'] > 52.63 else ""
    print(f"{name:<40} {r['win_rate']:>7.1f}% {r['trades']:>8} {r['trades_day']:>9.1f} {status}")

# === RÉSULTAT FINAL ===
print("\n" + "=" * 80)
print("8. VERDICT FINAL")
print("=" * 80)

if results and results[0]['win_rate'] > 52.63:
    best = results[0]
    print(f"\n✅ STRATÉGIE RENTABLE TROUVÉE !")
    print(f"   RSI: {best['rsi_low']}-{best['rsi_high']}")
    print(f"   Momentum: > {best['momentum']}%")
    print(f"   Volume: > {best['volume']}x")
    print(f"   Win Rate: {best['win_rate']:.2f}%")
    print(f"   Trades/jour: {best['trades_day']:.1f}")
else:
    print("\n❌ AUCUNE STRATÉGIE RENTABLE TROUVÉE")
    print("   Le marché Bitcoin 15m est trop efficace.")
    print("   Les indicateurs techniques classiques ne peuvent pas")
    print("   prédire la direction de la prochaine bougie avec > 52.63%.")

print("\n" + "=" * 80)
