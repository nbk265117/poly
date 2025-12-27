#!/usr/bin/env python3
"""
CONFIGURATION POLYMARKET
Script pour configurer et tester l'acces a Polymarket
"""

import os
import sys
from pathlib import Path

# Ajouter le path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

def check_prerequisites():
    """Verifie les prerequis"""
    print("=" * 60)
    print("CONFIGURATION POLYMARKET")
    print("=" * 60)
    print()

    # 1. Verifier py-clob-client
    print("1. Verification py-clob-client...")
    try:
        from py_clob_client.client import ClobClient
        print("   [OK] py-clob-client installe")
    except ImportError:
        print("   [ERREUR] py-clob-client non installe")
        print("   Executez: pip install py-clob-client")
        return False

    # 2. Verifier cle privee
    print()
    print("2. Verification cle privee...")
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY', '')
    if private_key and private_key.startswith('0x'):
        print(f"   [OK] Cle privee configuree: {private_key[:10]}...")
    else:
        print("   [ATTENTION] Cle privee non configuree")
        print()
        print("   Pour obtenir votre cle privee:")
        print("   a) Ouvrez MetaMask")
        print("   b) Cliquez sur les 3 points > Details du compte")
        print("   c) Cliquez sur 'Exporter la cle privee'")
        print("   d) Entrez votre mot de passe MetaMask")
        print("   e) Copiez la cle (commence par 0x...)")
        print()
        print("   Ajoutez dans .env:")
        print("   POLYMARKET_PRIVATE_KEY=0xVotreClePrivee...")
        return False

    # 3. Verifier environment
    print()
    print("3. Verification environment...")
    env = os.getenv('ENVIRONMENT', 'development')
    print(f"   Mode actuel: {env}")
    if env == 'production':
        print("   [ATTENTION] Mode PRODUCTION - Argent reel!")
    else:
        print("   [OK] Mode SIMULATION - Pas d'argent reel")

    return True


def test_connection():
    """Teste la connexion a Polymarket"""
    from py_clob_client.client import ClobClient

    print()
    print("4. Test de connexion Polymarket...")

    private_key = os.getenv('POLYMARKET_PRIVATE_KEY', '')
    if not private_key:
        print("   [ERREUR] Cle privee requise pour ce test")
        return False

    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137,
            signature_type=0
        )

        # Generer les credentials
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)

        print(f"   [OK] Connecte!")
        print(f"   API Key: {creds.api_key[:15]}...")

        # Recuperer le solde
        print()
        print("5. Verification du solde...")
        try:
            balance = client.get_balance_allowance()
            if balance:
                print(f"   Balance: {balance}")
            else:
                print("   [INFO] Impossible de recuperer le solde")
        except Exception as e:
            print(f"   [INFO] {e}")

        return True

    except Exception as e:
        print(f"   [ERREUR] {e}")
        return False


def find_btc_markets():
    """Recherche les marches BTC Up/Down"""
    from py_clob_client.client import ClobClient

    print()
    print("6. Recherche des marches BTC Up/Down...")

    try:
        # Client sans authentification pour lire les marches
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137
        )

        # Recuperer les marches
        markets = client.get_markets()

        btc_markets = []
        for market in markets:
            question = market.get('question', '').lower()
            if 'btc' in question and ('up' in question or 'down' in question):
                btc_markets.append(market)

        if btc_markets:
            print(f"   [OK] {len(btc_markets)} marches BTC trouves")
            for m in btc_markets[:5]:
                print(f"   - {m.get('question', 'N/A')[:50]}...")
                print(f"     ID: {m.get('condition_id', 'N/A')[:20]}...")
        else:
            print("   [INFO] Aucun marche BTC Up/Down trouve")
            print("   Le marche est peut-etre ferme ou pas encore ouvert")

    except Exception as e:
        print(f"   [ERREUR] {e}")


def main():
    # Verifier les prerequis
    if not check_prerequisites():
        print()
        print("=" * 60)
        print("Corrigez les erreurs ci-dessus avant de continuer")
        print("=" * 60)
        return

    # Tester la connexion si cle presente
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY', '')
    if private_key:
        test_connection()
        find_btc_markets()

    print()
    print("=" * 60)
    print("PROCHAINES ETAPES")
    print("=" * 60)
    print()
    print("1. Si pas fait: Ajoutez votre cle privee dans .env")
    print("   POLYMARKET_PRIVATE_KEY=0xVotreCle...")
    print()
    print("2. Deposez des USDC sur votre compte Polymarket")
    print("   https://polymarket.com/deposit")
    print()
    print("3. Pour tester en simulation:")
    print("   python live_trader.py --symbols BTC/USDT --bet 2")
    print()
    print("4. Pour trader en reel (ATTENTION!):")
    print("   a) Modifiez .env: ENVIRONMENT=production")
    print("   b) python live_trader.py --live --symbols BTC/USDT --bet 2")
    print()


if __name__ == "__main__":
    main()
