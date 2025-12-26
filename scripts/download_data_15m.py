#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de téléchargement des données 15m pour le robot de trading
Utilise le script fetch_ohlcv_full_v4.py existant avec les bons paramètres
"""

import sys
import os
import subprocess
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config


def download_data():
    """Télécharge les données historiques 15m pour BTC, ETH, XRP"""
    config = get_config()
    
    # Symboles à télécharger
    symbols = ["BTC", "ETH", "XRP"]
    symbols_str = ",".join(symbols)
    
    # Paramètres
    months = 24  # 2 ans de données
    timeframe = "15m"
    out_dir = str(config.historical_dir)
    
    print("=" * 80)
    print("📊 TÉLÉCHARGEMENT DES DONNÉES HISTORIQUES")
    print("=" * 80)
    print(f"Symboles: {symbols_str}")
    print(f"Timeframe: {timeframe}")
    print(f"Période: {months} mois")
    print(f"Destination: {out_dir}")
    print("=" * 80)
    print()
    
    # Chemin du script
    script_path = Path(__file__).parent / "fetch_ohlcv_full_v4.py"
    
    # Commande
    cmd = [
        sys.executable,
        str(script_path),
        "--symbols", symbols_str,
        "--months", str(months),
        "--timeframe", timeframe,
        "--out-dir", out_dir
    ]
    
    # Ajouter les clés API si disponibles
    if config.binance_api_key:
        cmd.extend(["--api-key", config.binance_api_key])
    if config.binance_api_secret:
        cmd.extend(["--api-secret", config.binance_api_secret])
    
    # Exécuter
    print(f"Exécution: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ Téléchargement terminé avec succès!")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erreur lors du téléchargement: {e}")
        return e.returncode
    except KeyboardInterrupt:
        print("\n⚠️ Téléchargement interrompu par l'utilisateur")
        return 1


if __name__ == "__main__":
    sys.exit(download_data())

