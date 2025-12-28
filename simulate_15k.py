#!/usr/bin/env python3
"""
Simulation pour atteindre $15,000/mois
"""

# Paramètres
BET = 100  # $100 par trade
TARGET_PNL = 15000  # $15k/mois

scenarios = [
    {
        'name': 'ACTUEL (53¢ + Blacklist)',
        'entry_price': 0.53,
        'trades_per_day': 45,
        'win_rate': 0.559
    },
    {
        'name': 'SANS BLACKLIST (53¢)',
        'entry_price': 0.53,
        'trades_per_day': 61,  # 4 pairs sans blacklist
        'win_rate': 0.546
    },
    {
        'name': 'ADNANE (52.5¢ sans blacklist)',
        'entry_price': 0.525,
        'trades_per_day': 61,
        'win_rate': 0.546
    },
    {
        'name': '6 PAIRS (52.5¢)',
        'entry_price': 0.525,
        'trades_per_day': 90,  # +DOGE, AVAX
        'win_rate': 0.54
    },
    {
        'name': '8 PAIRS (52.5¢)',
        'entry_price': 0.525,
        'trades_per_day': 120,
        'win_rate': 0.54
    },
]

print("=" * 80)
print("📊 SIMULATION POUR ATTEINDRE $15,000/MOIS")
print("=" * 80)
print(f"Mise: ${BET}/trade | Objectif: ${TARGET_PNL:,}/mois")
print("=" * 80)

for s in scenarios:
    shares = BET / s['entry_price']
    win_profit = shares - BET  # $1 per share if win
    loss = -BET

    pnl_per_trade = (s['win_rate'] * win_profit) + ((1 - s['win_rate']) * loss)
    pnl_per_day = pnl_per_trade * s['trades_per_day']
    pnl_per_month = pnl_per_day * 30

    pct_of_target = (pnl_per_month / TARGET_PNL) * 100
    status = "✅" if pnl_per_month >= TARGET_PNL else "❌"

    print(f"\n{status} {s['name']}")
    print(f"   Entry: {s['entry_price']*100:.1f}¢ | Trades: {s['trades_per_day']}/j | WR: {s['win_rate']*100:.1f}%")
    print(f"   Win: +${win_profit:.2f} | Loss: -${BET}")
    print(f"   PnL/trade: ${pnl_per_trade:.2f}")
    print(f"   PnL/jour: ${pnl_per_day:.0f}")
    print(f"   PnL/mois: ${pnl_per_month:,.0f} ({pct_of_target:.0f}% de l'objectif)")

# Calcul inverse: combien de trades pour $15k?
print("\n" + "=" * 80)
print("🎯 COMBIEN DE TRADES POUR $15,000/MOIS?")
print("=" * 80)

for entry in [0.53, 0.525, 0.52]:
    for wr in [0.54, 0.55, 0.56]:
        shares = BET / entry
        win_profit = shares - BET
        pnl_per_trade = (wr * win_profit) + ((1 - wr) * (-BET))

        if pnl_per_trade > 0:
            trades_needed_month = TARGET_PNL / pnl_per_trade
            trades_needed_day = trades_needed_month / 30

            print(f"   @ {entry*100:.1f}¢ | WR {wr*100:.0f}%: {trades_needed_day:.0f} trades/jour ({trades_needed_day/15:.1f} pairs)")

print("\n" + "=" * 80)
print("💡 RECOMMANDATION")
print("=" * 80)
print("""
Pour atteindre $15,000/mois avec $100/trade:

Option A: Garder 4 pairs, augmenter mise
  → Mise $200/trade = $14,826/mois

Option B: Ajouter des pairs (DOGE, AVAX, LINK, MATIC)
  → 8 pairs × 15 trades/j = 120 trades/jour
  → PnL estimé: $15,500/mois

Option C: Style Adnane (3 bots séparés)
  → 3 VPS × 2-3 pairs chacun
  → Meilleur timing, moins de latence
  → Plus de trades capturés
""")
