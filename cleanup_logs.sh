#!/bin/bash
# ============================================================
# CLEANUP - Nettoyage des logs et libération d'espace
# ============================================================
# Usage: ./cleanup_logs.sh
# Cron: 0 0 * * * /home/ubuntu/poly/cleanup_logs.sh >> /home/ubuntu/poly/logs/cleanup.log 2>&1
# ============================================================

POLY_DIR="/home/ubuntu/poly"
LOG_DIR="$POLY_DIR/logs"
MAX_LOG_SIZE_MB=10
KEEP_DAYS=3

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1"
}

log "=========================================="
log "🧹 CLEANUP - Nettoyage des logs"
log "=========================================="

# Afficher l'espace avant
BEFORE=$(df -h / | awk 'NR==2 {print $4}')
log "Espace disponible avant: $BEFORE"

# 1. Tronquer les logs trop gros (garder les 1000 dernières lignes)
log "📄 Troncature des gros fichiers logs..."
for logfile in $LOG_DIR/*.log; do
    if [ -f "$logfile" ]; then
        SIZE=$(du -m "$logfile" 2>/dev/null | cut -f1)
        if [ "$SIZE" -gt "$MAX_LOG_SIZE_MB" ]; then
            log "  - $logfile: ${SIZE}MB -> Troncature"
            tail -1000 "$logfile" > "$logfile.tmp" && mv "$logfile.tmp" "$logfile"
        fi
    fi
done

# 2. Supprimer les vieux fichiers logs (> 3 jours)
log "🗑️ Suppression des logs > $KEEP_DAYS jours..."
find $LOG_DIR -name "*.log.*" -mtime +$KEEP_DAYS -delete 2>/dev/null
find $LOG_DIR -name "*.log.bak" -mtime +$KEEP_DAYS -delete 2>/dev/null

# 3. Supprimer les fichiers temporaires Python
log "🐍 Nettoyage cache Python..."
find $POLY_DIR -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find $POLY_DIR -name "*.pyc" -delete 2>/dev/null
find $POLY_DIR -name "*.pyo" -delete 2>/dev/null

# 4. Vider les fichiers .npy et cache si présents
if [ -d "$POLY_DIR/data/cache" ]; then
    log "💾 Nettoyage cache data..."
    find $POLY_DIR/data/cache -mtime +7 -delete 2>/dev/null
fi

# 5. Nettoyer les logs système si possible
log "🖥️ Nettoyage logs système..."
sudo journalctl --vacuum-time=3d 2>/dev/null || true

# 6. Nettoyer apt cache
log "📦 Nettoyage apt cache..."
sudo apt-get clean 2>/dev/null || true
sudo apt-get autoremove -y 2>/dev/null || true

# Afficher l'espace après
AFTER=$(df -h / | awk 'NR==2 {print $4}')
log "Espace disponible après: $AFTER"

# Afficher la taille des logs actuels
log "------------------------------------------"
log "📊 Taille actuelle des logs:"
du -sh $LOG_DIR/*.log 2>/dev/null | while read size file; do
    log "  $size - $(basename $file)"
done

TOTAL=$(du -sh $LOG_DIR 2>/dev/null | cut -f1)
log "  Total: $TOTAL"

log "=========================================="
log "✅ Nettoyage terminé"
log "=========================================="
