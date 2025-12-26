# 🚀 Guide de Démarrage Rapide

Guide étape par étape pour démarrer le robot de trading Polymarket.

## 📋 Prérequis

### 1. Système
- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Git (optionnel)

### 2. Comptes & Clés
- [ ] Compte Binance (pour télécharger les données)
- [ ] Compte Polymarket (pour trader)
- [ ] Bot Telegram (optionnel, pour notifications)

## 🔧 Installation

### Étape 1: Installation des dépendances

```bash
# Option 1: Avec le Makefile
make install

# Option 2: Directement avec pip
pip install -r requirements.txt
```

### Étape 2: Configuration

1. **Créer le fichier .env**

```bash
# Copier le template (si disponible)
cp .env.example .env

# Ou créer manuellement
nano .env
```

2. **Remplir les clés API dans .env**

```env
# Binance (pour données historiques)
BINANCE_API_KEY=votre_cle_api_binance
BINANCE_API_SECRET=votre_secret_binance

# Polymarket (pour trading)
POLYMARKET_API_KEY=votre_cle_polymarket
POLYMARKET_PRIVATE_KEY=votre_cle_privee

# Telegram (optionnel)
TELEGRAM_BOT_TOKEN=votre_token_telegram
TELEGRAM_CHAT_ID=votre_chat_id

# Configuration
ENVIRONMENT=development  # development ou production
LOG_LEVEL=INFO
```

3. **Ajuster config.yaml** (optionnel)

```yaml
# Modifier selon vos préférences
symbols:
  - BTC/USDT
  - ETH/USDT
  - XRP/USDT

strategy:
  risk:
    position_size_usd: 100  # Taille de position
    stop_loss_percent: 2.0  # Stop loss
    take_profit_percent: 3.0  # Take profit
```

## 📊 Téléchargement des Données

**OBLIGATOIRE avant de lancer le backtesting ou le robot**

```bash
# Option 1: Script automatique
make download

# Option 2: Script Python
python scripts/download_data_15m.py

# Option 3: Script manuel avec options
python scripts/fetch_ohlcv_full_v4.py \
    --symbols "BTC,ETH,XRP" \
    --months 24 \
    --timeframe 15m \
    --out-dir data/historical
```

**Durée**: 10-30 minutes selon votre connexion

**Résultat**: Fichiers CSV dans `data/historical/`
- `BTC_USDT_15m.csv`
- `ETH_USDT_15m.csv`
- `XRP_USDT_15m.csv`

## 🧪 Backtesting (OBLIGATOIRE)

**⚠️ Ne JAMAIS lancer le robot sans backtest validé**

### Backtest Complet

```bash
# Avec graphiques et sauvegarde
make backtest

# Ou
python backtest_main.py --plot --save-results
```

### Backtest Personnalisé

```bash
# Période spécifique
python backtest_main.py \
    --start-date "2023-01-01" \
    --end-date "2024-12-31" \
    --capital 10000 \
    --plot

# Un seul symbole
python backtest_main.py \
    --symbols "BTC/USDT" \
    --plot

# Avec paramètres de coûts
python backtest_main.py \
    --commission 0.001 \
    --slippage 0.0005 \
    --plot
```

### Interpréter les Résultats

✅ **Stratégie Validée** si:
```
Win rate:     ≥ 55%
Total return: > 0%
Trades/jour:  40-60
Drawdown:     < 10%
```

❌ **À améliorer** si:
```
Win rate:     < 50%
Total return: < 0%
Drawdown:     > 15%
```

### Fichiers Générés

- `backtest_results/trades_YYYYMMDD_HHMMSS.csv` - Liste des trades
- `backtest_results/equity_YYYYMMDD_HHMMSS.csv` - Courbe d'equity
- `backtest_equity_YYYYMMDD_HHMMSS.png` - Graphique

## 🚀 Lancement du Robot

### Mode Simulation (Recommandé)

**Parfait pour tester sans risque**

```bash
# S'assurer que ENVIRONMENT=development dans .env
python main.py
```

### Mode Production

**⚠️ ATTENTION: Trading réel avec de l'argent réel**

1. **Valider le backtest**
2. **Tester en simulation**
3. **Commencer avec un petit capital**

```bash
# Modifier .env
ENVIRONMENT=production

# Lancer
python main.py
```

### Arrêter le Robot

```bash
# Appuyer sur Ctrl+C dans le terminal
# Ou envoyer un signal SIGTERM
kill -TERM <pid>
```

## 📱 Configuration Telegram

### Créer un Bot

1. Ouvrir [@BotFather](https://t.me/botfather) sur Telegram
2. Envoyer `/newbot`
3. Suivre les instructions
4. Copier le token

### Obtenir le Chat ID

1. Ouvrir [@userinfobot](https://t.me/userinfobot)
2. Envoyer n'importe quel message
3. Copier votre ID

### Configurer

Ajouter dans `.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

Dans `config.yaml`:
```yaml
telegram:
  enabled: true
```

## 🔍 Vérification

### Test des Modules

```bash
# Tester tous les modules
make test

# Ou individuellement
python src/config.py
python src/indicators.py
python src/data_manager.py
python src/telegram_bot.py
```

### Vérifier les Logs

```bash
# Logs en temps réel
tail -f logs/trading_bot.log

# Dernières lignes
tail -n 100 logs/trading_bot.log
```

## 📊 Surveillance

### Pendant l'Exécution

1. **Logs**: `logs/trading_bot.log`
2. **Telegram**: Notifications en temps réel
3. **Console**: Output direct

### Après Exécution

1. Analyser les trades fermés
2. Calculer les performances
3. Ajuster les paramètres si nécessaire

## 🆘 Problèmes Courants

### Module Not Found

```bash
# Réinstaller les dépendances
pip install -r requirements.txt --upgrade
```

### Données Manquantes

```bash
# Retélécharger
rm -rf data/historical/*
python scripts/download_data_15m.py
```

### Telegram Ne Fonctionne Pas

1. Vérifier le token et chat ID
2. Vérifier `telegram.enabled: true` dans config.yaml
3. Tester: `python src/telegram_bot.py`

### Polymarket Erreur

1. Vérifier les clés API dans .env
2. Vérifier le solde
3. Tester en mode simulation d'abord

### Pas Assez de Trades

Ajuster dans `config.yaml`:
```yaml
strategy:
  indicators:
    price_action:
      min_wick_ratio: 0.2  # Réduire pour plus de signaux
    volume:
      min_volume_ratio: 1.1  # Réduire pour plus de signaux
```

### Trop de Trades

Ajuster dans `config.yaml`:
```yaml
strategy:
  indicators:
    price_action:
      min_wick_ratio: 0.4  # Augmenter pour moins de signaux
    ftfc:
      require_all_aligned: true  # S'assurer que c'est true
    volume:
      min_volume_ratio: 1.5  # Augmenter pour filtrer plus
```

## 📈 Optimisation

### Améliorer le Win Rate

1. Augmenter les filtres (FTFC strict, volume élevé)
2. Réduire le nombre de trades
3. Analyser les trades perdants dans le backtest

### Augmenter le Nombre de Trades

1. Réduire les filtres
2. Ajouter plus de symboles
3. Réduire le min_body_size dans Price Action

### Réduire le Drawdown

1. Réduire la position_size_usd
2. Resserrer le stop_loss_percent
3. Limiter le nombre de positions simultanées

## 🎯 Checklist de Démarrage

- [ ] Python 3.8+ installé
- [ ] Dépendances installées (`make install`)
- [ ] Fichier `.env` créé et rempli
- [ ] `config.yaml` ajusté
- [ ] Données historiques téléchargées (`make download`)
- [ ] Backtest lancé et validé (`make backtest`)
- [ ] Win rate ≥ 55%
- [ ] Telegram configuré (optionnel)
- [ ] Test en mode simulation
- [ ] Prêt pour la production !

## 📚 Prochaines Étapes

1. **Jour 1-3**: Surveillance intensive en simulation
2. **Jour 4-7**: Ajustements fins des paramètres
3. **Semaine 2**: Passage en production avec petit capital
4. **Mois 1**: Analyse des performances et optimisations

## 💡 Conseils

1. **Toujours backtester** après un changement de paramètres
2. **Commencer petit** en production
3. **Surveiller quotidiennement** les premières semaines
4. **Ne pas sur-optimiser** la stratégie (risque d'overfitting)
5. **Tenir un journal** des modifications et performances

## 📞 Support

- Logs: `logs/trading_bot.log`
- README: `README.md`
- Code source: `src/`

---

**Bon trading ! 🚀**

