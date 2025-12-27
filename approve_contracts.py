#!/usr/bin/env python3
"""
Script pour approuver les contrats Polymarket
Permet de trader avec signature_type=0 (EOA direct)
"""

import os
import sys
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Configuration
POLYGON_RPC = "https://polygon-rpc.com"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Polymarket contracts a approuver
CONTRACTS = {
    "Exchange": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NegRisk Exchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "CTF Exchange": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
}

# Max uint256 pour approval illimite
MAX_APPROVAL = 2**256 - 1

# ABI minimal pour approve
ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def main():
    print("=" * 60)
    print("APPROBATION DES CONTRATS POLYMARKET")
    print("=" * 60)
    print()

    # Get private key
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        print("Erreur: POLYMARKET_PRIVATE_KEY non defini dans .env")
        sys.exit(1)

    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        print("Erreur: Impossible de se connecter a Polygon")
        sys.exit(1)

    print(f"Connecte a Polygon (Chain ID: {w3.eth.chain_id})")

    # Get account
    account = Account.from_key(private_key)
    address = account.address
    print(f"Adresse: {address}")

    # Check POL balance for gas
    pol_balance = w3.eth.get_balance(address)
    pol_balance_eth = w3.from_wei(pol_balance, 'ether')
    print(f"Balance POL: {pol_balance_eth:.4f}")

    if pol_balance_eth < 0.1:
        print("Attention: Balance POL faible pour les frais de gas")

    # USDC.e contract
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E),
        abi=ERC20_ABI
    )

    print()
    print("Verification des allowances actuelles...")
    print("-" * 60)

    needs_approval = []
    for name, contract_addr in CONTRACTS.items():
        allowance = usdc.functions.allowance(
            address,
            Web3.to_checksum_address(contract_addr)
        ).call()

        if allowance > 10**10:  # > 10000 USDC
            print(f"  [OK] {name}: Deja approuve")
        else:
            print(f"  [!] {name}: Non approuve (allowance: {allowance/10**6:.2f})")
            needs_approval.append((name, contract_addr))

    if not needs_approval:
        print()
        print("Tous les contrats sont deja approuves!")
        return

    print()
    print(f"{len(needs_approval)} contrat(s) a approuver:")
    for name, _ in needs_approval:
        print(f"  - {name}")

    print()
    confirm = input("Confirmer les approbations? (oui/non): ")
    if confirm.lower() != "oui":
        print("Annule.")
        return

    print()
    print("Envoi des transactions d'approbation...")
    print("-" * 60)

    nonce = w3.eth.get_transaction_count(address)

    for name, contract_addr in needs_approval:
        print(f"\nApprobation de {name}...")

        try:
            # Build transaction
            tx = usdc.functions.approve(
                Web3.to_checksum_address(contract_addr),
                MAX_APPROVAL
            ).build_transaction({
                'from': address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 137
            })

            # Sign and send
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            print(f"  TX envoyee: {tx_hash.hex()}")
            print(f"  En attente de confirmation...")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"  [OK] Approuve avec succes!")
            else:
                print(f"  [ERREUR] Transaction echouee")

            nonce += 1

        except Exception as e:
            print(f"  [ERREUR] {e}")

    print()
    print("=" * 60)
    print("TERMINE!")
    print("Vous pouvez maintenant trader sur Polymarket avec signature_type=0")
    print("=" * 60)


if __name__ == "__main__":
    main()
