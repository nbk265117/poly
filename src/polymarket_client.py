#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket Client
Interface pour trader sur Polymarket
Documentation: https://docs.polymarket.com/developers/CLOB/authentication
"""

import json
import logging
import os
import requests
import time
from typing import Dict, Optional, List
from datetime import datetime, timezone
from eth_account import Account
from Crypto.Hash import keccak

# Note: Installation requise: pip install py-clob-client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, OrderType, MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY, SELL
    CLOB_AVAILABLE = True
except ImportError:
    ClobClient = None
    CLOB_AVAILABLE = False
    BUY = "BUY"
    SELL = "SELL"

try:
    from src.config import get_config
except ImportError:
    from config import get_config

logger = logging.getLogger(__name__)

# Polymarket API endpoints
POLYMARKET_HOST = "https://clob.polymarket.com"
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
POLYGON_CHAIN_ID = 137

# Polymarket proxy factory contracts on Polygon
PROXY_FACTORY = '0xaB45c5A4B0c941a2F231C04C3f49182e1A254052'
PROXY_IMPLEMENTATION = '0x44e999d5c2F66Ef0861317f9A4805AC2e90aEB4f'


def _keccak256(data: bytes) -> bytes:
    """Calcule le hash keccak256"""
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


def derive_proxy_address(eoa_address: str) -> str:
    """
    Dérive l'adresse proxy Polymarket à partir de l'adresse EOA
    Utilise CREATE2 avec le proxy factory de Polymarket

    Args:
        eoa_address: Adresse EOA (ex: 0xd6d6bda...)

    Returns:
        Adresse proxy checksumée
    """
    # Salt = keccak256(eoa_address padded to 32 bytes)
    eoa_bytes = bytes.fromhex(eoa_address[2:])
    salt = _keccak256(eoa_bytes.rjust(32, b'\x00'))

    # Init code = EIP-1167 minimal proxy bytecode
    init_code = bytes.fromhex(
        '3d602d80600a3d3981f3363d3d373d3d3d363d73' +
        PROXY_IMPLEMENTATION[2:].lower() +
        '5af43d82803e903d91602b57fd5bf3'
    )
    init_code_hash = _keccak256(init_code)

    # CREATE2: keccak256(0xff ++ factory ++ salt ++ initCodeHash)
    create2_input = (
        bytes.fromhex('ff') +
        bytes.fromhex(PROXY_FACTORY[2:]) +
        salt +
        init_code_hash
    )
    proxy_hash = _keccak256(create2_input)
    proxy_address = '0x' + proxy_hash.hex()[-40:]

    # Checksum EIP-55
    addr_lower = proxy_address.lower()[2:]
    hash_of_addr = _keccak256(addr_lower.encode()).hex()
    checksummed = '0x'
    for i, c in enumerate(addr_lower):
        if c in '0123456789':
            checksummed += c
        elif int(hash_of_addr[i], 16) >= 8:
            checksummed += c.upper()
        else:
            checksummed += c.lower()

    return checksummed


class PolymarketClient:
    """
    Client pour interagir avec Polymarket CLOB API

    Supporte les marchés BTC/ETH Up/Down 15 minutes
    """

    def __init__(self, config=None):
        self.config = config or get_config()
        self.client = None
        self.is_live = self.config.environment == 'production'
        self.api_creds = None
        self.market_cache = {}  # Cache pour les marchés

        if CLOB_AVAILABLE:
            self._initialize_client()
        else:
            logger.warning("py-clob-client not installed. Install with: pip install py-clob-client")
            logger.warning("Running in SIMULATION mode")

    def _initialize_client(self):
        """Initialise le client Polymarket"""
        private_key = self.config.polymarket_private_key

        if not self.is_live or not private_key:
            logger.info("Polymarket client initialized (SIMULATION mode)")
            self.client = None
            return

        try:
            # Obtenir l'adresse EOA pour logging
            account = Account.from_key(private_key)
            eoa_address = account.address

            logger.info(f"EOA Address: {eoa_address}")

            # Signature type 0 = EOA (Externally Owned Account)
            # Les fonds USDC.e sont directement sur l'EOA
            # Necessite d'avoir approuve les contrats Polymarket au prealable
            self.client = ClobClient(
                host=POLYMARKET_HOST,
                key=private_key,
                chain_id=POLYGON_CHAIN_ID,
                signature_type=0  # EOA direct
            )

            self.api_creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(self.api_creds)

            logger.info("Polymarket client initialized (PRODUCTION mode)")
            logger.info(f"API Key: {self.api_creds.api_key[:10]}...")

        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            logger.warning("Falling back to SIMULATION mode")
            self.client = None

    def _get_current_15m_timestamp(self) -> int:
        """Retourne le timestamp du début de la fenêtre 15 minutes actuelle"""
        now = int(time.time())
        return (now // 900) * 900  # Arrondi aux 15 minutes

    def _search_active_market(self, symbol: str) -> Optional[Dict]:
        """
        Recherche le marché Up/Down actif pour un symbole via l'API Gamma

        Args:
            symbol: BTC ou ETH

        Returns:
            Dict avec condition_id, token_id_yes, token_id_no
        """
        try:
            # Construire le slug du marché basé sur le timestamp actuel
            current_ts = self._get_current_15m_timestamp()
            next_ts = current_ts + 900  # Prochaine fenêtre

            # IMPORTANT: 8 sec avant la fin de la bougie, on doit trader sur le PROCHAIN marché
            # Donc on cherche next_ts EN PREMIER
            for ts in [next_ts, current_ts + 1800, current_ts, current_ts - 900]:
                slug = f"{symbol.lower()}-updown-15m-{ts}"
                logger.debug(f"Searching for event: {slug}")

                # Chercher via Gamma API - endpoint /events (pas /markets)
                url = f"{GAMMA_API_HOST}/events?slug={slug}"
                resp = requests.get(url, timeout=10)

                if resp.status_code == 200:
                    data = resp.json()

                    # La réponse peut être une liste ou un objet
                    event = None
                    if isinstance(data, list) and len(data) > 0:
                        event = data[0]
                    elif isinstance(data, dict) and data.get('id'):
                        event = data

                    if event:
                        # Les marchés sont dans l'array 'markets'
                        markets = event.get('markets', [])
                        if markets and len(markets) > 0:
                            market = markets[0]

                            # Extraire les token IDs (peut être string JSON ou list)
                            tokens_raw = market.get('clobTokenIds', [])
                            if isinstance(tokens_raw, str):
                                try:
                                    tokens = json.loads(tokens_raw)
                                except json.JSONDecodeError:
                                    tokens = []
                            else:
                                tokens = tokens_raw

                            if len(tokens) >= 2:
                                logger.info(f"Found event: {slug}")
                                logger.info(f"Token UP: {tokens[0][:20]}...")
                                logger.info(f"Token DOWN: {tokens[1][:20]}...")
                                return {
                                    'condition_id': market.get('conditionId'),
                                    'token_id_yes': tokens[0],  # UP
                                    'token_id_no': tokens[1],   # DOWN
                                    'slug': slug,
                                    'question': event.get('title', ''),
                                    'end_date': event.get('endDate', ''),
                                    'outcomes': market.get('outcomes', ['Up', 'Down']),
                                    'prices': market.get('outcomePrices', [])
                                }

            # Méthode alternative: chercher les events actifs avec ticker
            for asset in [symbol.lower(), symbol.upper()]:
                url = f"{GAMMA_API_HOST}/events?ticker_contains={asset}-updown-15m&active=true&limit=10"
                resp = requests.get(url, timeout=10)

                if resp.status_code == 200:
                    events = resp.json()
                    if isinstance(events, list):
                        for event in events:
                            ticker = event.get('ticker', '').lower()
                            if 'updown-15m' in ticker and asset.lower() in ticker:
                                markets = event.get('markets', [])
                                if markets:
                                    market = markets[0]
                                    tokens_raw = market.get('clobTokenIds', [])
                                    if isinstance(tokens_raw, str):
                                        try:
                                            tokens = json.loads(tokens_raw)
                                        except json.JSONDecodeError:
                                            tokens = []
                                    else:
                                        tokens = tokens_raw
                                    if len(tokens) >= 2:
                                        logger.info(f"Found event via search: {event.get('ticker')}")
                                        return {
                                            'condition_id': market.get('conditionId'),
                                            'token_id_yes': tokens[0],
                                            'token_id_no': tokens[1],
                                            'slug': event.get('ticker'),
                                            'question': event.get('title', ''),
                                            'end_date': event.get('endDate', ''),
                                            'outcomes': market.get('outcomes', ['Up', 'Down']),
                                            'prices': market.get('outcomePrices', [])
                                        }

            logger.warning(f"No active Up/Down market found for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error searching market for {symbol}: {e}", exc_info=True)
            return None

    def get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        Récupère les informations du marché Up/Down actif

        Args:
            symbol: BTC, ETH

        Returns:
            Dict avec infos du marché ou None
        """
        if not self.client:
            # Mode simulation
            return {
                'symbol': symbol,
                'condition_id': f'sim_{symbol}',
                'token_id_yes': f'sim_yes_{symbol}',
                'token_id_no': f'sim_no_{symbol}',
                'yes_price': 0.50,
                'no_price': 0.50
            }

        # Vérifier le cache (valide 5 minutes)
        cache_key = f"{symbol}_market"
        if cache_key in self.market_cache:
            cached = self.market_cache[cache_key]
            if time.time() - cached['timestamp'] < 300:
                return cached['data']

        # Rechercher le marché actif
        market = self._search_active_market(symbol)

        if market:
            # Mettre en cache
            self.market_cache[cache_key] = {
                'data': market,
                'timestamp': time.time()
            }
            return market

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
            symbol: BTC, ETH
            direction: BUY (prendre position) ou SELL (fermer position)
            outcome: UP (Yes) ou DOWN (No)
            amount: Montant en USD
            price: Prix limite (optionnel, 0.50 par défaut)

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
                'order_id': f'sim_{datetime.now(timezone.utc).timestamp()}',
                'symbol': symbol,
                'direction': direction,
                'outcome': outcome,
                'amount': amount,
                'price': price or 0.50,
                'status': 'filled',
                'timestamp': datetime.now(timezone.utc),
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

            # Obtenir le bon token_id selon l'outcome
            if outcome == 'UP':
                token_id = market.get('token_id_yes')
            else:  # DOWN
                token_id = market.get('token_id_no')

            if not token_id:
                logger.error(f"No token_id found for {symbol} {outcome}")
                return None

            logger.info(f"Market found: {market.get('slug', 'unknown')}")
            logger.info(f"Token ID: {token_id[:20]}...")

            # Déterminer le côté de l'ordre
            side = BUY if direction == 'BUY' else SELL

            # Prix par défaut: 0.50 (50 cents)
            order_price = price if price else 0.50

            # Utiliser amount directement comme nombre de shares
            size = amount  # amount = nombre de shares

            # Créer l'ordre limite
            order_args = OrderArgs(
                token_id=token_id,
                price=order_price,
                size=size,
                side=side
            )

            # Créer et poster l'ordre
            signed_order = self.client.create_order(order_args)
            resp = self.client.post_order(signed_order, OrderType.GTC)

            logger.info(f"✅ ORDER PLACED: {resp}")

            return {
                'order_id': resp.get('orderID', resp.get('id', 'unknown')),
                'symbol': symbol,
                'direction': direction,
                'outcome': outcome,
                'amount': amount,
                'price': order_price,
                'size': size,
                'token_id': token_id[:20] + '...',
                'status': 'posted',
                'timestamp': datetime.now(timezone.utc),
                'simulation': False,
                'response': resp
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

