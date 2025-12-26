# 🤖 Robot de Trading Polymarket

Robot de trading automatisé en Python pour Polymarket, opérant sur timeframe 15 minutes avec une stratégie simple et robuste.

## 🎯 Caractéristiques

### Trading
- **Paires**: BTC, ETH, XRP
- **Timeframe**: 15 minutes
- **Fréquence**: 40-60 trades par jour
- **Win rate cible**: ~55%
- **Exécution**: 8 secondes avant clôture de la bougie

### Stratégie (Max 3 Indicateurs)

1. **Price Action** (Trigger principal)
   - Analyse des bougies (mèches, corps, rejection)
   - Détection des patterns (hammer, shooting star, engulfing)

2. **FTFC Multi-Timeframe** (Filtre directionnel)
   - Analyse sur 15m, 1h, 4h
   - Alignement des timeframes requis
   - Détermine le biais haussier/baissier

3. **Volume** (Filtre de qualité)
   - Confirmation par volume
   - Évite les faux breakouts
   - Filtre les trades en faible liquidité

### Fonctionnalités
- ✅ Backtesting intensif (>1 an de données)
- ✅ Notifications Telegram en temps réel
- ✅ Gestion du risque (SL/TP automatiques)
- ✅ Architecture modulaire et extensible
- ✅ Mode simulation et production
- ✅ Logs détaillés

## 📦 Installation

### Prérequis
- Python 3.8+
- pip
- Compte Polymarket
- Bot Telegram (optionnel)

### Étapes

1. **Cloner le projet**
```bash
cd /Users/mac/poly
```

2. **Créer un environnement virtuel**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les variables d'environnement**
```bash
cp .env.example .env
nano .env  # Éditer avec vos clés
```

Remplir les clés API:
- `BINANCE_API_KEY` et `BINANCE_API_SECRET` (pour données historiques)
- `POLYMARKET_API_KEY` et `POLYMARKET_PRIVATE_KEY` (pour trading)
- `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` (pour notifications)

5. **Adapter la configuration**
```bash
nano config.yaml  # Ajuster selon vos besoins
```

## 🚀 Utilisation

### 1. Télécharger les données historiques

```bash
# Télécharger 24 mois de données 15m pour BTC, ETH, XRP
python scripts/download_data_15m.py
```

Ou manuellement:
```bash
python scripts/fetch_ohlcv_full_v4.py --symbols "BTC,ETH,XRP" --months 24 --timeframe 15m
```

### 2. Lancer le Backtesting

**Backtest complet (recommandé avant production)**
```bash
python backtest_main.py --plot --save-results
```

**Backtest avec paramètres personnalisés**
```bash
python backtest_main.py \
    --symbols "BTC/USDT,ETH/USDT" \
    --start-date "2023-01-01" \
    --end-date "2024-12-31" \
    --capital 10000 \
    --plot
```

**Options disponibles**
```bash
python backtest_main.py --help
```

### 3. Lancer le Robot en Production

**⚠️ IMPORTANT**: Valider le backtest avant !

```bash
# Mode simulation (recommandé pour tests)
python main.py
```

Pour passer en production, modifier dans `.env`:
```
ENVIRONMENT=production
```

### 4. Arrêter le Robot

```bash
# Appuyer sur Ctrl+C ou envoyer SIGTERM
kill -TERM <pid>
```

## 📊 Structure du Projet

```
poly/
├── main.py                      # Point d'entrée principal (trading live)
├── backtest_main.py            # Point d'entrée backtesting
├── requirements.txt            # Dépendances Python
├── config.yaml                 # Configuration principale
├── .env                        # Variables d'environnement (à créer)
├── README.md                   # Ce fichier
│
├── src/                        # Code source
│   ├── __init__.py
│   ├── config.py              # Gestionnaire de configuration
│   ├── data_manager.py        # Gestion des données OHLCV
│   ├── indicators.py          # Indicateurs techniques
│   ├── strategy.py            # Moteur de stratégie
│   ├── backtest.py            # Moteur de backtesting
│   ├── polymarket_client.py   # Client Polymarket
│   └── telegram_bot.py        # Bot de notifications Telegram
│
├── scripts/                    # Scripts utilitaires
│   ├── fetch_ohlcv_full_v4.py # Téléchargement données Binance
│   └── download_data_15m.py   # Wrapper téléchargement 15m
│
├── data/                       # Données (créé automatiquement)
│   ├── historical/            # Données historiques CSV
│   └── cache/                 # Cache temporaire
│
├── logs/                       # Logs (créé automatiquement)
│   └── trading_bot.log
│
└── backtest_results/          # Résultats backtest (créé si sauvegarde)
    ├── trades_*.csv
    ├── equity_*.csv
    └── backtest_equity_*.png
```

## ⚙️ Configuration

### config.yaml

Fichier principal de configuration. Personnaliser:

- **symbols**: Paires à trader
- **timeframes**: Timeframes pour FTFC
- **strategy.indicators**: Paramètres des indicateurs
- **strategy.risk**: Gestion du risque (SL, TP, position size)
- **backtest**: Paramètres de backtesting

### .env

Variables sensibles:

- Clés API Binance
- Clés API Polymarket
- Token Telegram
- Environment (development/production)

## 📈 Backtesting

### Métriques Calculées

- **Win Rate**: Pourcentage de trades gagnants
- **Total Return**: Retour total en %
- **Profit Factor**: Ratio gains/pertes
- **Max Drawdown**: Perte maximale depuis un pic
- **Sharpe Ratio**: Ratio rendement/risque
- **Trades per Day**: Nombre moyen de trades par jour

### Critères de Validation

✅ **Stratégie Validée** si:
- Win rate ≥ 55%
- Total return > 0%
- Trades/jour entre 40-60
- Drawdown < 10%

## 📱 Notifications Telegram

Le bot envoie des notifications pour:

- 🤖 Démarrage/Arrêt du bot
- 📈 Ouverture de trade (symbole, direction, prix, SL/TP)
- 📉 Fermeture de trade (résultat, PnL, raison)
- 📊 Résumé journalier (stats, win rate, PnL)
- ⚠️ Erreurs et alertes

### Configurer Telegram

1. Créer un bot avec [@BotFather](https://t.me/botfather)
2. Récupérer le token
3. Obtenir votre chat ID ([@userinfobot](https://t.me/userinfobot))
4. Ajouter dans `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

## 🔐 Sécurité

- ❌ **NE JAMAIS** commiter `.env` ou les clés API
- ✅ Utiliser `.gitignore` pour exclure les fichiers sensibles
- ✅ Tester en mode simulation avant production
- ✅ Commencer avec un petit capital
- ✅ Surveiller les logs régulièrement

## 🛠️ Développement

### Ajouter un Indicateur

1. Éditer `src/indicators.py`
2. Créer une nouvelle classe d'indicateur
3. L'intégrer dans `IndicatorPipeline`
4. Tester avec backtest

### Modifier la Stratégie

1. Éditer `src/strategy.py`
2. Ajuster la logique dans `analyze_market()`
3. Valider avec backtest intensif

### Tester le Code

```bash
# Tester individuellement chaque module
python src/indicators.py
python src/data_manager.py
python src/strategy.py
```

## 📊 Exemple de Backtest

```bash
python backtest_main.py --plot --save-results

================================================================================
📊 RÉSULTATS DU BACKTEST
================================================================================

💰 PERFORMANCE
  Capital initial:      $10,000.00
  Capital final:        $11,250.00
  PnL total:            $1,250.00
  Retour total:         12.50%

📈 STATISTIQUES DES TRADES
  Nombre total:         450
  Gagnants:             248
  Perdants:             202
  Win rate:             55.11%
  Trades par jour:      45.2

💵 GAINS/PERTES
  Gain moyen:           $15.50
  Perte moyenne:        -$12.20
  PnL moyen:            $2.78
  Profit Factor:        1.27

📉 RISQUE
  Drawdown max:         -5.20%
  Sharpe Ratio:         1.85

================================================================================
✅ BACKTEST VALIDÉ - Stratégie prometteuse!
================================================================================
```

## 🚨 Dépannage

### Erreur: Module not found

```bash
pip install -r requirements.txt
```

### Erreur: Données manquantes

```bash
python scripts/download_data_15m.py
```

### Telegram ne fonctionne pas

Vérifier:
- Token et Chat ID corrects dans `.env`
- `telegram_enabled: true` dans `config.yaml`
- Installation: `pip install python-telegram-bot`

### Polymarket erreur

- Vérifier les clés API dans `.env`
- Tester en mode simulation d'abord
- Vérifier solde suffisant

## 📚 Ressources

- [Documentation Polymarket](https://docs.polymarket.com/)
- [CCXT Documentation](https://docs.ccxt.com/)
- [Python Telegram Bot](https://python-telegram-bot.org/)
- [Pandas Documentation](https://pandas.pydata.org/)

## 📝 TODO / Améliorations Futures

- [ ] Interface web de monitoring
- [ ] Support multi-exchange
- [ ] Optimisation automatique des paramètres
- [ ] ML pour prédiction de signaux
- [ ] Alertes SMS
- [ ] Dashboard Grafana

## ⚖️ Disclaimer

Ce robot est fourni à des fins éducatives. Le trading comporte des risques. Ne tradez jamais plus que ce que vous pouvez vous permettre de perdre. Les performances passées ne garantissent pas les résultats futurs.

## 📧 Support

Pour toute question ou problème, créer une issue ou consulter les logs dans `logs/trading_bot.log`.

---

**Made with ❤️ for automated trading**
