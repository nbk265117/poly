#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket Client
Interface pour trader sur Polymarket
Documentation: https://docs.polymarket.com/developers/CLOB/authentication
"""

import logging
import os
from typing import Dict, Optional
from datetime import datetime

# Note: Installation requise: pip install py-clob-client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType
    CLOB_AVAILABLE = True
except ImportError:
    ClobClient = None
    CLOB_AVAILABLE = False

try:
    from src.config import get_config
except ImportError:
    from config import get_config

logger = logging.getLogger(__name__)

# Polymarket CLOB API endpoint
POLYMARKET_HOST = "https://clob.polymarket.com"
POLYGON_CHAIN_ID = 137


class PolymarketClient:
    """
    Client pour interagir avec Polymarket CLOB API

    Pour le trading live, vous avez besoin de:
    1. Une cle privee de votre wallet Polygon (MetaMask)
    2. Des USDC sur votre compte Polymarket

    Configuration dans .env:
    POLYMARKET_PRIVATE_KEY=0x... (votre cle privee)
    ENVIRONMENT=production (pour trading reel)
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.client = None
        self.is_live = self.config.environment == 'production'
        self.api_creds = None

        if CLOB_AVAILABLE:
            self._initialize_client()
        else:
            logger.warning("py-clob-client not installed. Install with: pip install py-clob-client")
            logger.warning("Running in SIMULATION mode")

    def _initialize_client(self):
        """Initialise le client Polymarket"""
        private_key = self.config.polymarket_private_key

        # Mode simulation si pas de cle privee ou environment != production
        if not self.is_live or not private_key:
            logger.info("Polymarket client initialized (SIMULATION mode)")
            self.client = None
            return

        try:
            # Initialisation du client avec la cle privee
            # signature_type=0 pour wallet MetaMask/EOA standard
            # signature_type=1 pour wallet email/Magic (avec funder)
            self.client = ClobClient(
                host=POLYMARKET_HOST,
                key=private_key,
                chain_id=POLYGON_CHAIN_ID,
                signature_type=0  # EOA wallet (MetaMask)
            )

            # Generer/recuperer les credentials API
            self.api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(self.api_creds)

            logger.info("Polymarket client initialized (PRODUCTION mode)")
            logger.info(f"API Key: {self.api_creds.api_key[:10]}...")

        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            logger.warning("Falling back to SIMULATION mode")
            self.client = None
    
    def get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        Récupère les informations d'un marché
        
        Args:
            symbol: BTC, ETH, XRP
            
        Returns:
            Dict avec infos du marché ou None
        """
        if not self.client:
            # Mode simulation
            return {
                'symbol': symbol,
                'market_id': f'sim_{symbol}',
                'yes_price': 0.50,
                'no_price': 0.50,
                'volume': 1000000,
                'liquidity': 500000
            }
        
        try:
            # Rechercher le marché correspondant au symbole
            # Note: Adapter selon l'API Polymarket réelle
            markets = self.client.get_markets()
            
            # Filtrer pour trouver le marché crypto correspondant
            for market in markets:
                if symbol.upper() in market.get('question', '').upper():
                    return market
            
            logger.warning(f"Market not found for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching market info for {symbol}: {e}")
            return None
    
    def place_order(
        self,
        symbol: str,
        direction: str,  # BUY or SELL
        outcome: str,    # UP or DOWN
        amount: float,
        price: float = None
    ) -> Optional[Dict]:
        """
        Place un ordre sur Polymarket
        
        Args:
            symbol: BTC, ETH, XRP
            direction: BUY (prendre position) ou SELL (fermer position)
            outcome: UP (Yes) ou DOWN (No)
            amount: Montant en USD
            price: Prix limite (optionnel, sinon market order)
            
        Returns:
            Dict avec détails de l'ordre ou None
        """
        logger.info(
            f"📤 POLYMARKET ORDER | {symbol} | {direction} {outcome} | "
            f"Amount: ${amount:.2f} | Price: {price or 'MARKET'}"
        )
        
        if not self.client or not self.is_live:
            # Mode simulation
            simulated_order = {
                'order_id': f'sim_{datetime.now().timestamp()}',
                'symbol': symbol,
                'direction': direction,
                'outcome': outcome,
                'amount': amount,
                'price': price or 0.50,
                'status': 'filled',
                'timestamp': datetime.now(),
                'simulation': True
            }
            logger.info(f"✅ SIMULATED ORDER: {simulated_order['order_id']}")
            return simulated_order
        
        try:
            # Récupérer les infos du marché
            market = self.get_market_info(symbol)
            if not market:
                logger.error(f"Cannot place order: market not found for {symbol}")
                return None
            
            market_id = market['market_id']
            
            # Déterminer le côté de l'ordre
            # BUY UP = acheter YES
            # BUY DOWN = acheter NO
            # SELL UP = vendre YES
            # SELL DOWN = vendre NO
            
            if direction == 'BUY':
                side = 'BUY'
                token_id = 'YES' if outcome == 'UP' else 'NO'
            else:  # SELL
                side = 'SELL'
                token_id = 'YES' if outcome == 'UP' else 'NO'
            
            # Créer l'ordre
            order_args = OrderArgs(
                market=market_id,
                price=price or market.get('yes_price' if outcome == 'UP' else 'no_price', 0.50),
                size=amount,
                side=side,
                token_id=token_id
            )
            
            # Placer l'ordre
            order = self.client.create_order(order_args)
            
            logger.info(f"✅ ORDER PLACED: {order.get('order_id')}")
            
            return {
                'order_id': order.get('order_id'),
                'symbol': symbol,
                'direction': direction,
                'outcome': outcome,
                'amount': amount,
                'price': order.get('price'),
                'status': order.get('status'),
                'timestamp': datetime.now(),
                'simulation': False
            }
            
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre"""
        if not self.client or not self.is_live:
            logger.info(f"SIMULATED: Cancel order {order_id}")
            return True
        
        try:
            self.client.cancel_order(order_id)
            logger.info(f"✅ ORDER CANCELLED: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_open_orders(self) -> list:
        """Récupère les ordres ouverts"""
        if not self.client or not self.is_live:
            return []
        
        try:
            return self.client.get_orders(status='open')
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []
    
    def get_positions(self) -> list:
        """Récupère les positions ouvertes"""
        if not self.client or not self.is_live:
            return []
        
        try:
            return self.client.get_positions()
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_balance(self) -> float:
        """Récupère le solde du compte"""
        if not self.client or not self.is_live:
            return 10000.0  # Solde simulé
        
        try:
            balance = self.client.get_balance()
            return float(balance.get('available', 0))
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0


class PolymarketTradeExecutor:
    """
    Exécuteur de trades pour Polymarket
    Convertit les signaux de trading en ordres Polymarket
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.client = PolymarketClient(config)
    
    def execute_signal(
        self,
        symbol: str,
        signal: str,
        current_price: float
    ) -> Optional[Dict]:
        """
        Exécute un signal de trading
        
        Args:
            symbol: BTC, ETH, XRP
            signal: BUY ou SELL
            current_price: Prix actuel
            
        Returns:
            Détails de l'ordre ou None
        """
        # Extraire le symbole de base (BTC de BTC/USDT)
        base_symbol = symbol.split('/')[0]
        
        # Déterminer l'outcome (UP ou DOWN)
        # BUY signal = on pense que ça va monter = UP
        # SELL signal = on pense que ça va descendre = DOWN
        outcome = 'UP' if signal == 'BUY' else 'DOWN'
        
        # Montant de la position
        amount = self.config.position_size_usd
        
        # Placer l'ordre
        order = self.client.place_order(
            symbol=base_symbol,
            direction='BUY',  # On achète toujours (soit YES soit NO)
            outcome=outcome,
            amount=amount,
            price=None  # Market order
        )
        
        return order
    
    def close_position(
        self,
        symbol: str,
        outcome: str,
        amount: float
    ) -> Optional[Dict]:
        """
        Ferme une position
        
        Args:
            symbol: BTC, ETH, XRP
            outcome: UP ou DOWN
            amount: Montant
            
        Returns:
            Détails de l'ordre ou None
        """
        base_symbol = symbol.split('/')[0]
        
        # Vendre la position
        order = self.client.place_order(
            symbol=base_symbol,
            direction='SELL',
            outcome=outcome,
            amount=amount,
            price=None
        )
        
        return order


if __name__ == "__main__":
    # Test du client Polymarket
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    client = PolymarketClient()
    
    # Test market info
    market = client.get_market_info('BTC')
    print(f"\nMarket info: {market}")
    
    # Test order (simulation)
    order = client.place_order(
        symbol='BTC',
        direction='BUY',
        outcome='UP',
        amount=100
    )
    print(f"\nOrder: {order}")
    
    # Test executor
    executor = PolymarketTradeExecutor()
    result = executor.execute_signal('BTC/USDT', 'BUY', 50000)
    print(f"\nExecution result: {result}")

