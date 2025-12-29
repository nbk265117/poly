#!/bin/bash
# ============================================================
# WATCHDOG - Surveillance et relance automatique des bots
# ============================================================
# Usage: ./watchdog.sh
# Cron: */5 * * * * /home/ubuntu/poly/watchdog.sh >> /home/ubuntu/poly/logs/watchdog.log 2>&1
# ============================================================

POLY_DIR="/home/ubuntu/poly"
LOG_FILE="$POLY_DIR/logs/watchdog.log"
SHARES=5

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Timestamp
timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1"
}

# Bots à surveiller
BOTS=("BTC" "ETH" "XRP")

# Vérifier si un bot tourne
check_bot() {
    local symbol=$1
    pgrep -f "bot_simple.py.*--symbols $symbol" > /dev/null
    return $?
}

# Relancer un bot
restart_bot() {
    local symbol=$1
    log "🔄 Relance du bot $symbol..."

    cd $POLY_DIR
    source venv/bin/activate

    # Lancer le bot
    nohup python bot_simple.py --live --yes --shares $SHARES --symbols $symbol > logs/bot_$(echo $symbol | tr '[:upper:]' '[:lower:]').log 2>&1 &

    sleep 2

    if check_bot $symbol; then
        log "✅ Bot $symbol relancé avec succès (PID: $(pgrep -f "bot_simple.py.*--symbols $symbol"))"
        return 0
    else
        log "❌ Échec du relancement du bot $symbol"
        return 1
    fi
}

# Vérifier l'espace disque
check_disk() {
    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$usage" -gt 90 ]; then
        log "⚠️ ALERTE: Espace disque critique ($usage%)"
        return 1
    fi
    return 0
}

# Main
log "=========================================="
log "🔍 WATCHDOG - Vérification des bots"
log "=========================================="

# Vérifier l'espace disque
check_disk

# Compteurs
running=0
restarted=0
failed=0

for bot in "${BOTS[@]}"; do
    if check_bot $bot; then
        log "✅ $bot: En cours d'exécution"
        ((running++))
    else
        log "❌ $bot: ARRÊTÉ - Tentative de relance..."
        if restart_bot $bot; then
            ((restarted++))
        else
            ((failed++))
        fi
    fi
done

log "------------------------------------------"
log "📊 Résumé: $running actifs, $restarted relancés, $failed échecs"
log "=========================================="

# Code de sortie
if [ $failed -gt 0 ]; then
    exit 1
fi
exit 0
