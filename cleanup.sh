#!/bin/bash
# =============================================================================
# SCRIPT DE NETTOYAGE AUTOMATIQUE
# Supprime les logs, scripts obsoletes et fichiers temporaires
# =============================================================================

set -e

PROJECT_DIR="/Users/mac/poly"
cd "$PROJECT_DIR"

echo "=============================================="
echo "NETTOYAGE DU PROJET POLYMARKET"
echo "=============================================="

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Compteurs
DELETED_FILES=0
DELETED_SIZE=0

# Fonction pour supprimer avec confirmation
delete_file() {
    local file=$1
    if [ -f "$file" ]; then
        local size=$(du -k "$file" | cut -f1)
        rm -f "$file"
        echo -e "  ${RED}[DELETED]${NC} $file (${size}KB)"
        ((DELETED_FILES++))
        ((DELETED_SIZE+=size))
    fi
}

# =============================================================================
# 1. SUPPRIMER LES LOGS
# =============================================================================
echo -e "\n${YELLOW}[1/5] Nettoyage des logs...${NC}"

# Logs dans le dossier logs/
if [ -d "logs" ]; then
    find logs -name "*.log" -type f -exec rm -f {} \;
    echo -e "  ${GREEN}[OK]${NC} Logs supprimés dans logs/"
fi

# Fichiers .log à la racine
for log in *.log; do
    [ -f "$log" ] && delete_file "$log"
done

# =============================================================================
# 2. SUPPRIMER LES SCRIPTS D'ANALYSE OBSOLETES
# =============================================================================
echo -e "\n${YELLOW}[2/5] Suppression des scripts d'analyse obsolètes...${NC}"

OBSOLETE_SCRIPTS=(
    "analyze_adnane.py"
    "analyze_advanced.py"
    "analyze_all_pairs_hours.py"
    "analyze_best_config.py"
    "analyze_hours_days.py"
    "analyze_market.py"
    "analyze_mean_reversion.py"
    "analyze_strategy.py"
    "analyze_with_sol.py"
    "apply_loss_patterns.py"
    "backtest_2024_2025.py"
    "backtest_53c.py"
    "backtest_blacklist.py"
    "backtest_fast.py"
    "backtest_multi_asset.py"
    "backtest_simple.py"
    "backtest_yearly.py"
    "demo_strategy.py"
    "final_optimized_config.py"
    "find_best_config.py"
    "find_max_55.py"
    "optimize_55wr.py"
    "optimize_for_15k.py"
    "optimize_strategy_full.py"
    "optimize_trades.py"
    "search_60_60.py"
    "simulate_15k.py"
    "test_new_indicators.py"
    "strategy_price_action_ftfc.py"
    "strategy_ict.py"
    "strategy_ict_rsi_stoch.py"
    "strategy_hybrid_fast.py"
    "strategy_hybrid_v2.py"
    "strategy_max_pnl.py"
)

for script in "${OBSOLETE_SCRIPTS[@]}"; do
    delete_file "$script"
done

# =============================================================================
# 3. SUPPRIMER LES FICHIERS TEMPORAIRES
# =============================================================================
echo -e "\n${YELLOW}[3/5] Suppression des fichiers temporaires...${NC}"

# Cache Python
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
echo -e "  ${GREEN}[OK]${NC} Cache Python nettoyé"

# Fichiers DS_Store
find . -name ".DS_Store" -delete 2>/dev/null || true
echo -e "  ${GREEN}[OK]${NC} Fichiers .DS_Store supprimés"

# Fichiers backup
find . -name "*.bak" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true
echo -e "  ${GREEN}[OK]${NC} Fichiers backup supprimés"

# =============================================================================
# 4. SUPPRIMER LES IMAGES DE BACKTEST
# =============================================================================
echo -e "\n${YELLOW}[4/5] Suppression des images de backtest...${NC}"

for img in backtest_*.png; do
    [ -f "$img" ] && delete_file "$img"
done

# =============================================================================
# 5. NETTOYER LES ANCIENS BOTS (garder seulement la nouvelle stratégie)
# =============================================================================
echo -e "\n${YELLOW}[5/5] Nettoyage des anciens bots...${NC}"

OLD_BOTS=(
    "bot_btc.py"
    "bot_eth.py"
    "bot_xrp.py"
    "bot_sol.py"
)

for bot in "${OLD_BOTS[@]}"; do
    delete_file "$bot"
done

# =============================================================================
# RÉSUMÉ
# =============================================================================
echo -e "\n=============================================="
echo -e "${GREEN}NETTOYAGE TERMINÉ${NC}"
echo "=============================================="
echo -e "Fichiers supprimés: ${RED}$DELETED_FILES${NC}"
echo -e "Espace libéré: ${GREEN}${DELETED_SIZE}KB${NC}"

# Liste des fichiers restants
echo -e "\n${YELLOW}Fichiers Python restants:${NC}"
ls -la *.py 2>/dev/null || echo "  Aucun fichier .py à la racine"

echo -e "\n${YELLOW}Structure du projet:${NC}"
echo "  docs/          - Site web Netlify"
echo "  src/           - Code source"
echo "  scripts/       - Scripts utilitaires"
echo "  config.yaml    - Configuration"
echo "  backtest_final.py - Backtest principal"
echo "  strategy_final_15k.py - Stratégie optimisée"
