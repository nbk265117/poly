# GUIDE DE CONFIGURATION - Trading Live Polymarket

## 1. Configuration Telegram Bot

### Étape 1 : Créer un bot Telegram

1. Ouvrez Telegram et cherchez **@BotFather**
2. Envoyez `/newbot`
3. Choisissez un nom (ex: "Polymarket Trading Bot")
4. Choisissez un username (ex: "my_poly_trader_bot")
5. **Copiez le TOKEN** (ressemble à: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Étape 2 : Obtenir votre Chat ID

1. Cherchez **@userinfobot** sur Telegram
2. Envoyez `/start`
3. **Copiez votre Chat ID** (un nombre comme: `123456789`)

### Étape 3 : Configurer les variables d'environnement

Créez un fichier `.env` à la racine du projet :

```bash
# .env
TELEGRAM_BOT_TOKEN=votre_token_ici
TELEGRAM_CHAT_ID=votre_chat_id_ici

# Polymarket (pour trading live)
POLYMARKET_API_KEY=votre_api_key
POLYMARKET_PRIVATE_KEY=votre_private_key

# Binance (pour données)
BINANCE_API_KEY=votre_api_key
BINANCE_API_SECRET=votre_secret

# Mode
ENVIRONMENT=development  # ou 'production' pour trading réel
```

### Étape 4 : Tester le bot Telegram

```bash
cd /Users/mac/poly
source venv/bin/activate
python src/telegram_bot.py
```

Vous devriez recevoir des messages de test sur Telegram.

---

## 2. Configuration Polymarket

### Étape 1 : Créer un compte Polymarket

1. Allez sur https://polymarket.com
2. Connectez-vous avec votre wallet (MetaMask, etc.)
3. Déposez des USDC sur Polygon

### Étape 2 : Obtenir les clés API

Pour le trading automatique, vous aurez besoin de :
- **API Key** : Depuis les paramètres de votre compte Polymarket
- **Private Key** : La clé privée de votre wallet Polygon

⚠️ **SÉCURITÉ** : Ne partagez JAMAIS votre clé privée !

---

## 3. Lancer le Trading

### Mode Simulation (recommandé pour commencer)

```bash
cd /Users/mac/poly
source venv/bin/activate

# Lancer en simulation (pas d'argent réel)
python live_trader.py --symbols "BTC/USDT,ETH/USDT" --bet 2
```

### Mode Production (argent réel)

```bash
# ⚠️ ATTENTION: Cela utilisera de l'argent réel !
python live_trader.py --live --symbols "BTC/USDT" --bet 2
```

---

## 4. Déploiement sur Serveur (24/7)

### Option A : VPS (Recommandé)

**Fournisseurs suggérés :**
- DigitalOcean ($5-10/mois)
- Vultr ($5/mois)
- Hetzner (€4/mois)
- AWS Lightsail ($3.50/mois)

**Configuration minimale :**
- 1 vCPU
- 1 GB RAM
- Ubuntu 22.04

### Installation sur VPS

```bash
# Se connecter au VPS
ssh root@votre_ip

# Mettre à jour
apt update && apt upgrade -y

# Installer Python
apt install python3 python3-pip python3-venv git -y

# Cloner le projet
git clone https://github.com/nbk265117/poly.git
cd poly

# Créer l'environnement
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Créer le fichier .env
nano .env
# (coller vos variables d'environnement)

# Créer le dossier logs
mkdir -p logs

# Tester
python live_trader.py --symbols "BTC/USDT" --bet 1
```

### Lancer en arrière-plan avec systemd

```bash
# Créer le service
sudo nano /etc/systemd/system/polytrader.service
```

Contenu du fichier :

```ini
[Unit]
Description=Polymarket Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/poly
Environment=PATH=/root/poly/venv/bin
ExecStart=/root/poly/venv/bin/python live_trader.py --symbols "BTC/USDT,ETH/USDT" --bet 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable polytrader
sudo systemctl start polytrader

# Vérifier le status
sudo systemctl status polytrader

# Voir les logs
journalctl -u polytrader -f
```

### Option B : Docker (Alternative)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["python", "live_trader.py", "--symbols", "BTC/USDT,ETH/USDT", "--bet", "2"]
```

```bash
# Build et run
docker build -t polytrader .
docker run -d --name polytrader --env-file .env polytrader
```

### Option C : Screen (Simple)

```bash
# Installer screen
apt install screen -y

# Créer une session
screen -S trader

# Lancer le bot
source venv/bin/activate
python live_trader.py --symbols "BTC/USDT,ETH/USDT" --bet 2

# Détacher (Ctrl+A puis D)
# Rattacher: screen -r trader
```

---

## 5. Monitoring

### Logs en temps réel

```bash
# Sur le serveur
tail -f logs/live_trader.log
```

### Telegram

Le bot vous enverra automatiquement :
- ✅ Chaque trade exécuté
- 📊 Résumé journalier
- ⚠️ Alertes d'erreur

---

## 6. Sécurité

### Checklist

- [ ] Ne jamais commit le fichier `.env`
- [ ] Utiliser un wallet dédié au trading (pas votre wallet principal)
- [ ] Commencer avec de petites mises ($1-2)
- [ ] Monitorer régulièrement les trades
- [ ] Avoir un stop-loss mental (ex: arrêter si perte > $50/jour)

### Limites recommandées

```
Capital initial : $100
Mise par trade  : $2 (2% du capital)
Max trades/jour : 50
Stop si perte   : -$20/jour
```

---

## 7. Dépannage

### Le bot ne démarre pas

```bash
# Vérifier Python
python --version

# Vérifier les dépendances
pip install -r requirements.txt

# Vérifier le fichier .env
cat .env
```

### Pas de notification Telegram

```bash
# Tester le bot
python -c "
from src.telegram_bot import TelegramNotifier
t = TelegramNotifier()
t.send_message('Test')
"
```

### Erreur connexion Binance

```bash
# Vérifier la connexion
python -c "
import ccxt
e = ccxt.binance()
print(e.fetch_ticker('BTC/USDT'))
"
```

---

## 8. Commandes utiles

```bash
# Lancer en simulation
python live_trader.py

# Lancer en production
python live_trader.py --live

# Changer la mise
python live_trader.py --bet 5

# Changer les symboles
python live_trader.py --symbols "BTC/USDT,ETH/USDT,XRP/USDT"

# Voir l'aide
python live_trader.py --help
```

---

**Bonne chance avec votre trading ! 🚀**
