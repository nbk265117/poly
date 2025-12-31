#!/bin/bash
# ============================================================
# CHECK RESULTS - Verifie les resultats des trades (WIN/LOSS)
# Cron: 3,18,33,48 * * * * (3 min apres chaque candle)
# ============================================================

cd /home/ubuntu/poly
source venv/bin/activate

# Verifier les trades en attente
python trade_tracker.py check >> logs/tracker.log 2>&1

# Afficher stats si argument "stats"
if [ "$1" = "stats" ]; then
    python trade_tracker.py stats
fi
