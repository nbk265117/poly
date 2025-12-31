#!/bin/bash
# ============================================================
# WATCHDOG v8.1 - Surveillance et relance automatique des bots
# ============================================================
# Usage: ./watchdog.sh
# Cron: */5 * * * * /home/ubuntu/poly/watchdog.sh >> /home/ubuntu/poly/logs/watchdog.log 2>&1
# ============================================================

POLY_DIR="/home/ubuntu/poly"
LOG_FILE="$POLY_DIR/logs/watchdog.log"

# Config par bot (symbol:shares)
declare -A BOT_CONFIG
BOT_CONFIG["ETH"]=10
BOT_CONFIG["BTC"]=7
BOT_CONFIG["XRP"]=5

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1"
}

# Verifier si un bot tourne
check_bot() {
    local symbol=$1
    pgrep -f "bot_simple.py.*--symbols $symbol" > /dev/null
    return $?
}

# Relancer un bot
restart_bot() {
    local symbol=$1
    local shares=${BOT_CONFIG[$symbol]}
    log "Relance du bot $symbol avec $shares shares..."

    cd $POLY_DIR
    source venv/bin/activate

    nohup python bot_simple.py --live --yes --shares $shares --symbols ${symbol}/USDT > logs/$(echo $symbol | tr '[:upper:]' '[:lower:]').log 2>&1 &

    sleep 3

    if check_bot $symbol; then
        log "Bot $symbol relance avec succes (PID: $(pgrep -f "bot_simple.py.*--symbols $symbol"))"
        return 0
    else
        log "Echec du relancement du bot $symbol"
        return 1
    fi
}

# Verifier espace disque
check_disk() {
    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        log "ALERTE: Espace disque critique ($usage%)"
        return 1
    fi
    return 0
}

# Main
log "=========================================="
log "WATCHDOG v8.1 - Verification des bots"
log "=========================================="

check_disk

running=0
restarted=0
failed=0

for bot in ETH BTC XRP; do
    shares=${BOT_CONFIG[$bot]}
    if check_bot $bot; then
        log "$bot ($shares shares): En cours"
        ((running++))
    else
        log "$bot: ARRETE - Relance..."
        if restart_bot $bot; then
            ((restarted++))
        else
            ((failed++))
        fi
    fi
done

log "------------------------------------------"
log "Resume: $running actifs, $restarted relances, $failed echecs"
log "=========================================="

[ $failed -gt 0 ] && exit 1
exit 0
