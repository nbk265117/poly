#!/bin/bash
# ============================================================
# HEARTBEAT - Envoie un signal "alive" à Telegram toutes les heures
# Si tu ne reçois pas ce message, le VPS est down!
# ============================================================

POLY_DIR="/home/ubuntu/poly"
source "$POLY_DIR/.env" 2>/dev/null

# Telegram config (récupère depuis .env ou utilise les valeurs par défaut)
TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Fonction pour envoyer message Telegram
send_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${message}" \
            -d "parse_mode=HTML" > /dev/null
    fi
}

# Infos système
UPTIME=$(uptime -p)
MEMORY=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
DISK=$(df -h / | awk 'NR==2{print $5}')
LOAD=$(cat /proc/loadavg | awk '{print $1}')

# Vérifier les bots
BOTS_RUNNING=0
BOTS_STATUS=""

for symbol in ETH BTC XRP; do
    if pgrep -f "bot_simple.py.*--symbols $symbol" > /dev/null; then
        BOTS_STATUS+="✅ $symbol "
        ((BOTS_RUNNING++))
    else
        BOTS_STATUS+="❌ $symbol "
    fi
done

# Timestamp
TIMESTAMP=$(date -u "+%Y-%m-%d %H:%M UTC")

# Message
MESSAGE="💓 <b>HEARTBEAT VPS</b>

🖥️ Status: ONLINE
⏰ $TIMESTAMP

<b>Système:</b>
• Uptime: $UPTIME
• RAM: $MEMORY
• Disque: $DISK
• Load: $LOAD

<b>Bots ($BOTS_RUNNING/3):</b>
$BOTS_STATUS

✅ Tout fonctionne!"

# Envoyer
send_telegram "$MESSAGE"

echo "[$(date)] Heartbeat envoyé"
