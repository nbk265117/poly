# 🔐 Configuration du fichier .env

## Créer le fichier .env

Dans votre terminal, exécutez :

```bash
cd /Users/mac/poly
nano .env
```

Puis copiez-collez ce contenu :

```env
# ========================================
# Configuration Robot de Trading Polymarket
# ========================================

# ========== Binance API (pour données historiques) ==========
BINANCE_API_KEY=
BINANCE_API_SECRET=

# ========== Polymarket API (pour trading) ==========
POLYMARKET_API_KEY=
POLYMARKET_PRIVATE_KEY=
POLYMARKET_CHAIN_ID=137

# ========== Telegram Bot (notifications) ==========
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ========== Trading Parameters ==========
TRADE_AMOUNT_USD=100
MAX_POSITION_SIZE=1000
STOP_LOSS_PERCENT=2.0
TAKE_PROFIT_PERCENT=3.0

# ========== Environment ==========
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Enregistrez avec** : `Ctrl+O` puis `Entrée`, puis `Ctrl+X` pour quitter

---

## 📝 Où Obtenir les Clés API

### 1. Binance (OBLIGATOIRE pour télécharger données)

1. Créer un compte sur [Binance](https://www.binance.com/)
2. Aller dans **Profil** → **API Management**
3. Créer une nouvelle clé API
4. Copier `API Key` et `Secret Key`
5. Coller dans `.env`

**Permissions nécessaires** : "Read" uniquement (pas de trading)

### 2. Polymarket (pour trading réel)

1. Créer un compte sur [Polymarket](https://polymarket.com/)
2. Accéder aux paramètres API
3. Générer une clé API
4. Coller dans `.env`

⚠️ **Optionnel en phase de test** - Le robot peut fonctionner en mode simulation sans ces clés

### 3. Telegram (pour notifications)

**Créer un bot :**
1. Ouvrir [@BotFather](https://t.me/botfather) sur Telegram
2. Envoyer `/newbot`
3. Choisir un nom et un username
4. Copier le **token** fourni

**Obtenir votre Chat ID :**
1. Ouvrir [@userinfobot](https://t.me/userinfobot)
2. Envoyer n'importe quel message
3. Copier votre **ID**

---

## ⚡ Configuration Rapide (Sans Clés)

Si vous voulez tester rapidement sans configurer les clés :

```bash
# Créer un .env minimal
cat > .env << 'EOF'
ENVIRONMENT=development
LOG_LEVEL=INFO
BINANCE_API_KEY=
BINANCE_API_SECRET=
POLYMARKET_API_KEY=
POLYMARKET_PRIVATE_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF
```

Le robot fonctionnera en **mode simulation** (pas de trading réel).

---

## ✅ Vérifier la Configuration

Testez que votre configuration est correcte :

```bash
python src/config.py
```

Si tout est OK, vous verrez les paramètres chargés.

---

## 🔒 Sécurité

- ❌ **NE JAMAIS** commiter `.env` sur git (déjà dans `.gitignore`)
- ❌ **NE JAMAIS** partager vos clés API
- ✅ Garder `.env` en local uniquement
- ✅ Utiliser des clés en "Read Only" pour Binance
- ✅ Tester en mode `development` avant production

---

## 🎯 Prochaines Étapes

Une fois le fichier `.env` créé :

### 1. Télécharger les données (10-30 min)
```bash
python scripts/download_data_15m.py
```

### 2. Lancer le backtesting
```bash
python backtest_main.py --plot
```

### 3. Test en simulation
```bash
python main.py
```

---

**Besoin d'aide ?** Consultez `README.md` ou `GUIDE_DEMARRAGE.md`





