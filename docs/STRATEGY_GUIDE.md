# Bot Polymarket - Guide Complet de la Stratégie HYBRID

## 1. CONCEPT GÉNÉRAL

Tu trades sur **Polymarket** des marchés binaires "Up or Down" sur crypto:
- **BTC** va-t-il monter ou descendre dans les 15 prochaines minutes?
- **ETH** va-t-il monter ou descendre dans les 15 prochaines minutes?
- **XRP** va-t-il monter ou descendre dans les 15 prochaines minutes?

**Paiement:** Si tu as raison → tu récupères $1 par share. Si tu as tort → tu perds ta mise.

---

## 2. STRATÉGIE: MEAN REVERSION (Retour à la Moyenne)

**Principe:** Après un mouvement extrême, le prix tend à revenir vers sa moyenne.

| Condition | Action |
|-----------|--------|
| Prix monte trop haut | Il va probablement redescendre → Parie **DOWN** |
| Prix descend trop bas | Il va probablement remonter → Parie **UP** |

---

## 3. INDICATEURS UTILISÉS

### A) RSI (Relative Strength Index)

Le RSI mesure la force relative des mouvements de prix récents. Il varie de 0 à 100.

| RSI | Interprétation | Signal |
|-----|----------------|--------|
| < 35 | Survendu (trop de ventes) | **UP** |
| > 65 | Suracheté (trop d'achats) | **DOWN** |
| 35-65 | Zone neutre | Pas de signal |

**Formule:**
```
RSI = 100 - (100 / (1 + RS))
RS = Moyenne des gains / Moyenne des pertes
```

### B) Stochastic %K

Compare le prix de clôture actuel au range haut/bas sur une période donnée.

| Stochastic | Interprétation | Signal |
|------------|----------------|--------|
| < 30 | Prix proche du bas | **UP** |
| > 70 | Prix proche du haut | **DOWN** |

**Formule:**
```
%K = 100 × (Close - Low_n) / (High_n - Low_n)
```

### C) Bougies Consécutives

Compte le nombre de bougies allant dans la même direction.

| Condition | Signal |
|-----------|--------|
| 3+ bougies DOWN consécutives | Retournement probable → **UP** |
| 3+ bougies UP consécutives | Retournement probable → **DOWN** |

---

## 4. CONFIGURATION HYBRID PAR SYMBOLE

La stratégie HYBRID utilise des paramètres différents pour chaque crypto:

### BTC (Bitcoin)
| Paramètre | Valeur |
|-----------|--------|
| RSI Period | 7 |
| RSI Oversold | < 35 |
| RSI Overbought | > 65 |
| Stoch Period | 5 |
| Stoch Oversold | < 30 |
| Stoch Overbought | > 70 |
| Consec Threshold | 1 |
| **Trades attendus/jour** | ~40 |
| **Win Rate attendu** | 56% |

### ETH (Ethereum)
| Paramètre | Valeur |
|-----------|--------|
| RSI Period | 7 |
| RSI Oversold | < 35 |
| RSI Overbought | > 65 |
| Stoch Period | 5 |
| Stoch Oversold | < 30 |
| Stoch Overbought | > 70 |
| Consec Threshold | 1 |
| **Trades attendus/jour** | ~40 |
| **Win Rate attendu** | 56% |

### XRP (Ripple)
| Paramètre | Valeur |
|-----------|--------|
| RSI Period | 5 |
| RSI Oversold | < 25 |
| RSI Overbought | > 75 |
| Stoch Period | 5 |
| Stoch Oversold | < 20 |
| Stoch Overbought | > 80 |
| Consec Threshold | 2 |
| **Trades attendus/jour** | ~18 |
| **Win Rate attendu** | 55% |

**Pourquoi XRP est différent?**
- XRP est plus volatile
- Configuration plus stricte (RSI 25/75 au lieu de 35/65)
- Nécessite 2 bougies consécutives en plus des indicateurs

---

## 5. GÉNÉRATION DES SIGNAUX

### Signal UP (acheter "le prix va monter")
```
Pour BTC/ETH:
  RSI < 35 ET Stoch < 30

Pour XRP:
  RSI < 25 ET Stoch < 20 ET consec_down >= 2
```

### Signal DOWN (acheter "le prix va baisser")
```
Pour BTC/ETH:
  RSI > 65 ET Stoch > 70

Pour XRP:
  RSI > 75 ET Stoch > 80 ET consec_up >= 2
```

---

## 6. TIMING: -8 SECONDES

Le bot analyse le marché **8 secondes avant** la fin de chaque bougie 15 minutes.

```
Bougie 15m: 18:00:00 → 18:14:59
                            │
                    18:14:52 = Analyse (-8 sec)
                            │
                    Signal détecté? → Placer ordre
                            │
                    18:15:00 = Nouvelle bougie commence
                            │
                    18:30:00 = Résolution du marché
```

**Pourquoi -8 secondes?**
1. Avoir les données les plus récentes possibles
2. Placer l'ordre AVANT que le nouveau marché commence
3. Trader sur le marché de la PROCHAINE bougie 15m

---

## 7. FLUX D'EXÉCUTION COMPLET

```
┌─────────────────────────────────────────────────────────┐
│  1. ATTENDRE                                            │
│     → Calculer temps jusqu'à -8 sec avant bougie 15m    │
│     → sleep(temps)                                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  2. RÉCUPÉRER DONNÉES (Binance)                         │
│     → fetch_ohlcv('BTC/USDT', '15m', limit=50)          │
│     → fetch_ohlcv('ETH/USDT', '15m', limit=50)          │
│     → fetch_ohlcv('XRP/USDT', '15m', limit=50)          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  3. CALCULER INDICATEURS (pour chaque symbole)          │
│     → RSI avec période configurée                       │
│     → Stochastic %K                                     │
│     → Bougies consécutives                              │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  4. GÉNÉRER SIGNAL                                      │
│     → Vérifier conditions RSI + Stoch (+ consec)        │
│     → Signal UP, DOWN, ou rien                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  5. VÉRIFIER COOLDOWN                                   │
│     → Dernier trade sur ce symbole > 15 min?            │
│     → Si non, skip ce symbole                           │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  6. PLACER ORDRE (Polymarket)                           │
│     → Trouver le marché actif (ex: BTC Up/Down 15m)     │
│     → Vérifier prix <= 50¢                              │
│     → Créer ordre limite: 5 shares @ 50¢ max            │
│     → Poster l'ordre via API                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  7. NOTIFICATION TELEGRAM                               │
│     → Envoyer détails du trade                          │
│     → Symbole, direction, BET, TO WIN, prix             │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
             (Répéter toutes les 15 minutes)
```

---

## 8. EXEMPLE CONCRET

```
🕐 18:14:52 UTC - Analyse déclenchée

📊 BTC/USDT:
   Données: 50 dernières bougies 15m
   RSI(7) = 26.6   (< 35 ✓ survendu)
   Stoch(5) = 0.0  (< 30 ✓ proche du bas)

📈 Signal généré: UP (le prix devrait remonter)

🎯 TRADE:
   Marché: "Bitcoin Up or Down - 18:15-18:30"
   Pari: UP (Yes)
   Shares: 5
   Prix: 50¢
   Coût total: $2.50

✅ Résultat à 18:30:
   Si BTC a monté  → Gain: $5.00 - $2.50 = +$2.50 (100%)
   Si BTC a baissé → Perte: -$2.50 (100%)
```

---

## 9. MONEY MANAGEMENT

### Paramètres de trading
| Paramètre | Valeur |
|-----------|--------|
| Shares par trade | 5 |
| Prix maximum | 50¢ |
| Coût max par trade | $2.50 |
| Gain potentiel max | $2.50 (100%) |
| Cooldown | 15 min par symbole |

### Calcul de rentabilité (avec 55% Win Rate)

```
Sur 100 trades à $2.50 chacun:

Misé total:    100 × $2.50 = $250.00
Gains (55%):    55 × $2.50 = $137.50
Pertes (45%):   45 × $2.50 = -$112.50
─────────────────────────────────────
Profit net:                  +$25.00 (10% ROI)
```

### Projection mensuelle

| Métrique | Valeur |
|----------|--------|
| Trades/jour | ~98 |
| Trades/mois | ~2,940 |
| Win Rate | 55.5% |
| Profit/trade | ~$0.25 |
| **Profit/mois** | **~$735** |

---

## 10. RÉSULTATS DE BACKTEST (2024-2025)

### Par symbole et année

| Année | Symbole | Trades | Trades/jour | Win Rate | PnL |
|-------|---------|--------|-------------|----------|-----|
| 2024 | BTC | 14,461 | 39.5 | 56.0% | +$4,358 |
| 2024 | ETH | 13,979 | 38.2 | 55.4% | +$3,788 |
| 2024 | XRP | 6,522 | 17.8 | 57.1% | +$2,300 |
| **2024** | **Total** | **34,962** | **95.5** | **56.0%** | **+$10,445** |
| 2025 | BTC | 15,382 | 42.5 | 54.6% | +$3,525 |
| 2025 | ETH | 14,132 | 39.0 | 55.1% | +$3,620 |
| 2025 | XRP | 7,149 | 19.7 | 55.8% | +$2,072 |
| **2025** | **Total** | **36,663** | **101.2** | **55.0%** | **+$9,218** |

### Résumé global

| Métrique | Valeur |
|----------|--------|
| Total trades | 71,625 |
| Trades/jour moyen | ~98 |
| Win Rate global | 55.5% |
| **PnL total** | **+$19,662** |

---

## 11. FICHIERS DU PROJET

| Fichier | Description |
|---------|-------------|
| `bot_simple.py` | Bot principal, boucle de trading |
| `src/polymarket_client.py` | Connexion API Polymarket |
| `src/telegram_bot.py` | Notifications Telegram |
| `src/config.py` | Chargement configuration (.env) |
| `src/trade_validator.py` | Validation des prix |
| `logs/bot_simple.log` | Logs du bot |

---

## 12. CONFIGURATION SERVEUR (VPS)

| Paramètre | Valeur |
|-----------|--------|
| Provider | AWS Lightsail |
| OS | Ubuntu 22.04 |
| Région | ca-central-1 |
| Path | /home/ubuntu/poly |
| Service | bot_simple.py |

### Commandes utiles

```bash
# Démarrer le bot
cd /home/ubuntu/poly
source venv/bin/activate
echo 'OUI' | nohup python -u bot_simple.py --live --shares 5 > logs/bot_simple.log 2>&1 &

# Vérifier le status
ps aux | grep bot_simple

# Voir les logs
tail -f logs/bot_simple.log

# Arrêter le bot
pkill -f bot_simple.py
```

### Cron jobs configurés

| Heure (UTC) | Script | Description |
|-------------|--------|-------------|
| 04:00 | daily_maintenance.sh | Nettoyage logs + vérification bot |
| 13:00 | daily_summary.py | Résumé quotidien |

---

## 13. SCHÉMA RÉCAPITULATIF

```
     BINANCE                          POLYMARKET
    (données)                          (trading)
        │                                  │
        ▼                                  ▼
   ┌─────────┐    ┌──────────────┐   ┌─────────────┐
   │ BTC 15m │───▶│ RSI < 35 ?   │──▶│ BUY UP 5sh  │
   │ ETH 15m │    │ Stoch < 30 ? │   │ @ 50¢ max   │
   │ XRP 15m │    └──────────────┘   └─────────────┘
   └─────────┘          │                  │
                        ▼                  ▼
                   ┌─────────┐      ┌─────────────┐
                   │ Signal  │      │  TELEGRAM   │
                   │ UP/DOWN │      │ Notification│
                   └─────────┘      └─────────────┘
```

---

*Document généré le 28 décembre 2025*
*Stratégie HYBRID v1.0*
