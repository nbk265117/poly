#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'installation Python pour le Robot de Trading Polymarket
Alternative au script bash pour compatibilité multi-plateforme
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Exécute une commande et affiche le résultat"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=isinstance(cmd, str)
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Erreur: {e}")
        return False

def check_python_version():
    """Vérifie la version de Python"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ requis")
        return False
    
    if version.major == 3 and version.minor >= 13:
        print("✅ Python 3.13 détecté (versions récentes utilisées)")
    
    return True

def install_packages():
    """Installe les packages Python"""
    
    print("\n" + "=" * 50)
    print("🤖 INSTALLATION DU ROBOT DE TRADING")
    print("=" * 50)
    
    # Vérifier Python
    if not check_python_version():
        sys.exit(1)
    
    # Mettre à jour pip
    print("\n🔧 Mise à jour de pip...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        capture_output=True
    )
    
    # Packages essentiels
    essential_packages = [
        ("ccxt", "CCXT (Binance API)"),
        ("pandas>=2.2.0", "Pandas"),
        ("numpy>=1.26.0", "NumPy"),
        ("python-telegram-bot>=20.0", "Telegram Bot"),
        ("python-dotenv>=1.0.0", "Python-dotenv"),
        ("pyyaml>=6.0.0", "PyYAML"),
        ("schedule>=1.2.0", "Schedule"),
        ("requests>=2.31.0", "Requests"),
        ("pytz>=2024.0", "Pytz"),
        ("matplotlib>=3.8.0", "Matplotlib"),
    ]
    
    print("\n" + "=" * 50)
    print("📥 INSTALLATION DES PACKAGES ESSENTIELS")
    print("=" * 50)
    
    failed = []
    
    for i, (package, name) in enumerate(essential_packages, 1):
        print(f"\n[{i}/{len(essential_packages)}] Installation de {name}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"  ✅ {name} installé")
        else:
            print(f"  ❌ {name} échoué")
            failed.append(name)
    
    # Packages optionnels
    optional_packages = [
        ("pandas-ta>=0.3.14b0", "Pandas-TA (indicateurs techniques)"),
        ("py-clob-client>=0.20.0", "Polymarket Client"),
    ]
    
    print("\n" + "=" * 50)
    print("📦 INSTALLATION DES PACKAGES OPTIONNELS")
    print("=" * 50)
    
    for package, name in optional_packages:
        print(f"\nInstallation de {name}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"  ✅ {name} installé")
        else:
            print(f"  ⚠️  {name} non installé (non critique)")
    
    return failed

def test_imports():
    """Test les imports des packages"""
    print("\n" + "=" * 50)
    print("🧪 TEST DES IMPORTS")
    print("=" * 50)
    
    packages = {
        'ccxt': 'CCXT (Binance API)',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
        'telegram': 'Telegram Bot',
        'yaml': 'PyYAML',
        'dotenv': 'Python-dotenv',
        'schedule': 'Schedule',
        'matplotlib': 'Matplotlib',
        'requests': 'Requests',
        'pytz': 'Pytz'
    }
    
    failed = []
    
    for package, name in packages.items():
        try:
            __import__(package)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name}")
            failed.append(name)
    
    # Optionnels
    optional = {
        'pandas_ta': 'Pandas-TA',
        'py_clob_client': 'Polymarket Client'
    }
    
    print("\nPackages optionnels:")
    for package, name in optional.items():
        try:
            __import__(package)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ⚠️  {name} (non installé - mode simulation disponible)")
    
    return failed

def create_directories():
    """Crée les répertoires nécessaires"""
    print("\n📁 Création des répertoires...")
    
    directories = [
        'data/historical',
        'data/cache',
        'logs',
        'backtest_results'
    ]
    
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {directory}")

def check_env_file():
    """Vérifie si le fichier .env existe"""
    print("\n🔍 Vérification de la configuration...")
    
    if not Path('.env').exists():
        print("  ⚠️  Fichier .env manquant")
        print("     Créez-le avec vos clés API (voir .env.example)")
        return False
    else:
        print("  ✅ Fichier .env trouvé")
        return True

def main():
    """Point d'entrée principal"""
    
    # Vérifier qu'on est dans le bon répertoire
    if not Path('requirements.txt').exists():
        print("❌ Erreur: requirements.txt non trouvé")
        print("   Exécutez ce script depuis /Users/mac/poly")
        sys.exit(1)
    
    # Installation
    failed = install_packages()
    
    # Test imports
    import_failed = test_imports()
    
    # Créer répertoires
    create_directories()
    
    # Vérifier .env
    env_exists = check_env_file()
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DE L'INSTALLATION")
    print("=" * 50)
    
    if not failed and not import_failed:
        print("\n🎉 Installation réussie!")
        print("✅ Tous les packages essentiels sont installés")
    else:
        print("\n⚠️  Installation partielle")
        if failed:
            print(f"   Packages manquants: {', '.join(failed)}")
        print("   Le robot peut fonctionner en mode limité")
    
    # Prochaines étapes
    print("\n" + "=" * 50)
    print("🎯 PROCHAINES ÉTAPES")
    print("=" * 50)
    
    if not env_exists:
        print("\n1. Créer le fichier .env avec vos clés API")
        print("   (Voir README.md pour les détails)")
    
    print("\n2. Télécharger les données historiques:")
    print("   python scripts/download_data_15m.py")
    
    print("\n3. Lancer le backtesting:")
    print("   python backtest_main.py --plot")
    
    print("\n4. Lancer le robot en simulation:")
    print("   python main.py")
    
    print("\n✅ Installation terminée!")
    print("=" * 50)

if __name__ == "__main__":
    main()


