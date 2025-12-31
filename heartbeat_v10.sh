#!/bin/bash
# ============================================================
# HEARTBEAT V10 - Signal "alive" toutes les heures
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

# System info
UPTIME=$(uptime -p)
MEMORY=$(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
DISK=$(df -h / | awk 'NR==2{print $5}')
LOAD=$(cat /proc/loadavg | awk '{print $1}')

# Check V10 bots
BOTS_RUNNING=0
BOTS_STATUS=""

# Check watchdog
if pgrep -f "watchdog_v10.py" > /dev/null; then
    WATCHDOG_STATUS="✅ Watchdog V10"
else
    WATCHDOG_STATUS="❌ Watchdog V10"
fi

# Check individual bots
for symbol in BTC ETH XRP; do
    if pgrep -f "bot_v10_${symbol,,}.py" > /dev/null; then
        BOTS_STATUS+="✅ $symbol "
        ((BOTS_RUNNING++))
    else
        BOTS_STATUS+="❌ $symbol "
    fi
done

# Get recent trades from logs
TRADES_1H=$(grep -c "TRADE" $POLY_DIR/logs/bot_v10_*.log 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')

TIMESTAMP=$(date -u "+%Y-%m-%d %H:%M UTC")

MESSAGE="💓 <b>HEARTBEAT V10</b>

🖥️ Status: ONLINE
⏰ $TIMESTAMP

<b>Systeme:</b>
• Uptime: $UPTIME
• RAM: $MEMORY
• Disque: $DISK
• Load: $LOAD

<b>Bots V10 ($BOTS_RUNNING/3):</b>
$WATCHDOG_STATUS
$BOTS_STATUS

<b>Strategie:</b>
• RSI(7): 42/62
• Stoch(5): 38/68
• FTFC: 2.0

✅ Systeme operationnel!"

send_telegram "$MESSAGE"
echo "[$(date)] Heartbeat V10 envoye"
