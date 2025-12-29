#!/bin/bash
# ============================================================
# SETUP MONITORING - Installation watchdog + cleanup + cron
# ============================================================

echo "=========================================="
echo "🔧 Installation du monitoring"
echo "=========================================="

POLY_DIR="/home/ubuntu/poly"

# Rendre les scripts exécutables
chmod +x $POLY_DIR/watchdog.sh
chmod +x $POLY_DIR/cleanup_logs.sh

echo "✅ Scripts rendus exécutables"

# Créer le dossier logs s'il n'existe pas
mkdir -p $POLY_DIR/logs

# Configurer les cron jobs
echo "📅 Configuration des cron jobs..."

# Supprimer les anciens crons pour éviter les doublons
crontab -l 2>/dev/null | grep -v "watchdog.sh" | grep -v "cleanup_logs.sh" > /tmp/crontab.tmp

# Ajouter les nouveaux crons
echo "# Watchdog - vérifie les bots toutes les 5 minutes" >> /tmp/crontab.tmp
echo "*/5 * * * * $POLY_DIR/watchdog.sh >> $POLY_DIR/logs/watchdog.log 2>&1" >> /tmp/crontab.tmp
echo "" >> /tmp/crontab.tmp
echo "# Cleanup - nettoie les logs tous les jours à minuit" >> /tmp/crontab.tmp
echo "0 0 * * * $POLY_DIR/cleanup_logs.sh >> $POLY_DIR/logs/cleanup.log 2>&1" >> /tmp/crontab.tmp

# Installer les crons
crontab /tmp/crontab.tmp
rm /tmp/crontab.tmp

echo "✅ Cron jobs installés"
echo ""
echo "📋 Cron jobs actifs:"
crontab -l

echo ""
echo "=========================================="
echo "✅ Monitoring installé avec succès!"
echo "=========================================="
echo ""
echo "🔍 Watchdog: Vérifie toutes les 5 min"
echo "🧹 Cleanup:  Nettoie tous les jours à minuit"
echo ""
echo "Pour tester manuellement:"
echo "  ./watchdog.sh      # Vérifier les bots"
echo "  ./cleanup_logs.sh  # Nettoyer les logs"
echo ""
