#!/bin/bash
#
# POLYMARKET TRADING BOT - VPS INSTALLATION SCRIPT
# DigitalOcean / Ubuntu 22.04
#
# Usage: curl -sSL https://raw.githubusercontent.com/nbk265117/poly/main/scripts/vps_install.sh | bash
#

set -e

echo "============================================================"
echo "  POLYMARKET TRADING BOT - INSTALLATION"
echo "============================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
REPO_URL="https://github.com/nbk265117/poly.git"
INSTALL_DIR="/root/poly"
SERVICE_NAME="polybot"

# Step 1: System Update
echo -e "${YELLOW}[1/7] Mise à jour du système...${NC}"
apt update && apt upgrade -y

# Step 2: Install dependencies
echo -e "${YELLOW}[2/7] Installation des dépendances...${NC}"
apt install -y python3 python3-pip python3-venv git curl wget htop

# Step 3: Clone repository
echo -e "${YELLOW}[3/7] Clonage du repository...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo "Dossier existe déjà, mise à jour..."
    cd $INSTALL_DIR
    git pull origin main
else
    git clone $REPO_URL $INSTALL_DIR
    cd $INSTALL_DIR
fi

# Step 4: Setup Python environment
echo -e "${YELLOW}[4/7] Configuration de l'environnement Python...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 5: Create directories
echo -e "${YELLOW}[5/7] Création des dossiers...${NC}"
mkdir -p logs
mkdir -p data/historical

# Step 6: Create .env file if not exists
echo -e "${YELLOW}[6/7] Configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}IMPORTANT: Vous devez configurer le fichier .env${NC}"
    cat > .env << 'ENVFILE'
# === POLYMARKET TRADING BOT CONFIG ===

# Mode: development (simulation) ou production (argent réel)
ENVIRONMENT=production

# Polymarket - Clé privée de votre wallet
POLYMARKET_PRIVATE_KEY=YOUR_PRIVATE_KEY_HERE

# Telegram - Notifications
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID

# Binance - Pour les données de prix (optionnel)
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Logging
LOG_LEVEL=INFO
ENVFILE
    echo -e "${YELLOW}Fichier .env créé. Éditez-le avec: nano /root/poly/.env${NC}"
else
    echo ".env existe déjà"
fi

# Step 7: Create systemd service
echo -e "${YELLOW}[7/7] Création du service systemd...${NC}"
cat > /etc/systemd/system/${SERVICE_NAME}.service << 'SERVICEFILE'
[Unit]
Description=Polymarket Trading Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/poly
Environment=PATH=/root/poly/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/root/poly/venv/bin/python live_trader.py --live --symbols "BTC/USDT,ETH/USDT" --bet 2
Restart=always
RestartSec=30
StandardOutput=append:/root/poly/logs/bot.log
StandardError=append:/root/poly/logs/bot_error.log

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/root/poly

[Install]
WantedBy=multi-user.target
SERVICEFILE

systemctl daemon-reload

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  INSTALLATION TERMINÉE !${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "Prochaines étapes:"
echo ""
echo "1. Configurez vos clés API:"
echo "   nano /root/poly/.env"
echo ""
echo "2. Testez le bot en simulation:"
echo "   cd /root/poly && source venv/bin/activate"
echo "   python live_trader.py --symbols 'BTC/USDT,ETH/USDT' --bet 2"
echo ""
echo "3. Lancez le bot en production:"
echo "   systemctl start polybot"
echo "   systemctl enable polybot  # Démarrage auto au boot"
echo ""
echo "4. Commandes utiles:"
echo "   systemctl status polybot   # Voir le status"
echo "   journalctl -u polybot -f   # Voir les logs en temps réel"
echo "   systemctl restart polybot  # Redémarrer"
echo "   systemctl stop polybot     # Arrêter"
echo ""
echo -e "${GREEN}Bonne chance avec votre trading ! 🚀${NC}"
