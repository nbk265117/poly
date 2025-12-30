#!/bin/bash
# ============================================================
# ALERT STARTUP - Envoie une alerte quand le VPS démarre/redémarre
# ============================================================

POLY_DIR="/home/ubuntu/poly"
source "$POLY_DIR/.env" 2>/dev/null

TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

send_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${message}" \
            -d "parse_mode=HTML" > /dev/null
    fi
}

TIMESTAMP=$(date -u "+%Y-%m-%d %H:%M UTC")
IP=$(curl -s ifconfig.me 2>/dev/null || echo "Unknown")

MESSAGE="🔄 <b>VPS REDÉMARRÉ!</b>

⚠️ Le VPS vient de démarrer/redémarrer

⏰ $TIMESTAMP
🌐 IP: $IP

🤖 Les bots vont démarrer automatiquement...

⚡ Action: Vérifier que tout fonctionne"

send_telegram "$MESSAGE"
echo "[$(date)] Alert startup envoyée"
