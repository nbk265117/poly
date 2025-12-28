#!/bin/bash
# Lance les 4 bots en parallèle (1 bot par pair)
# Usage: ./start_all_bots.sh [--live] [--shares N]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Arguments
LIVE_FLAG=""
SHARES="5"

while [[ $# -gt 0 ]]; do
    case $1 in
        --live)
            LIVE_FLAG="--live --yes"
            shift
            ;;
        --shares)
            SHARES="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "=============================================="
echo "  LANCEMENT 4 BOTS (1 bot = 1 pair)"
echo "=============================================="
echo "Mode: ${LIVE_FLAG:-SIMULATION}"
echo "Shares: $SHARES par trade"
echo "=============================================="

# Activer venv si présent
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Créer dossier logs
mkdir -p logs

# Lancer les 4 bots en background
echo ""
echo "Lancement BTC..."
python3 bot_btc.py $LIVE_FLAG --shares $SHARES > logs/bot_btc_stdout.log 2>&1 &
PID_BTC=$!
echo "  PID: $PID_BTC"

echo "Lancement ETH..."
python3 bot_eth.py $LIVE_FLAG --shares $SHARES > logs/bot_eth_stdout.log 2>&1 &
PID_ETH=$!
echo "  PID: $PID_ETH"

echo "Lancement XRP..."
python3 bot_xrp.py $LIVE_FLAG --shares $SHARES > logs/bot_xrp_stdout.log 2>&1 &
PID_XRP=$!
echo "  PID: $PID_XRP"

echo "Lancement SOL..."
python3 bot_sol.py $LIVE_FLAG --shares $SHARES > logs/bot_sol_stdout.log 2>&1 &
PID_SOL=$!
echo "  PID: $PID_SOL"

# Sauvegarder les PIDs
echo "$PID_BTC" > logs/pid_btc.txt
echo "$PID_ETH" > logs/pid_eth.txt
echo "$PID_XRP" > logs/pid_xrp.txt
echo "$PID_SOL" > logs/pid_sol.txt

echo ""
echo "=============================================="
echo "  4 BOTS LANCÉS!"
echo "=============================================="
echo ""
echo "Pour voir les logs:"
echo "  tail -f logs/bot_btc.log"
echo "  tail -f logs/bot_eth.log"
echo "  tail -f logs/bot_xrp.log"
echo "  tail -f logs/bot_sol.log"
echo ""
echo "Pour arrêter tous les bots:"
echo "  ./stop_all_bots.sh"
echo ""

# Attendre un des processus (pour garder le script actif si exécuté en foreground)
wait
