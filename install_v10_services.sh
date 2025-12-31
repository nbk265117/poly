#!/bin/bash
# ============================================================
# INSTALL V10 SERVICES - Configuration complete du monitoring
# ============================================================

set -e

POLY_DIR="/home/ubuntu/poly"
echo "============================================================"
echo "Installation des services V10"
echo "============================================================"

# 1. Stop old services
echo ""
echo "[1/6] Arret des anciens services..."
sudo systemctl stop bot-btc.service 2>/dev/null || true
sudo systemctl stop bot-eth.service 2>/dev/null || true
sudo systemctl stop bot-xrp.service 2>/dev/null || true
sudo systemctl stop bot-startup-alert.service 2>/dev/null || true
sudo systemctl disable bot-btc.service 2>/dev/null || true
sudo systemctl disable bot-eth.service 2>/dev/null || true
sudo systemctl disable bot-xrp.service 2>/dev/null || true
sudo systemctl disable bot-startup-alert.service 2>/dev/null || true

# Kill any running bots
pkill -f "bot_simple.py" 2>/dev/null || true
pkill -f "bot_v10" 2>/dev/null || true
pkill -f "watchdog_v10" 2>/dev/null || true
sleep 2

# 2. Make scripts executable
echo "[2/6] Configuration des permissions..."
chmod +x $POLY_DIR/heartbeat_v10.sh
chmod +x $POLY_DIR/alert_startup_v10.sh
chmod +x $POLY_DIR/cleanup_logs.sh
chmod +x $POLY_DIR/watchdog_v10.py

# 3. Install systemd services
echo "[3/6] Installation des services systemd..."
sudo cp $POLY_DIR/systemd/watchdog-v10.service /etc/systemd/system/
sudo cp $POLY_DIR/systemd/startup-alert-v10.service /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Enable and start services
echo "[4/6] Activation des services..."
sudo systemctl enable watchdog-v10.service
sudo systemctl enable startup-alert-v10.service
sudo systemctl start watchdog-v10.service

# 5. Setup crontab
echo "[5/6] Configuration du crontab..."
CRON_FILE="/tmp/poly_cron"
cat > $CRON_FILE << 'CRON'
# Polymarket V10 Monitoring
# Heartbeat toutes les heures
0 * * * * /home/ubuntu/poly/heartbeat_v10.sh >> /home/ubuntu/poly/logs/heartbeat.log 2>&1

# Cleanup logs tous les jours a minuit
0 0 * * * /home/ubuntu/poly/cleanup_logs.sh >> /home/ubuntu/poly/logs/cleanup.log 2>&1
CRON
crontab $CRON_FILE
rm $CRON_FILE

# 6. Verify installation
echo "[6/6] Verification..."
sleep 5

echo ""
echo "============================================================"
echo "STATUS DES SERVICES"
echo "============================================================"

# Check watchdog service
if systemctl is-active --quiet watchdog-v10.service; then
    echo "✅ watchdog-v10.service: ACTIVE"
else
    echo "❌ watchdog-v10.service: INACTIVE"
fi

# Check startup alert service
if systemctl is-enabled --quiet startup-alert-v10.service; then
    echo "✅ startup-alert-v10.service: ENABLED"
else
    echo "❌ startup-alert-v10.service: DISABLED"
fi

# Check bots running
echo ""
echo "BOTS V10:"
for bot in btc eth xrp; do
    if pgrep -f "bot_v10_${bot}.py" > /dev/null; then
        PID=$(pgrep -f "bot_v10_${bot}.py")
        echo "✅ bot_v10_${bot}: Running (PID $PID)"
    else
        echo "❌ bot_v10_${bot}: Not running"
    fi
done

# Check crontab
echo ""
echo "CRONTAB:"
crontab -l | grep -v "^#" | grep -v "^$" | while read line; do
    echo "  $line"
done

echo ""
echo "============================================================"
echo "Installation terminee!"
echo "============================================================"
echo ""
echo "Commandes utiles:"
echo "  sudo systemctl status watchdog-v10"
echo "  sudo journalctl -u watchdog-v10 -f"
echo "  tail -f $POLY_DIR/logs/watchdog_v10.log"
echo ""
