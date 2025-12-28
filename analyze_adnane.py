#!/usr/bin/env python3
"""
Analyse inverse: Comment Adnane fait $15k/mois avec $100/trade?
"""

BET = 100
TARGET = 15000
DAYS = 30

print("=" * 70)
print("🔍 ANALYSE INVERSE: Comment faire $15k/mois avec $100/trade?")
print("=" * 70)

# Calcul inverse
print("\n📊 SCÉNARIOS POSSIBLES POUR $15k/mois:")
print("-" * 70)
print(f"{'Entry':<8} {'WR':<8} {'PnL/trade':<12} {'Trades/jour':<15} {'Réaliste?'}")
print("-" * 70)

for entry in [0.53, 0.525, 0.52, 0.51, 0.50]:
    for wr in [0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60]:
        shares = BET / entry
        win_profit = shares - BET  # $1 per share if win
        pnl_per_trade = (wr * win_profit) + ((1 - wr) * (-BET))

        if pnl_per_trade > 0:
            trades_needed_day = (TARGET / DAYS) / pnl_per_trade

            # Réaliste = moins de 100 trades/jour avec WR atteignable
            if trades_needed_day < 100 and wr <= 0.58:
                status = "✅ POSSIBLE"
            elif trades_needed_day < 60:
                status = "🎯 OPTIMAL"
            else:
                status = "❌"

            if trades_needed_day < 120:
                print(f"{entry*100:.1f}¢     {wr*100:.0f}%     ${pnl_per_trade:.2f}        {trades_needed_day:.0f}              {status}")

print("\n" + "=" * 70)
print("🎯 CE QUE ADNANE FAIT PROBABLEMENT:")
print("=" * 70)

# Hypothèse Adnane: 52¢, 57-58% WR, ~50 trades/jour
scenarios_adnane = [
    ("52¢ + 57% WR + 50 trades/j", 0.52, 0.57, 50),
    ("52¢ + 58% WR + 45 trades/j", 0.52, 0.58, 45),
    ("51¢ + 56% WR + 55 trades/j", 0.51, 0.56, 55),
    ("52.5¢ + 58% WR + 50 trades/j", 0.525, 0.58, 50),
]

for name, entry, wr, tpd in scenarios_adnane:
    shares = BET / entry
    win_profit = shares - BET
    pnl_per_trade = (wr * win_profit) + ((1 - wr) * (-BET))
    pnl_month = pnl_per_trade * tpd * 30

    print(f"\n{name}:")
    print(f"   PnL/trade: ${pnl_per_trade:.2f}")
    print(f"   PnL/mois: ${pnl_month:,.0f}")

print("\n" + "=" * 70)
print("📊 COMPARAISON: TOI vs ADNANE (hypothèse)")
print("=" * 70)

# Toi actuellement
my_entry = 0.53
my_wr = 0.559
my_tpd = 45
my_shares = BET / my_entry
my_win = my_shares - BET
my_pnl_trade = (my_wr * my_win) + ((1 - my_wr) * (-BET))
my_pnl_month = my_pnl_trade * my_tpd * 30

# Adnane (hypothèse: 52¢, 58% WR, 50 trades/jour grâce à 1 bot par pair)
ad_entry = 0.52
ad_wr = 0.58
ad_tpd = 50
ad_shares = BET / ad_entry
ad_win = ad_shares - BET
ad_pnl_trade = (ad_wr * ad_win) + ((1 - ad_wr) * (-BET))
ad_pnl_month = ad_pnl_trade * ad_tpd * 30

print(f"""
                        TOI              ADNANE
Entry price:            {my_entry*100:.0f}¢              {ad_entry*100:.0f}¢
Win Rate:               {my_wr*100:.1f}%           {ad_wr*100:.0f}%
Trades/jour:            {my_tpd}               {ad_tpd}
PnL/trade:              ${my_pnl_trade:.2f}           ${ad_pnl_trade:.2f}
PnL/mois:               ${my_pnl_month:,.0f}          ${ad_pnl_month:,.0f}
""")

print("=" * 70)
print("🔑 DIFFÉRENCES CLÉS:")
print("=" * 70)
print(f"""
1. ENTRY PRICE: 52¢ vs 53¢
   → +{((1/0.52 - 1/0.53) / (1/0.53)) * 100:.1f}% de profit par win

2. WIN RATE: 58% vs 55.9%
   → La vraie différence! +2.1% WR = ÉNORME impact

3. TRADES/JOUR: 50 vs 45
   → 1 bot par pair = moins de latence = plus de fills

CONCLUSION: Le secret est le WIN RATE!
- Comment Adnane a 58%? Meilleure stratégie ou meilleur timing
- 1 bot par pair = réponse plus rapide = meilleurs prix
""")

print("=" * 70)
print("💡 PLAN D'ACTION:")
print("=" * 70)
print("""
OPTION 1: Améliorer ta stratégie (atteindre 58% WR)
   - Analyser les trades perdants
   - Ajouter des filtres (volume, volatilité)
   - Optimiser les paramètres RSI/Stoch par pair

OPTION 2: 4 bots séparés (1 bot = 1 pair)
   - Moins de latence
   - Meilleur timing d'entrée
   - Plus de trades capturés
   - Possiblement meilleur WR grâce à meilleurs prix

OPTION 3: Les deux!
   - Améliorer stratégie + 4 bots séparés
""")
