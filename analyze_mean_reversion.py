#!/usr/bin/env python3
"""
Analyse approfondie des stratégies de Mean Reversion
Objectif : Combiner les patterns pour atteindre 20+ trades/jour + 55%+ win rate
"""

import pandas as pd
import numpy as np

print("=" * 80)
print("STRATÉGIE OPTIMALE : MEAN REVERSION")
print("=" * 80)

df = pd.read_csv('/Users/mac/poly/data/historical/BTC_USDT_15m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

# Direction prochaine bougie
df['next_close'] = df['close'].shift(-1)
df['next_up'] = df['next_close'] > df['close']
df['next_down'] = df['next_close'] < df['close']

# Indicateurs
df['up'] = df['close'] > df['open']
df['down'] = df['close'] < df['open']

# RSI
delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
df['RSI'] = 100 - (100 / (1 + gain.ewm(span=14).mean() / loss.ewm(span=14).mean()))

# Volume
df['VOL_MA'] = df['volume'].rolling(20).mean()
df['VOL_RATIO'] = df['volume'] / df['VOL_MA']

# Momentum
df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

# === BOUGIES CONSÉCUTIVES ===
print("\n" + "=" * 80)
print("1. SÉQUENCES CONSÉCUTIVES (ANALYSE DÉTAILLÉE)")
print("=" * 80)

# Compter bougies DOWN consécutives
df['consec_down'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['down']:
        count += 1
    else:
        count = 0
    df.iloc[i, df.columns.get_loc('consec_down')] = count

# Compter bougies UP consécutives
df['consec_up'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['up']:
        count += 1
    else:
        count = 0
    df.iloc[i, df.columns.get_loc('consec_up')] = count

print("\n{:<40} {:>10} {:>10} {:>10}".format("PATTERN", "WIN RATE", "TRADES", "T/JOUR"))
print("-" * 75)

# Après N bougies DOWN → prédire UP
for n in range(2, 8):
    subset = df[df['consec_down'] >= n].dropna()
    if len(subset) >= 100:
        wr = subset['next_up'].mean() * 100
        tpd = len(subset) / 719
        status = "✅" if wr > 55 else "⚠️" if wr > 52.63 else ""
        print(f"{n} DOWN consécutives → Prédire UP       {wr:>8.1f}%  {len(subset):>9}  {tpd:>9.1f} {status}")

# Après N bougies UP → prédire DOWN
print()
for n in range(2, 8):
    subset = df[df['consec_up'] >= n].dropna()
    if len(subset) >= 100:
        wr = subset['next_down'].mean() * 100
        tpd = len(subset) / 719
        status = "✅" if wr > 55 else "⚠️" if wr > 52.63 else ""
        print(f"{n} UP consécutives → Prédire DOWN       {wr:>8.1f}%  {len(subset):>9}  {tpd:>9.1f} {status}")

# === RSI EXTRÊMES ===
print("\n" + "=" * 80)
print("2. RSI EXTRÊMES (SURACHAT/SURVENTE)")
print("=" * 80)

print("\n{:<40} {:>10} {:>10} {:>10}".format("CONDITION RSI", "WIN RATE", "TRADES", "T/JOUR"))
print("-" * 75)

# RSI survente → prédire UP
for rsi_level in [15, 20, 25, 30, 35]:
    subset = df[df['RSI'] < rsi_level].dropna()
    if len(subset) >= 100:
        wr = subset['next_up'].mean() * 100
        tpd = len(subset) / 719
        status = "✅" if wr > 55 else "⚠️" if wr > 52.63 else ""
        print(f"RSI < {rsi_level} → Prédire UP                   {wr:>8.1f}%  {len(subset):>9}  {tpd:>9.1f} {status}")

print()
# RSI surachat → prédire DOWN
for rsi_level in [65, 70, 75, 80, 85]:
    subset = df[df['RSI'] > rsi_level].dropna()
    if len(subset) >= 100:
        wr = subset['next_down'].mean() * 100
        tpd = len(subset) / 719
        status = "✅" if wr > 55 else "⚠️" if wr > 52.63 else ""
        print(f"RSI > {rsi_level} → Prédire DOWN                  {wr:>8.1f}%  {len(subset):>9}  {tpd:>9.1f} {status}")

# === COMBINAISON OPTIMALE ===
print("\n" + "=" * 80)
print("3. STRATÉGIE COMBINÉE OPTIMALE")
print("=" * 80)

# Signal UP : (N DOWN consécutives) OU (RSI < seuil)
# Signal DOWN : (N UP consécutives) OU (RSI > seuil)

print("\nTest de combinaisons UP + DOWN simultanées :\n")

best_combo = None
best_wr = 0
best_tpd = 0

for down_consec in [2, 3, 4]:
    for up_consec in [2, 3, 4]:
        for rsi_low in [25, 30, 35]:
            for rsi_high in [65, 70, 75]:
                # Signaux UP
                cond_up = (df['consec_down'] >= down_consec) | (df['RSI'] < rsi_low)
                # Signaux DOWN
                cond_down = (df['consec_up'] >= up_consec) | (df['RSI'] > rsi_high)

                # Combiner
                signals = pd.DataFrame()
                signals['timestamp'] = df['timestamp']
                signals['signal'] = 'NONE'
                signals.loc[cond_up, 'signal'] = 'UP'
                signals.loc[cond_down, 'signal'] = 'DOWN'
                signals['correct'] = False

                # Vérifier UP corrects
                signals.loc[(signals['signal'] == 'UP') & df['next_up'], 'correct'] = True
                # Vérifier DOWN corrects
                signals.loc[(signals['signal'] == 'DOWN') & df['next_down'], 'correct'] = True

                # Calculer stats
                active_signals = signals[signals['signal'] != 'NONE']
                if len(active_signals) >= 1000:
                    wr = active_signals['correct'].mean() * 100
                    tpd = len(active_signals) / 719

                    if wr > best_wr and tpd >= 15:  # Min 15 trades/jour
                        best_wr = wr
                        best_tpd = tpd
                        best_combo = {
                            'down_consec': down_consec,
                            'up_consec': up_consec,
                            'rsi_low': rsi_low,
                            'rsi_high': rsi_high,
                            'wr': wr,
                            'trades': len(active_signals),
                            'tpd': tpd
                        }

if best_combo:
    print(f"✅ MEILLEURE COMBINAISON TROUVÉE :")
    print(f"   - Signal UP  : {best_combo['down_consec']}+ DOWN consécutives OU RSI < {best_combo['rsi_low']}")
    print(f"   - Signal DOWN: {best_combo['up_consec']}+ UP consécutives OU RSI > {best_combo['rsi_high']}")
    print(f"   - Win Rate: {best_combo['wr']:.2f}%")
    print(f"   - Trades: {best_combo['trades']}")
    print(f"   - Trades/jour: {best_combo['tpd']:.1f}")
else:
    print("Aucune combinaison optimale trouvée avec >= 15 trades/jour")

# === STRATÉGIE FINALE SIMPLIFIÉE ===
print("\n" + "=" * 80)
print("4. STRATÉGIE FINALE SIMPLIFIÉE (3 INDICATEURS)")
print("=" * 80)

# Indicateur 1: Bougies consécutives
# Indicateur 2: RSI
# Indicateur 3: Confirmation momentum (optionnel)

print("\nTest stratégie finale : Mean Reversion Combinée\n")

# Signal UP si:
# - 3+ bougies DOWN consécutives
# - OU RSI < 30
# Filtre: momentum négatif (confirme la survente)

cond_up = (
    ((df['consec_down'] >= 3) | (df['RSI'] < 30)) &
    (df['momentum'] < 0)  # Confirmation: momentum négatif
)

# Signal DOWN si:
# - 3+ bougies UP consécutives
# - OU RSI > 70
# Filtre: momentum positif (confirme le surachat)

cond_down = (
    ((df['consec_up'] >= 3) | (df['RSI'] > 70)) &
    (df['momentum'] > 0)  # Confirmation: momentum positif
)

# Calculer résultats
signals = pd.DataFrame()
signals['timestamp'] = df['timestamp']
signals['signal'] = 'NONE'
signals.loc[cond_up, 'signal'] = 'UP'
signals.loc[cond_down, 'signal'] = 'DOWN'
signals['correct'] = False
signals.loc[(signals['signal'] == 'UP') & df['next_up'], 'correct'] = True
signals.loc[(signals['signal'] == 'DOWN') & df['next_down'], 'correct'] = True

active = signals[signals['signal'] != 'NONE']
up_signals = signals[signals['signal'] == 'UP']
down_signals = signals[signals['signal'] == 'DOWN']

print("RÉSULTATS STRATÉGIE FINALE :")
print("-" * 50)

if len(up_signals) > 0:
    up_wr = up_signals['correct'].mean() * 100
    print(f"  Signaux UP:   {len(up_signals):>6} | Win Rate: {up_wr:>6.2f}%")

if len(down_signals) > 0:
    down_wr = down_signals['correct'].mean() * 100
    print(f"  Signaux DOWN: {len(down_signals):>6} | Win Rate: {down_wr:>6.2f}%")

if len(active) > 0:
    total_wr = active['correct'].mean() * 100
    tpd = len(active) / 719
    print(f"\n  TOTAL:        {len(active):>6} | Win Rate: {total_wr:>6.2f}%")
    print(f"  Trades/jour:  {tpd:.1f}")

    # Rentabilité Polymarket
    wins = active['correct'].sum()
    losses = len(active) - wins
    pnl = wins * 90 - losses * 100  # Gain 90$ si win, perte 100$ si loss
    roi = pnl / (len(active) * 100) * 100

    print(f"\n  Simulation Polymarket (mise $100) :")
    print(f"    Wins: {wins} | Losses: {losses}")
    print(f"    PnL total: ${pnl:+,.0f}")
    print(f"    ROI: {roi:+.2f}%")

    if total_wr >= 55 and tpd >= 20:
        print(f"\n  ✅ OBJECTIF ATTEINT : {total_wr:.1f}% win rate + {tpd:.0f} trades/jour")
    elif total_wr >= 52.63:
        print(f"\n  ⚠️ RENTABLE mais objectifs partiellement atteints")
    else:
        print(f"\n  ❌ Stratégie non rentable")

# === TEST SANS FILTRE MOMENTUM ===
print("\n" + "=" * 80)
print("5. VARIANTES SANS FILTRE MOMENTUM")
print("=" * 80)

# Version plus simple (sans filtre momentum)
cond_up_simple = (df['consec_down'] >= 3) | (df['RSI'] < 30)
cond_down_simple = (df['consec_up'] >= 3) | (df['RSI'] > 70)

signals_simple = pd.DataFrame()
signals_simple['signal'] = 'NONE'
signals_simple.loc[cond_up_simple, 'signal'] = 'UP'
signals_simple.loc[cond_down_simple, 'signal'] = 'DOWN'
signals_simple['correct'] = False
signals_simple.loc[(signals_simple['signal'] == 'UP') & df['next_up'], 'correct'] = True
signals_simple.loc[(signals_simple['signal'] == 'DOWN') & df['next_down'], 'correct'] = True

active_simple = signals_simple[signals_simple['signal'] != 'NONE']

if len(active_simple) > 0:
    wr = active_simple['correct'].mean() * 100
    tpd = len(active_simple) / 719
    print(f"\nVersion simplifiée (sans filtre momentum) :")
    print(f"  Trades: {len(active_simple)} | Win Rate: {wr:.2f}% | Trades/jour: {tpd:.1f}")

# Version avec seuils ajustés
print("\nTest de différents seuils :\n")
print("{:<50} {:>10} {:>10} {:>10}".format("CONFIGURATION", "WIN RATE", "TRADES", "T/JOUR"))
print("-" * 85)

for consec in [2, 3, 4]:
    for rsi_low in [25, 30, 35]:
        for rsi_high in [65, 70, 75]:
            cond_up = (df['consec_down'] >= consec) | (df['RSI'] < rsi_low)
            cond_down = (df['consec_up'] >= consec) | (df['RSI'] > rsi_high)

            signals = pd.DataFrame()
            signals['signal'] = 'NONE'
            signals.loc[cond_up, 'signal'] = 'UP'
            signals.loc[cond_down, 'signal'] = 'DOWN'
            signals['correct'] = False
            signals.loc[(signals['signal'] == 'UP') & df['next_up'], 'correct'] = True
            signals.loc[(signals['signal'] == 'DOWN') & df['next_down'], 'correct'] = True

            active = signals[signals['signal'] != 'NONE']
            if len(active) > 500:
                wr = active['correct'].mean() * 100
                tpd = len(active) / 719
                status = "✅ OBJECTIF" if wr >= 55 and tpd >= 20 else "⚠️" if wr >= 52.63 else ""
                name = f"{consec}+ consec + RSI {rsi_low}/{rsi_high}"
                print(f"{name:<50} {wr:>8.1f}%  {len(active):>9}  {tpd:>9.1f} {status}")

print("\n" + "=" * 80)
print("6. RÉSUMÉ FINAL")
print("=" * 80)

print("""
STRATÉGIE RECOMMANDÉE : MEAN REVERSION

Règles de trading :
1. Signal UP (acheter "Up" sur Polymarket) :
   - 3+ bougies DOWN consécutives
   - OU RSI < 30

2. Signal DOWN (acheter "Down" sur Polymarket) :
   - 3+ bougies UP consécutives
   - OU RSI > 70

Indicateurs utilisés :
1. Direction des bougies (UP/DOWN)
2. RSI(14)
3. [Optionnel] Momentum pour confirmation

Timing : Entrée 8 secondes avant la clôture de la bougie 15m
""")

print("=" * 80)
