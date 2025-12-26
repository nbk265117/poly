#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Manager
Charge et gère les configurations depuis config.yaml et .env
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

class Config:
    """Gestionnaire de configuration centralisé"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.project_root = Path(__file__).parent.parent
        self.config_path = self.project_root / config_path
        
        # Charger les variables d'environnement
        load_dotenv(self.project_root / ".env")
        
        # Charger le fichier YAML
        self.config = self._load_yaml()
        
    def _load_yaml(self) -> Dict[str, Any]:
        """Charge le fichier de configuration YAML"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML config: {e}")
    
    # ========== Symbols ==========
    @property
    def symbols(self) -> List[str]:
        """Liste des paires à trader"""
        return self.config.get('symbols', ['BTC/USDT', 'ETH/USDT', 'XRP/USDT'])
    
    # ========== Timeframes ==========
    @property
    def primary_timeframe(self) -> str:
        """Timeframe principal (15m)"""
        return self.config.get('timeframes', {}).get('primary', '15m')
    
    @property
    def ftfc_timeframes(self) -> List[str]:
        """Timeframes pour FTFC"""
        return self.config.get('timeframes', {}).get('ftfc', ['15m', '1h', '4h'])
    
    # ========== Strategy ==========
    @property
    def price_action_config(self) -> Dict[str, Any]:
        """Configuration Price Action"""
        return self.config.get('strategy', {}).get('indicators', {}).get('price_action', {})
    
    @property
    def ftfc_config(self) -> Dict[str, Any]:
        """Configuration FTFC"""
        return self.config.get('strategy', {}).get('indicators', {}).get('ftfc', {})
    
    @property
    def volume_config(self) -> Dict[str, Any]:
        """Configuration Volume"""
        return self.config.get('strategy', {}).get('indicators', {}).get('volume', {})
    
    @property
    def entry_offset_seconds(self) -> int:
        """Offset d'entrée en secondes avant clôture"""
        return self.config.get('strategy', {}).get('execution', {}).get('entry_offset_seconds', 8)
    
    @property
    def min_trades_per_day(self) -> int:
        """Nombre minimum de trades par jour"""
        return self.config.get('strategy', {}).get('execution', {}).get('min_trades_per_day', 40)
    
    @property
    def max_trades_per_day(self) -> int:
        """Nombre maximum de trades par jour"""
        return self.config.get('strategy', {}).get('execution', {}).get('max_trades_per_day', 60)
    
    # ========== Risk Management ==========
    @property
    def max_positions(self) -> int:
        """Nombre maximum de positions simultanées"""
        return self.config.get('strategy', {}).get('risk', {}).get('max_positions', 3)
    
    @property
    def position_size_usd(self) -> float:
        """Taille de position par défaut (USD)"""
        return float(self.config.get('strategy', {}).get('risk', {}).get('position_size_usd', 100))
    
    @property
    def stop_loss_percent(self) -> float:
        """Stop loss en pourcentage"""
        return float(self.config.get('strategy', {}).get('risk', {}).get('stop_loss_percent', 2.0))
    
    @property
    def take_profit_percent(self) -> float:
        """Take profit en pourcentage"""
        return float(self.config.get('strategy', {}).get('risk', {}).get('take_profit_percent', 3.0))
    
    # ========== Backtest ==========
    @property
    def backtest_start_date(self) -> str:
        """Date de début du backtest"""
        return self.config.get('backtest', {}).get('start_date', '2023-01-01')
    
    @property
    def backtest_end_date(self) -> str:
        """Date de fin du backtest"""
        return self.config.get('backtest', {}).get('end_date', '2024-12-31')
    
    @property
    def initial_capital(self) -> float:
        """Capital initial pour backtest"""
        return float(self.config.get('backtest', {}).get('initial_capital', 10000))
    
    @property
    def commission(self) -> float:
        """Commission par trade"""
        return float(self.config.get('backtest', {}).get('commission', 0.001))
    
    @property
    def slippage(self) -> float:
        """Slippage"""
        return float(self.config.get('backtest', {}).get('slippage', 0.0005))
    
    # ========== Environment Variables ==========
    @property
    def binance_api_key(self) -> str:
        """Clé API Binance"""
        return os.getenv('BINANCE_API_KEY', '')
    
    @property
    def binance_api_secret(self) -> str:
        """Secret API Binance"""
        return os.getenv('BINANCE_API_SECRET', '')
    
    @property
    def polymarket_api_key(self) -> str:
        """Clé API Polymarket"""
        return os.getenv('POLYMARKET_API_KEY', '')
    
    @property
    def polymarket_private_key(self) -> str:
        """Clé privée Polymarket"""
        return os.getenv('POLYMARKET_PRIVATE_KEY', '')
    
    @property
    def telegram_bot_token(self) -> str:
        """Token du bot Telegram"""
        return os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    @property
    def telegram_chat_id(self) -> str:
        """ID du chat Telegram"""
        return os.getenv('TELEGRAM_CHAT_ID', '')
    
    @property
    def telegram_enabled(self) -> bool:
        """Telegram activé"""
        return self.config.get('telegram', {}).get('enabled', True)
    
    @property
    def environment(self) -> str:
        """Environment (development/production)"""
        return os.getenv('ENVIRONMENT', 'development')
    
    @property
    def log_level(self) -> str:
        """Niveau de log"""
        return os.getenv('LOG_LEVEL', 'INFO')
    
    # ========== Directories ==========
    @property
    def data_dir(self) -> Path:
        """Répertoire des données"""
        return self.project_root / "data"
    
    @property
    def cache_dir(self) -> Path:
        """Répertoire du cache"""
        cache_path = self.project_root / self.config.get('data', {}).get('cache_dir', 'data/cache')
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path
    
    @property
    def historical_dir(self) -> Path:
        """Répertoire des données historiques"""
        hist_path = self.project_root / self.config.get('data', {}).get('historical_dir', 'data/historical')
        hist_path.mkdir(parents=True, exist_ok=True)
        return hist_path
    
    @property
    def logs_dir(self) -> Path:
        """Répertoire des logs"""
        logs_path = self.project_root / "logs"
        logs_path.mkdir(parents=True, exist_ok=True)
        return logs_path
    
    def get(self, key: str, default: Any = None) -> Any:
        """Récupère une valeur de configuration"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value


# Instance globale
_config = None

def get_config() -> Config:
    """Retourne l'instance de configuration (singleton)"""
    global _config
    if _config is None:
        _config = Config()
    return _config


if __name__ == "__main__":
    # Test de la configuration
    config = get_config()
    print("=== Configuration Test ===")
    print(f"Symbols: {config.symbols}")
    print(f"Primary Timeframe: {config.primary_timeframe}")
    print(f"FTFC Timeframes: {config.ftfc_timeframes}")
    print(f"Position Size: ${config.position_size_usd}")
    print(f"Telegram Enabled: {config.telegram_enabled}")
    print(f"Environment: {config.environment}")

