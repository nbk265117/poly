#!/bin/bash
# ============================================================
# ALERT STARTUP V10 - Alerte au demarrage du VPS
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

MESSAGE="🔄 <b>VPS REDEMARRE - V10</b>

⚠️ Le VPS vient de demarrer/redemarrer

⏰ $TIMESTAMP
🌐 IP: $IP

🤖 <b>Bots V10 en demarrage:</b>
  - BTC: 7 shares (~\$3.68)
  - ETH: 10 shares (~\$5.25)
  - XRP: 5 shares (~\$2.63)

📊 <b>Strategie V10:</b>
  - RSI(7): 42/62
  - Stoch(5): 38/68
  - FTFC: 2.0

⚡ Watchdog V10 demarre automatiquement..."

send_telegram "$MESSAGE"
echo "[$(date)] Alert startup V10 envoyee"
