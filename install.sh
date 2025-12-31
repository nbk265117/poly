#!/bin/bash
# Script d'installation automatique pour le Robot de Trading Polymarket

set -e

echo "=================================="
echo "🤖 INSTALLATION DU ROBOT"
echo "=================================="
echo ""

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "requirements.txt" ]; then
    echo "❌ Erreur: requirements.txt non trouvé"
    echo "   Assurez-vous d'être dans le répertoire /Users/mac/poly"
    exit 1
fi

# Vérifier l'environnement virtuel
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Environnement virtuel non activé"
    
    if [ -d "venv" ]; then
        echo "📦 Activation de l'environnement virtuel existant..."
        source venv/bin/activate
    else
        echo "📦 Création de l'environnement virtuel..."
        python3 -m venv venv
        source venv/bin/activate
    fi
fi

echo "✅ Environnement virtuel actif: $VIRTUAL_ENV"
echo ""

# Mettre à jour pip
echo "🔧 Mise à jour de pip, setuptools et wheel..."
pip install --upgrade pip setuptools wheel --quiet

echo ""
echo "=================================="
echo "📥 INSTALLATION DES PACKAGES"
echo "=================================="
echo ""

# Installation par groupe pour meilleur diagnostic
echo "1/5 Installation des dépendances de base..."
pip install ccxt pandas numpy || {
    echo "⚠️  Tentative avec versions spécifiques..."
    pip install ccxt
    pip install "pandas>=2.2.0"
    pip install "numpy>=1.26.0"
}

echo ""
echo "2/5 Installation des outils de configuration..."
pip install python-dotenv pyyaml requests pytz schedule

echo ""
echo "3/5 Installation de Telegram bot..."
pip install python-telegram-bot

echo ""
echo "4/5 Installation des outils de visualisation..."
pip install matplotlib

echo ""
echo "5/5 Installation des indicateurs techniques..."
pip install pandas-ta || echo "⚠️  pandas-ta: erreur (non critique)"

echo ""
echo "Tentative d'installation py-clob-client (Polymarket)..."
pip install py-clob-client || {
    echo "⚠️  py-clob-client non installé (mode simulation disponible)"
}

echo ""
echo "=================================="
echo "✅ INSTALLATION TERMINÉE"
echo "=================================="
echo ""

# Créer les répertoires nécessaires
echo "📁 Création des répertoires..."
mkdir -p data/historical data/cache logs backtest_results

# Vérifier les imports
echo "🧪 Test des imports..."
python3 << 'PYEOF'
import sys

packages = {
    'ccxt': 'CCXT (Binance API)',
    'pandas': 'Pandas',
    'numpy': 'NumPy',
    'telegram': 'Telegram Bot',
    'yaml': 'PyYAML',
    'dotenv': 'Python-dotenv',
    'schedule': 'Schedule',
    'matplotlib': 'Matplotlib'
}

failed = []
for package, name in packages.items():
    try:
        __import__(package)
        print(f"  ✅ {name}")
    except ImportError:
        print(f"  ❌ {name}")
        failed.append(name)

if failed:
    print(f"\n⚠️  Packages non installés: {', '.join(failed)}")
    print("   Le robot peut fonctionner en mode limité")
else:
    print("\n🎉 Tous les packages essentiels sont installés!")

PYEOF

echo ""
echo "=================================="
echo "🎯 PROCHAINES ÉTAPES"
echo "=================================="
echo ""
echo "1. Créer le fichier .env avec vos clés API:"
echo "   nano .env"
echo ""
echo "2. Télécharger les données historiques:"
echo "   python scripts/download_data_15m.py"
echo ""
echo "3. Lancer le backtesting:"
echo "   python backtest_main.py --plot"
echo ""
echo "4. Lancer le robot en simulation:"
echo "   python main.py"
echo ""
echo "✅ Installation complète!"





