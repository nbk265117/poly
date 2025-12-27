#!/bin/bash
#
# Configuration rapide du fichier .env
# Usage: ./configure_env.sh
#

echo "============================================================"
echo "  CONFIGURATION DU BOT POLYMARKET"
echo "============================================================"
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    echo "Fichier .env existant détecté."
    read -p "Voulez-vous le reconfigurer? (o/n): " reconfigure
    if [ "$reconfigure" != "o" ]; then
        echo "Configuration annulée."
        exit 0
    fi
fi

echo ""
echo "Entrez vos informations (ou appuyez sur Entrée pour ignorer):"
echo ""

# Polymarket Private Key
read -p "Clé privée Polymarket (0x...): " POLY_KEY

# Telegram
read -p "Token Bot Telegram: " TG_TOKEN
read -p "Chat ID Telegram: " TG_CHAT

# Binance (optional)
read -p "API Key Binance (optionnel): " BN_KEY
read -p "API Secret Binance (optionnel): " BN_SECRET

# Create .env
cat > .env << EOF
# === POLYMARKET TRADING BOT CONFIG ===
# Généré le $(date)

# Mode: development (simulation) ou production (argent réel)
ENVIRONMENT=production

# Polymarket - Clé privée de votre wallet
POLYMARKET_PRIVATE_KEY=${POLY_KEY}

# Telegram - Notifications
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_CHAT_ID=${TG_CHAT}

# Binance - Pour les données de prix
BINANCE_API_KEY=${BN_KEY}
BINANCE_API_SECRET=${BN_SECRET}

# Logging
LOG_LEVEL=INFO
EOF

echo ""
echo "✅ Fichier .env créé avec succès!"
echo ""
echo "Pour vérifier: cat .env"
echo "Pour modifier: nano .env"
