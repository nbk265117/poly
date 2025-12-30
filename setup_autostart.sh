#!/bin/bash
# ============================================================
# SETUP AUTOSTART - Configure les bots pour démarrer automatiquement
# au boot du VPS avec systemd + alertes Telegram
# ============================================================

echo "=========================================="
echo "🔧 Configuration Auto-Start & Alertes"
echo "=========================================="

POLY_DIR="/home/ubuntu/poly"

# 1. Créer les services systemd pour chaque bot
echo "📝 Création des services systemd..."

# Service ETH
sudo tee /etc/systemd/system/bot-eth.service > /dev/null << 'EOF'
[Unit]
Description=Polymarket Bot ETH
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/poly
Environment=PATH=/home/ubuntu/poly/venv/bin:/usr/bin
ExecStart=/home/ubuntu/poly/venv/bin/python bot_simple.py --live --yes --shares 10 --symbols ETH
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Service BTC
sudo tee /etc/systemd/system/bot-btc.service > /dev/null << 'EOF'
[Unit]
Description=Polymarket Bot BTC
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/poly
Environment=PATH=/home/ubuntu/poly/venv/bin:/usr/bin
ExecStart=/home/ubuntu/poly/venv/bin/python bot_simple.py --live --yes --shares 7 --symbols BTC
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Service XRP
sudo tee /etc/systemd/system/bot-xrp.service > /dev/null << 'EOF'
[Unit]
Description=Polymarket Bot XRP
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/poly
Environment=PATH=/home/ubuntu/poly/venv/bin:/usr/bin
ExecStart=/home/ubuntu/poly/venv/bin/python bot_simple.py --live --yes --shares 5 --symbols XRP
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Services créés"

# 2. Service pour alerte au démarrage
echo "📝 Création du service d'alerte startup..."

sudo tee /etc/systemd/system/bot-startup-alert.service > /dev/null << 'EOF'
[Unit]
Description=Bot Startup Alert
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
ExecStart=/home/ubuntu/poly/alert_startup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service alerte créé"

# 3. Activer tous les services
echo "🔄 Activation des services..."

sudo systemctl daemon-reload
sudo systemctl enable bot-eth.service
sudo systemctl enable bot-btc.service
sudo systemctl enable bot-xrp.service
sudo systemctl enable bot-startup-alert.service

echo "✅ Services activés"

# 4. Arrêter les anciens bots (lancés manuellement)
echo "🛑 Arrêt des anciens processus..."
pkill -f "bot_simple.py" 2>/dev/null
sleep 2

# 5. Démarrer les nouveaux services
echo "🚀 Démarrage des services..."
sudo systemctl start bot-eth.service
sudo systemctl start bot-btc.service
sudo systemctl start bot-xrp.service

sleep 3

# 6. Vérifier le status
echo ""
echo "=========================================="
echo "📊 STATUS DES SERVICES"
echo "=========================================="
sudo systemctl status bot-eth.service --no-pager | head -5
echo "---"
sudo systemctl status bot-btc.service --no-pager | head -5
echo "---"
sudo systemctl status bot-xrp.service --no-pager | head -5

# 7. Configurer le heartbeat (toutes les heures)
echo ""
echo "💓 Configuration du heartbeat..."

chmod +x $POLY_DIR/heartbeat.sh
chmod +x $POLY_DIR/alert_startup.sh

# Ajouter au cron
(crontab -l 2>/dev/null | grep -v "heartbeat.sh"; echo "0 * * * * $POLY_DIR/heartbeat.sh >> $POLY_DIR/logs/heartbeat.log 2>&1") | crontab -

echo "✅ Heartbeat configuré (toutes les heures)"

# 8. Résumé
echo ""
echo "=========================================="
echo "✅ CONFIGURATION TERMINÉE!"
echo "=========================================="
echo ""
echo "🤖 Bots configurés comme services systemd:"
echo "   • bot-eth.service (10 shares)"
echo "   • bot-btc.service (7 shares)"
echo "   • bot-xrp.service (5 shares)"
echo ""
echo "⚡ Auto-start au boot: ACTIVÉ"
echo "🔄 Auto-restart si crash: ACTIVÉ (après 30s)"
echo "📱 Alerte Telegram au reboot: ACTIVÉ"
echo "💓 Heartbeat Telegram: Toutes les heures"
echo ""
echo "📋 Commandes utiles:"
echo "   sudo systemctl status bot-eth"
echo "   sudo systemctl restart bot-eth"
echo "   sudo journalctl -u bot-eth -f"
echo ""
