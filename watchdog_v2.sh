#!/bin/bash
# ============================================================
# WATCHDOG V2 - 3 BOTS SEPARES (BTC, ETH, XRP)
# Verifie et relance chaque bot individuellement
# ============================================================

cd /home/ubuntu/poly
source venv/bin/activate

PY="/home/ubuntu/poly/venv/bin/python"
LOG_DIR="/home/ubuntu/poly/logs"

# Fonction pour verifier et lancer un bot
check_bot() {
    local SYMBOL=$1
    local LOG_FILE="${LOG_DIR}/bot_${SYMBOL}.log"

    # Verifier si le bot tourne
    if ! pgrep -f "bot_v2_simple.py.*${SYMBOL}/USDT" > /dev/null; then
        echo "$(date) | Starting bot ${SYMBOL}..." >> ${LOG_DIR}/watchdog.log
        nohup $PY bot_v2_simple.py --live --yes --shares 10 --symbols ${SYMBOL}/USDT >> ${LOG_FILE} 2>&1 &
        sleep 2
    fi
}

# Verifier chaque bot
check_bot "BTC"
check_bot "ETH"
check_bot "XRP"

# Log status
echo "$(date) | Watchdog check complete. Running bots: $(pgrep -c -f bot_v2_simple.py)" >> ${LOG_DIR}/watchdog.log
