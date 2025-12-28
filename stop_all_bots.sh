#!/bin/bash
# Arrête tous les bots

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Arrêt des 4 bots..."

# Arrêter par PID sauvegardé
for pair in btc eth xrp sol; do
    if [ -f "logs/pid_${pair}.txt" ]; then
        PID=$(cat "logs/pid_${pair}.txt")
        if kill -0 $PID 2>/dev/null; then
            echo "  Arrêt ${pair^^} (PID: $PID)"
            kill $PID
        fi
        rm -f "logs/pid_${pair}.txt"
    fi
done

# Backup: tuer tous les processus bot_*.py
pkill -f "bot_btc.py" 2>/dev/null
pkill -f "bot_eth.py" 2>/dev/null
pkill -f "bot_xrp.py" 2>/dev/null
pkill -f "bot_sol.py" 2>/dev/null

echo ""
echo "Tous les bots arrêtés!"
