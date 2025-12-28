#!/bin/bash
# Installe les 4 services systemd pour les bots
# À exécuter sur le VPS en tant que root

echo "=============================================="
echo "  INSTALLATION 4 BOTS POLYMARKET"
echo "=============================================="

# Vérifier qu'on est root
if [ "$EUID" -ne 0 ]; then
    echo "Erreur: Exécutez ce script en tant que root"
    exit 1
fi

# Arrêter l'ancien bot si existant
echo ""
echo "1. Arrêt ancien bot..."
systemctl stop polybot 2>/dev/null
systemctl disable polybot 2>/dev/null

# Copier les nouveaux services
echo ""
echo "2. Installation des services..."
cp /root/poly/systemd/polybot-btc.service /etc/systemd/system/
cp /root/poly/systemd/polybot-eth.service /etc/systemd/system/
cp /root/poly/systemd/polybot-xrp.service /etc/systemd/system/
cp /root/poly/systemd/polybot-sol.service /etc/systemd/system/

# Recharger systemd
echo ""
echo "3. Rechargement systemd..."
systemctl daemon-reload

# Activer les services
echo ""
echo "4. Activation des services..."
systemctl enable polybot-btc
systemctl enable polybot-eth
systemctl enable polybot-xrp
systemctl enable polybot-sol

# Créer dossier logs
mkdir -p /root/poly/logs

# Démarrer les services
echo ""
echo "5. Démarrage des 4 bots..."
systemctl start polybot-btc
sleep 2
systemctl start polybot-eth
sleep 2
systemctl start polybot-xrp
sleep 2
systemctl start polybot-sol

# Vérifier le statut
echo ""
echo "=============================================="
echo "  STATUT DES 4 BOTS"
echo "=============================================="
for pair in btc eth xrp sol; do
    status=$(systemctl is-active polybot-$pair)
    if [ "$status" = "active" ]; then
        echo "  polybot-$pair: ACTIF"
    else
        echo "  polybot-$pair: $status"
    fi
done

echo ""
echo "=============================================="
echo "  COMMANDES UTILES"
echo "=============================================="
echo ""
echo "Voir les logs:"
echo "  journalctl -u polybot-btc -f"
echo "  tail -f /root/poly/logs/bot_btc.log"
echo ""
echo "Redémarrer un bot:"
echo "  systemctl restart polybot-btc"
echo ""
echo "Arrêter tous les bots:"
echo "  systemctl stop polybot-btc polybot-eth polybot-xrp polybot-sol"
echo ""
echo "Statut:"
echo "  systemctl status polybot-btc polybot-eth polybot-xrp polybot-sol"
echo ""
