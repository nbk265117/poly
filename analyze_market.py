#!/usr/bin/env python3
"""
Analyse du marché Bitcoin 15m pour stratégie Polymarket
Objectif : Identifier les patterns avec win rate > 55%
"""

import pandas as pd
import numpy as np
from datetime import timedelta

# Charger les données
print("=" * 80)
print("ANALYSE DU MARCHÉ BITCOIN 15M POUR POLYMARKET")
print("=" * 80)

df = pd.read_csv('/Users/mac/poly/data/historical/BTC_USDT_15m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"\nDonnées chargées : {len(df)} bougies")
print(f"Période : {df['timestamp'].min()} à {df['timestamp'].max()}")
print(f"Durée : {(df['timestamp'].max() - df['timestamp'].min()).days} jours")

# Calculer la direction de la prochaine bougie (ce qu'on veut prédire)
df['next_close'] = df['close'].shift(-1)
df['next_direction'] = np.where(df['next_close'] > df['close'], 'UP', 'DOWN')
df['direction_correct'] = df['next_close'] > df['close']  # True si UP

# Statistiques de base
print("\n" + "=" * 80)
print("1. STATISTIQUES DE BASE")
print("=" * 80)

up_count = (df['next_direction'] == 'UP').sum()
down_count = (df['next_direction'] == 'DOWN').sum()
total = up_count + down_count

print(f"Bougies UP :   {up_count} ({up_count/total*100:.1f}%)")
print(f"Bougies DOWN : {down_count} ({down_count/total*100:.1f}%)")
print(f"\n→ Biais naturel : {'Neutre' if 49 < up_count/total*100 < 51 else 'HAUSSIER' if up_count > down_count else 'BAISSIER'}")

# Calculer les indicateurs
print("\n" + "=" * 80)
print("2. CALCUL DES INDICATEURS")
print("=" * 80)

# EMAs
df['EMA8'] = df['close'].ewm(span=8, adjust=False).mean()
df['EMA21'] = df['close'].ewm(span=21, adjust=False).mean()
df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()

# RSI
delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.ewm(span=14, adjust=False).mean()
avg_loss = loss.ewm(span=14, adjust=False).mean()
rs = avg_gain / avg_loss
df['RSI'] = 100 - (100 / (1 + rs))

# Volume relatif
df['VOL_MA20'] = df['volume'].rolling(20).mean()
df['VOL_RATIO'] = df['volume'] / df['VOL_MA20']

# Momentum (variation sur 3 bougies)
df['MOMENTUM_3'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

# Direction de la bougie actuelle
df['current_up'] = df['close'] > df['open']

# ATR
df['TR'] = np.maximum(
    df['high'] - df['low'],
    np.maximum(
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    )
)
df['ATR'] = df['TR'].rolling(14).mean()
df['ATR_pct'] = df['ATR'] / df['close'] * 100

# Supprimer les NaN
df_clean = df.dropna().copy()
print(f"Données après calcul indicateurs : {len(df_clean)} bougies")

# Test des stratégies
print("\n" + "=" * 80)
print("3. TEST DES STRATEGIES (Win Rate pour prédire UP)")
print("=" * 80)

def test_strategy(condition, name):
    """Test une condition et retourne le win rate"""
    subset = df_clean[condition]
    if len(subset) < 100:
        return None, 0, 0
    win_rate = subset['direction_correct'].mean() * 100
    trades_per_day = len(subset) / ((df_clean['timestamp'].max() - df_clean['timestamp'].min()).days)
    return win_rate, len(subset), trades_per_day

strategies = []

# === Stratégie 1: Momentum simple ===
cond = df_clean['MOMENTUM_3'] > 0.1  # Momentum positif > 0.1%
wr, n, tpd = test_strategy(cond, "Momentum > 0.1%")
strategies.append(("Momentum > 0.1%", wr, n, tpd))

cond = df_clean['MOMENTUM_3'] > 0.2
wr, n, tpd = test_strategy(cond, "Momentum > 0.2%")
strategies.append(("Momentum > 0.2%", wr, n, tpd))

cond = df_clean['MOMENTUM_3'] > 0.3
wr, n, tpd = test_strategy(cond, "Momentum > 0.3%")
strategies.append(("Momentum > 0.3%", wr, n, tpd))

cond = df_clean['MOMENTUM_3'] > 0.5
wr, n, tpd = test_strategy(cond, "Momentum > 0.5%")
strategies.append(("Momentum > 0.5%", wr, n, tpd))

# === Stratégie 2: Tendance EMA ===
cond = (df_clean['close'] > df_clean['EMA8']) & (df_clean['EMA8'] > df_clean['EMA21'])
wr, n, tpd = test_strategy(cond, "Prix > EMA8 > EMA21")
strategies.append(("Prix > EMA8 > EMA21", wr, n, tpd))

cond = (df_clean['close'] > df_clean['EMA21']) & (df_clean['EMA21'] > df_clean['EMA50'])
wr, n, tpd = test_strategy(cond, "Prix > EMA21 > EMA50")
strategies.append(("Prix > EMA21 > EMA50", wr, n, tpd))

# === Stratégie 3: RSI ===
cond = (df_clean['RSI'] > 50) & (df_clean['RSI'] < 70)
wr, n, tpd = test_strategy(cond, "RSI 50-70")
strategies.append(("RSI 50-70", wr, n, tpd))

cond = (df_clean['RSI'] > 55) & (df_clean['RSI'] < 75)
wr, n, tpd = test_strategy(cond, "RSI 55-75")
strategies.append(("RSI 55-75", wr, n, tpd))

cond = (df_clean['RSI'] > 40) & (df_clean['RSI'] < 60)
wr, n, tpd = test_strategy(cond, "RSI 40-60 (neutre)")
strategies.append(("RSI 40-60", wr, n, tpd))

# === Stratégie 4: Volume ===
cond = df_clean['VOL_RATIO'] > 1.5
wr, n, tpd = test_strategy(cond, "Volume > 1.5x moyenne")
strategies.append(("Volume > 1.5x", wr, n, tpd))

cond = df_clean['VOL_RATIO'] > 2.0
wr, n, tpd = test_strategy(cond, "Volume > 2.0x moyenne")
strategies.append(("Volume > 2.0x", wr, n, tpd))

# === Stratégie 5: Bougie actuelle ===
cond = df_clean['current_up'] == True
wr, n, tpd = test_strategy(cond, "Bougie actuelle UP")
strategies.append(("Bougie UP", wr, n, tpd))

# === Stratégie 6: Combinaisons ===
cond = (df_clean['MOMENTUM_3'] > 0.2) & (df_clean['close'] > df_clean['EMA21'])
wr, n, tpd = test_strategy(cond, "Momentum + EMA21")
strategies.append(("Momentum 0.2% + EMA21", wr, n, tpd))

cond = (df_clean['MOMENTUM_3'] > 0.2) & (df_clean['RSI'] > 50) & (df_clean['RSI'] < 70)
wr, n, tpd = test_strategy(cond, "Momentum + RSI 50-70")
strategies.append(("Momentum + RSI 50-70", wr, n, tpd))

cond = (df_clean['close'] > df_clean['EMA8']) & (df_clean['EMA8'] > df_clean['EMA21']) & (df_clean['RSI'] > 50)
wr, n, tpd = test_strategy(cond, "EMA + RSI > 50")
strategies.append(("EMA Cross + RSI > 50", wr, n, tpd))

cond = (df_clean['MOMENTUM_3'] > 0.3) & (df_clean['VOL_RATIO'] > 1.2)
wr, n, tpd = test_strategy(cond, "Momentum 0.3% + Volume")
strategies.append(("Momentum 0.3% + Volume", wr, n, tpd))

cond = (df_clean['current_up']) & (df_clean['close'] > df_clean['EMA21'])
wr, n, tpd = test_strategy(cond, "Bougie UP + EMA21")
strategies.append(("Bougie UP + EMA21", wr, n, tpd))

# === Stratégie 7: Anti-retournement (continuation) ===
cond = (df_clean['current_up']) & (df_clean['MOMENTUM_3'] > 0) & (df_clean['RSI'] > 45) & (df_clean['RSI'] < 70)
wr, n, tpd = test_strategy(cond, "Continuation UP")
strategies.append(("Continuation UP", wr, n, tpd))

# === Stratégie 8: Force de la tendance ===
cond = (df_clean['close'] > df_clean['EMA8']) & (df_clean['EMA8'] > df_clean['EMA21']) & (df_clean['MOMENTUM_3'] > 0.15)
wr, n, tpd = test_strategy(cond, "Tendance forte")
strategies.append(("Tendance forte (EMA + Mom)", wr, n, tpd))

# === Stratégie 9: Volatilité faible (marché calme) ===
cond = (df_clean['ATR_pct'] < 1.5) & (df_clean['MOMENTUM_3'] > 0.1)
wr, n, tpd = test_strategy(cond, "Low ATR + Momentum")
strategies.append(("ATR < 1.5% + Momentum", wr, n, tpd))

# === Stratégie 10: Triple confirmation ===
cond = (
    (df_clean['close'] > df_clean['EMA21']) &
    (df_clean['MOMENTUM_3'] > 0.15) &
    (df_clean['RSI'] > 50) &
    (df_clean['RSI'] < 70)
)
wr, n, tpd = test_strategy(cond, "Triple: EMA + Mom + RSI")
strategies.append(("Triple: EMA + Mom + RSI", wr, n, tpd))

# Afficher les résultats triés par win rate
print("\n{:<35} {:>10} {:>10} {:>12}".format("STRATÉGIE", "WIN RATE", "TRADES", "TRADES/JOUR"))
print("-" * 70)

for name, wr, n, tpd in sorted(strategies, key=lambda x: x[1] if x[1] else 0, reverse=True):
    if wr is not None:
        status = "✅" if wr >= 55 else "⚠️" if wr >= 52 else "❌"
        print(f"{name:<35} {wr:>8.1f}% {n:>10} {tpd:>10.1f} {status}")

# Meilleure stratégie
print("\n" + "=" * 80)
print("4. MEILLEURE STRATÉGIE TROUVÉE")
print("=" * 80)

best = max([s for s in strategies if s[1] is not None], key=lambda x: x[1])
print(f"\nStratégie : {best[0]}")
print(f"Win Rate  : {best[1]:.2f}%")
print(f"Trades    : {best[2]}")
print(f"Trades/J  : {best[3]:.1f}")

# Analyse de la rentabilité avec payout Polymarket
print("\n" + "=" * 80)
print("5. SIMULATION POLYMARKET (Payout 1.9x)")
print("=" * 80)

def simulate_polymarket(win_rate, num_trades, bet_size=100):
    """Simule la rentabilité avec le payout Polymarket"""
    wins = int(num_trades * win_rate / 100)
    losses = num_trades - wins

    gain_per_win = bet_size * 0.9  # Payout 1.9x - mise
    loss_per_loss = bet_size  # Perd la mise

    total_gain = wins * gain_per_win
    total_loss = losses * loss_per_loss
    net_pnl = total_gain - total_loss
    roi = net_pnl / (bet_size * num_trades) * 100

    return {
        'wins': wins,
        'losses': losses,
        'total_gain': total_gain,
        'total_loss': total_loss,
        'net_pnl': net_pnl,
        'roi': roi
    }

# Simuler pour les meilleures stratégies (>52% win rate)
print("\nSimulation avec mise de $100 par trade :")
print("-" * 70)

good_strategies = [s for s in strategies if s[1] is not None and s[1] >= 50]
for name, wr, n, tpd in sorted(good_strategies, key=lambda x: x[1], reverse=True)[:10]:
    sim = simulate_polymarket(wr, n)
    print(f"\n{name}")
    print(f"  Win Rate: {wr:.1f}% | Trades: {n} | PnL: ${sim['net_pnl']:+,.0f} | ROI: {sim['roi']:+.2f}%")

# Calculer le seuil de rentabilité
print("\n" + "=" * 80)
print("6. SEUIL DE RENTABILITÉ")
print("=" * 80)

# Avec payout 1.9x : Win * 0.9 = Loss * 1
# Win * 0.9 = (1 - Win) * 1
# Win * 0.9 + Win = 1
# Win * 1.9 = 1
# Win = 1 / 1.9 = 52.63%
breakeven = 1 / 1.9 * 100
print(f"\nPour être rentable avec payout 1.9x, il faut > {breakeven:.2f}% de win rate")
print(f"Pour atteindre 55%, il faut un edge de +{55 - breakeven:.2f}%")

# Vérifier les stratégies rentables
profitable = [s for s in strategies if s[1] and s[1] > breakeven]
print(f"\n✅ Stratégies rentables trouvées : {len(profitable)}")
for name, wr, n, tpd in sorted(profitable, key=lambda x: x[1], reverse=True):
    edge = wr - breakeven
    print(f"  - {name}: {wr:.1f}% (edge: +{edge:.1f}%)")

print("\n" + "=" * 80)
