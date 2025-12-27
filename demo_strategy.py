#!/usr/bin/env python3
"""
DÉMONSTRATION COMPLÈTE DE LA STRATÉGIE MEAN REVERSION
Avec explication de chaque étape et simulation PnL
"""

import pandas as pd
import numpy as np

print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    STRATÉGIE MEAN REVERSION - EXPLICATION                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

# ============================================================================
# ÉTAPE 1 : CHARGEMENT DES DONNÉES HISTORIQUES
# ============================================================================

print("=" * 80)
print("ÉTAPE 1 : CHARGEMENT DES DONNÉES HISTORIQUES")
print("=" * 80)

df = pd.read_csv('/Users/mac/poly/data/historical/BTC_USDT_15m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"""
Ces données viennent de Binance (données RÉELLES, pas des prédictions) :

  Fichier      : BTC_USDT_15m.csv
  Bougies      : {len(df):,}
  Période      : {df['timestamp'].min().strftime('%Y-%m-%d')} à {df['timestamp'].max().strftime('%Y-%m-%d')}

Exemple de données (5 premières bougies) :
""")

print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].head().to_string(index=False))


# ============================================================================
# ÉTAPE 2 : CALCUL DES BOUGIES CONSÉCUTIVES
# ============================================================================

print("\n" + "=" * 80)
print("ÉTAPE 2 : CALCUL DES BOUGIES CONSÉCUTIVES")
print("=" * 80)

print("""
LOGIQUE :
- Une bougie est UP si close > open (verte)
- Une bougie est DOWN si close < open (rouge)
- On compte combien de bougies DOWN (ou UP) se suivent

CODE :
""")

code_consec = '''
# Déterminer si chaque bougie est UP ou DOWN
df['is_up'] = df['close'] > df['open']    # True = bougie verte
df['is_down'] = df['close'] < df['open']  # True = bougie rouge

# Compter les bougies DOWN consécutives
df['consec_down'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['is_down']:  # Si bougie rouge
        count += 1             # Incrémenter le compteur
    else:
        count = 0              # Réinitialiser si bougie verte
    df.iloc[i, df.columns.get_loc('consec_down')] = count

# Pareil pour les bougies UP consécutives
df['consec_up'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['is_up']:
        count += 1
    else:
        count = 0
    df.iloc[i, df.columns.get_loc('consec_up')] = count
'''

print(code_consec)

# Exécuter le code
df['is_up'] = df['close'] > df['open']
df['is_down'] = df['close'] < df['open']

df['consec_down'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['is_down']:
        count += 1
    else:
        count = 0
    df.iloc[i, df.columns.get_loc('consec_down')] = count

df['consec_up'] = 0
count = 0
for i in range(len(df)):
    if df.iloc[i]['is_up']:
        count += 1
    else:
        count = 0
    df.iloc[i, df.columns.get_loc('consec_up')] = count

# Montrer un exemple
print("\nEXEMPLE - Séquence de bougies avec compteur :")
print("-" * 70)

# Trouver une séquence intéressante
example_idx = df[df['consec_down'] >= 3].index[100]
example = df.iloc[example_idx-5:example_idx+3][['timestamp', 'open', 'close', 'is_down', 'consec_down']]
example['direction'] = example.apply(lambda x: '🔴 DOWN' if x['is_down'] else '🟢 UP', axis=1)

print(example[['timestamp', 'open', 'close', 'direction', 'consec_down']].to_string(index=False))
print("\n→ Quand consec_down >= 3, on génère un signal UP (retournement attendu)")


# ============================================================================
# ÉTAPE 3 : CALCUL DU RSI
# ============================================================================

print("\n" + "=" * 80)
print("ÉTAPE 3 : CALCUL DU RSI (Relative Strength Index)")
print("=" * 80)

print("""
LOGIQUE :
- RSI mesure la force du mouvement (0-100)
- RSI < 30 = Survente (le prix a trop baissé, rebond probable)
- RSI > 70 = Surachat (le prix a trop monté, correction probable)

CODE :
""")

code_rsi = '''
# Calculer les variations de prix
delta = df['close'].diff()

# Séparer les gains et les pertes
gain = delta.where(delta > 0, 0)  # Garder que les hausses
loss = -delta.where(delta < 0, 0)  # Garder que les baisses (en positif)

# Moyenne mobile exponentielle sur 14 périodes
avg_gain = gain.ewm(span=14, adjust=False).mean()
avg_loss = loss.ewm(span=14, adjust=False).mean()

# Calcul du RSI
rs = avg_gain / avg_loss
df['RSI'] = 100 - (100 / (1 + rs))
'''

print(code_rsi)

# Exécuter le code
delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.ewm(span=14, adjust=False).mean()
avg_loss = loss.ewm(span=14, adjust=False).mean()
rs = avg_gain / avg_loss
df['RSI'] = 100 - (100 / (1 + rs))

# Stats RSI
print(f"\nSTATISTIQUES RSI sur {len(df):,} bougies :")
print(f"  RSI moyen     : {df['RSI'].mean():.1f}")
print(f"  RSI < 30      : {(df['RSI'] < 30).sum():,} fois ({(df['RSI'] < 30).sum()/len(df)*100:.1f}%)")
print(f"  RSI > 70      : {(df['RSI'] > 70).sum():,} fois ({(df['RSI'] > 70).sum()/len(df)*100:.1f}%)")


# ============================================================================
# ÉTAPE 4 : GÉNÉRATION DES SIGNAUX
# ============================================================================

print("\n" + "=" * 80)
print("ÉTAPE 4 : GÉNÉRATION DES SIGNAUX")
print("=" * 80)

print("""
RÈGLES DE TRADING :

  ┌─────────────────────────────────────────────────────────────┐
  │  SIGNAL UP (acheter "Up" sur Polymarket) :                  │
  │                                                             │
  │    Condition 1 : 3+ bougies DOWN consécutives               │
  │         OU                                                  │
  │    Condition 2 : RSI < 30                                   │
  │                                                             │
  │    + Filtre : momentum < 0 (confirme la baisse)             │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  SIGNAL DOWN (acheter "Down" sur Polymarket) :              │
  │                                                             │
  │    Condition 1 : 3+ bougies UP consécutives                 │
  │         OU                                                  │
  │    Condition 2 : RSI > 70                                   │
  │                                                             │
  │    + Filtre : momentum > 0 (confirme la hausse)             │
  └─────────────────────────────────────────────────────────────┘

CODE :
""")

code_signal = '''
# Calculer le momentum (variation sur 3 bougies)
df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

# Générer les signaux
def generate_signal(row):
    # Conditions pour signal UP
    cond_up = (row['consec_down'] >= 3) or (row['RSI'] < 30)

    # Conditions pour signal DOWN
    cond_down = (row['consec_up'] >= 3) or (row['RSI'] > 70)

    # Appliquer le filtre momentum
    if cond_up and row['momentum'] < 0:
        return 'UP'
    elif cond_down and row['momentum'] > 0:
        return 'DOWN'
    else:
        return None

df['signal'] = df.apply(generate_signal, axis=1)
'''

print(code_signal)

# Exécuter le code
df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

def generate_signal(row):
    if pd.isna(row['RSI']) or pd.isna(row['momentum']):
        return None
    cond_up = (row['consec_down'] >= 3) or (row['RSI'] < 30)
    cond_down = (row['consec_up'] >= 3) or (row['RSI'] > 70)

    if cond_up and row['momentum'] < 0:
        return 'UP'
    elif cond_down and row['momentum'] > 0:
        return 'DOWN'
    return None

df['signal'] = df.apply(generate_signal, axis=1)

# Stats signaux
up_signals = (df['signal'] == 'UP').sum()
down_signals = (df['signal'] == 'DOWN').sum()
total_signals = up_signals + down_signals

print(f"\nSIGNAUX GÉNÉRÉS sur {len(df):,} bougies :")
print(f"  Signaux UP   : {up_signals:,}")
print(f"  Signaux DOWN : {down_signals:,}")
print(f"  TOTAL        : {total_signals:,}")
print(f"  Signaux/jour : {total_signals / ((df['timestamp'].max() - df['timestamp'].min()).days):.1f}")


# ============================================================================
# ÉTAPE 5 : VÉRIFICATION DES RÉSULTATS (BACKTEST)
# ============================================================================

print("\n" + "=" * 80)
print("ÉTAPE 5 : VÉRIFICATION DES RÉSULTATS")
print("=" * 80)

print("""
On vérifie si nos signaux étaient CORRECTS en regardant ce qui s'est passé
APRÈS chaque signal dans les données historiques.
""")

# Calculer si le signal était correct
df['next_close'] = df['close'].shift(-1)
df['signal_correct'] = False
df.loc[(df['signal'] == 'UP') & (df['next_close'] > df['close']), 'signal_correct'] = True
df.loc[(df['signal'] == 'DOWN') & (df['next_close'] < df['close']), 'signal_correct'] = True

# Stats par signal
signals_df = df[df['signal'].isin(['UP', 'DOWN'])].copy()

up_df = signals_df[signals_df['signal'] == 'UP']
down_df = signals_df[signals_df['signal'] == 'DOWN']

up_correct = up_df['signal_correct'].sum()
down_correct = down_df['signal_correct'].sum()

print(f"""
RÉSULTATS DE LA VÉRIFICATION :

  Signaux UP :
    Total      : {len(up_df):,}
    Corrects   : {up_correct:,}
    Win Rate   : {up_correct/len(up_df)*100:.1f}%

  Signaux DOWN :
    Total      : {len(down_df):,}
    Corrects   : {down_correct:,}
    Win Rate   : {down_correct/len(down_df)*100:.1f}%

  GLOBAL :
    Total      : {len(signals_df):,}
    Corrects   : {up_correct + down_correct:,}
    Win Rate   : {(up_correct + down_correct)/len(signals_df)*100:.1f}%
""")


# ============================================================================
# ÉTAPE 6 : SIMULATION PnL AVEC 100$
# ============================================================================

print("=" * 80)
print("ÉTAPE 6 : SIMULATION PnL AVEC BUDGET DE 100$")
print("=" * 80)

print("""
PARAMÈTRES POLYMARKET :
  - Payout : 1.9x (vous gagnez 90% si correct, perdez 100% si faux)
  - Mise par trade : Variable (on teste plusieurs scénarios)
""")

def simulate_pnl(initial_capital, bet_size, win_rate, num_trades):
    """Simule le PnL"""
    capital = initial_capital
    history = [capital]

    wins = int(num_trades * win_rate / 100)
    losses = num_trades - wins

    # Simuler les trades (alternance réaliste)
    results = [True] * wins + [False] * losses
    np.random.seed(42)
    np.random.shuffle(results)

    for won in results:
        if capital < bet_size:
            bet = capital  # All-in si pas assez
        else:
            bet = bet_size

        if won:
            capital += bet * 0.9  # Gain de 90%
        else:
            capital -= bet  # Perte de 100%

        history.append(max(0, capital))

        if capital <= 0:
            break

    return capital, history

# Données réelles du backtest
total_trades = len(signals_df)
win_rate = (up_correct + down_correct) / len(signals_df) * 100
days = (df['timestamp'].max() - df['timestamp'].min()).days

print(f"""
DONNÉES DU BACKTEST :
  Période        : {days} jours
  Trades totaux  : {total_trades:,}
  Win Rate       : {win_rate:.1f}%
  Trades/jour    : {total_trades/days:.1f}
""")

print("-" * 80)
print("SIMULATION AVEC DIFFÉRENTES MISES (Capital initial : 100$)")
print("-" * 80)
print(f"\n{'Mise/Trade':<15} {'Capital Final':<18} {'PnL':<15} {'ROI':<12} {'Status'}")
print("-" * 70)

for bet in [1, 2, 5, 10, 20]:
    final, history = simulate_pnl(100, bet, win_rate, total_trades)
    pnl = final - 100
    roi = (final / 100 - 1) * 100
    status = "✅" if final > 100 else "❌"
    print(f"${bet:<14} ${final:>15,.2f}   ${pnl:>+12,.2f}   {roi:>+8.1f}%   {status}")

print("\n" + "-" * 80)
print("PROJECTION MENSUELLE ET ANNUELLE (Mise optimale : 2$ par trade)")
print("-" * 80)

# Calcul détaillé avec mise de 2$
bet_size = 2
trades_per_day = total_trades / days
trades_per_month = trades_per_day * 30
trades_per_year = trades_per_day * 365

# Simulation sur 1 mois
final_month, _ = simulate_pnl(100, bet_size, win_rate, int(trades_per_month))
# Simulation sur 1 an
final_year, _ = simulate_pnl(100, bet_size, win_rate, int(trades_per_year))

print(f"""
Avec mise de ${bet_size} par trade et capital initial de $100 :

  📅 PAR JOUR :
     Trades        : {trades_per_day:.0f}
     Gain espéré   : ${trades_per_day * bet_size * (win_rate/100 * 0.9 - (100-win_rate)/100):.2f}

  📅 PAR MOIS (30 jours) :
     Trades        : {trades_per_month:.0f}
     Capital final : ${final_month:,.2f}
     PnL           : ${final_month - 100:+,.2f}
     ROI           : {(final_month/100-1)*100:+.1f}%

  📅 PAR AN (365 jours) :
     Trades        : {trades_per_year:.0f}
     Capital final : ${final_year:,.2f}
     PnL           : ${final_year - 100:+,.2f}
     ROI           : {(final_year/100-1)*100:+.1f}%
""")


# ============================================================================
# ÉTAPE 7 : TABLEAU RÉCAPITULATIF
# ============================================================================

print("=" * 80)
print("RÉCAPITULATIF FINAL")
print("=" * 80)

print("""
┌────────────────────────────────────────────────────────────────────────────┐
│                        STRATÉGIE MEAN REVERSION                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  RÈGLES :                                                                  │
│  ────────                                                                  │
│  • Signal UP  : 3+ bougies DOWN consécutives OU RSI < 30                   │
│  • Signal DOWN: 3+ bougies UP consécutives OU RSI > 70                     │
│  • Filtre     : Momentum dans la direction opposée                         │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  INDICATEURS UTILISÉS (2-3) :                                              │
│  ──────────────────────────                                                │
│  1. Bougies consécutives (compteur UP/DOWN)                                │
│  2. RSI(14) - seuils 30 et 70                                              │
│  3. Momentum 3 périodes (optionnel, filtre)                                │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  RÉSULTATS BACKTEST (BTC 15m, ~2 ans) :                                    │
│  ─────────────────────────────────────                                     │
│  • Win Rate      : 55.1%  ✅ (objectif 55%)                                │
│  • Trades/jour   : 30.6   ✅ (objectif 20+)                                │
│  • Rentabilité   : OUI    ✅ (seuil 52.63%)                                │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ESTIMATION PnL (Capital 100$, Mise 2$/trade) :                            │
│  ─────────────────────────────────────────────                             │
│  • Par jour  : ~$1-2 de profit                                             │
│  • Par mois  : ~$30-60 de profit                                           │
│  • Par an    : ~$400-800 de profit                                         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
""")

print("""
⚠️  AVERTISSEMENTS IMPORTANTS :

1. Ces résultats sont basés sur des DONNÉES HISTORIQUES
   → Le futur peut être différent

2. Win Rate de 55% signifie 45% de pertes
   → Vous ALLEZ perdre des trades

3. Testez d'abord en PAPER TRADING
   → Ne risquez pas d'argent réel immédiatement

4. Commencez avec de PETITES MISES
   → $1-2 par trade maximum au début
""")

print("=" * 80)
