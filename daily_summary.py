#!/usr/bin/env python3
"""
Script de résumé quotidien - Envoyé chaque matin sur Telegram
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.telegram_bot import TelegramNotifier
from src.polymarket_client import PolymarketClient
from datetime import datetime, timezone
from web3 import Web3

def get_summary():
    """Génère et envoie le résumé quotidien"""
    
    telegram = TelegramNotifier()
    client = PolymarketClient()
    
    # Get USDC.e balance
    w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
    usdc_e = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
    eoa = '0xd6d6bda70E983432d9702a1AA31E47Fb80376C52'
    
    balance_abi = [{'inputs': [{'name': 'account', 'type': 'address'}], 'name': 'balanceOf', 'outputs': [{'name': '', 'type': 'uint256'}], 'stateMutability': 'view', 'type': 'function'}]
    usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(usdc_e), abi=balance_abi)
    usdc_balance = usdc_contract.functions.balanceOf(Web3.to_checksum_address(eoa)).call() / 10**6
    
    # Get trades
    trades = []
    orders = []
    try:
        trades = client.client.get_trades() or []
        orders = client.client.get_orders() or []
    except:
        pass
    
    # Count stats
    total_trades = len(trades)
    open_orders = len([o for o in orders if o.get('status') == 'LIVE'])
    
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    msg = f"""
☀️ <b>RÉSUMÉ DU MATIN</b>

📅 {now}

💰 <b>Solde USDC.e:</b> ${usdc_balance:.2f}

📊 <b>Activité:</b>
• Trades exécutés: {total_trades}
• Ordres ouverts: {open_orders}

🤖 <b>Bot Status:</b> Actif 24/7
• BTC/ETH/XRP
• 5 shares/trade
• Mean Reversion

Bonne journée! ☕
"""
    
    result = telegram.send_message(msg)
    print(f"Summary sent: {'OK' if result else 'FAILED'}")
    return result

if __name__ == "__main__":
    get_summary()
