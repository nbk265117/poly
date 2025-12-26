#!/bin/bash
# Quick Start Script pour le Robot de Trading Polymarket

set -e

echo "=================================="
echo "🤖 ROBOT DE TRADING POLYMARKET"
echo "=================================="
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

echo "✅ Python 3 détecté"

# Créer l'environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
echo "🔧 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installer les dépendances
echo "📥 Installation des dépendances..."
pip install -r requirements.txt --quiet

# Créer les répertoires nécessaires
echo "📁 Création des répertoires..."
mkdir -p data/historical data/cache logs backtest_results

# Vérifier le fichier .env
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env manquant"
    echo "   Créez le fichier .env avec vos clés API"
    echo "   Voir .env.example pour un modèle"
    exit 1
fi

echo "✅ Configuration OK"
echo ""
echo "=================================="
echo "Options disponibles:"
echo "=================================="
echo "1. Télécharger les données historiques"
echo "2. Lancer le backtesting"
echo "3. Lancer le robot (simulation)"
echo "4. Quitter"
echo ""
read -p "Votre choix (1-4): " choice

case $choice in
    1)
        echo "📊 Téléchargement des données..."
        python scripts/download_data_15m.py
        ;;
    2)
        echo "📈 Lancement du backtesting..."
        python backtest_main.py --plot --save-results
        ;;
    3)
        echo "🚀 Lancement du robot..."
        python main.py
        ;;
    4)
        echo "👋 Au revoir!"
        exit 0
        ;;
    *)
        echo "❌ Choix invalide"
        exit 1
        ;;
esac

echo ""
echo "✅ Terminé!"

