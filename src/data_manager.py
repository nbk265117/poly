#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Manager
Gère le chargement et la préparation des données OHLCV
"""

import ccxt
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging

from src.config import get_config

logger = logging.getLogger(__name__)


class DataManager:
    """Gestionnaire de données OHLCV"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.exchange = self._init_exchange()
        
    def _init_exchange(self) -> ccxt.Exchange:
        """Initialize Binance exchange"""
        return ccxt.binance({
            'enableRateLimit': True,
            'apiKey': self.config.binance_api_key,
            'secret': self.config.binance_api_secret,
            'options': {'defaultType': 'spot'},
        })
    
    def load_historical_data(
        self, 
        symbol: str, 
        timeframe: str = '15m',
        months: int = 24
    ) -> pd.DataFrame:
        """
        Charge les données historiques depuis le fichier CSV
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            timeframe: Timeframe (15m, 1h, 4h)
            months: Nombre de mois à charger
            
        Returns:
            DataFrame avec colonnes: timestamp, open, high, low, close, volume
        """
        # Convertir symbole format
        base, quote = symbol.split('/')
        filename = f"{base}_{quote}_{timeframe}.csv"
        filepath = self.config.historical_dir / filename
        
        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            logger.info(f"Downloading data for {symbol} {timeframe}...")
            self.download_historical_data(symbol, timeframe, months)
        
        try:
            df = pd.read_csv(filepath, parse_dates=['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Filtrer sur la période demandée (UTC-aware pour comparaison)
            cutoff_date = pd.Timestamp.now(tz='UTC') - timedelta(days=months * 30)
            df = df[df['timestamp'] >= cutoff_date]
            
            logger.info(f"Loaded {len(df)} rows for {symbol} {timeframe}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            raise
    
    def download_historical_data(
        self,
        symbol: str,
        timeframe: str = '15m',
        months: int = 24
    ) -> None:
        """
        Télécharge les données historiques depuis Binance
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            timeframe: Timeframe
            months: Nombre de mois
        """
        logger.info(f"Downloading {symbol} {timeframe} for {months} months...")
        
        # Calculer la période (UTC)
        since = self.exchange.parse8601(
            (datetime.now(timezone.utc) - timedelta(days=months * 30)).isoformat()
        )
        
        all_ohlcv = []
        
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol, 
                    timeframe=timeframe,
                    since=since,
                    limit=1000
                )
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1
                
                if len(ohlcv) < 1000:
                    break
                    
            except Exception as e:
                logger.error(f"Error downloading data: {e}")
                break
        
        # Convertir en DataFrame
        df = pd.DataFrame(
            all_ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        
        # Sauvegarder
        base, quote = symbol.split('/')
        filename = f"{base}_{quote}_{timeframe}.csv"
        filepath = self.config.historical_dir / filename
        df.to_csv(filepath, index=False)
        
        logger.info(f"Saved {len(df)} rows to {filepath}")
    
    def resample_timeframe(
        self,
        df: pd.DataFrame,
        target_timeframe: str
    ) -> pd.DataFrame:
        """
        Resample le DataFrame vers un timeframe supérieur
        
        Args:
            df: DataFrame avec timeframe source
            target_timeframe: Timeframe cible (1h, 4h)
            
        Returns:
            DataFrame resamplé
        """
        if df.empty:
            return df
        
        df = df.copy()
        df = df.set_index('timestamp')
        
        # Mapping des timeframes
        tf_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '1h': '1h',
            '4h': '4h',
            '1d': '1D'
        }
        
        rule = tf_map.get(target_timeframe, '1h')
        
        # Resample
        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled.reset_index()
    
    def get_live_data(
        self,
        symbol: str,
        timeframe: str = '15m',
        limit: int = 200
    ) -> pd.DataFrame:
        """
        Récupère les données en temps réel depuis Binance
        
        Args:
            symbol: Paire
            timeframe: Timeframe
            limit: Nombre de bougies
            
        Returns:
            DataFrame avec données récentes
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching live data for {symbol}: {e}")
            return pd.DataFrame()
    
    def prepare_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Prépare les données pour plusieurs timeframes
        
        Args:
            symbol: Paire
            timeframes: Liste des timeframes
            
        Returns:
            Dict {timeframe: DataFrame}
        """
        if timeframes is None:
            timeframes = self.config.ftfc_timeframes
        
        data = {}
        
        # Charger le timeframe le plus bas
        base_tf = min(timeframes, key=lambda x: self._tf_to_minutes(x))
        base_data = self.load_historical_data(symbol, base_tf)
        
        for tf in timeframes:
            if tf == base_tf:
                data[tf] = base_data
            else:
                data[tf] = self.resample_timeframe(base_data, tf)
        
        return data
    
    def _tf_to_minutes(self, timeframe: str) -> int:
        """Convertit un timeframe en minutes"""
        multiplier = {
            'm': 1,
            'h': 60,
            'd': 1440
        }
        
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        return value * multiplier.get(unit, 1)


if __name__ == "__main__":
    # Test du Data Manager
    logging.basicConfig(level=logging.INFO)
    
    dm = DataManager()
    
    # Test chargement données
    df = dm.load_historical_data('BTC/USDT', '15m', months=1)
    print(f"\nLoaded BTC/USDT 15m: {len(df)} rows")
    print(df.head())
    
    # Test multi-timeframe
    data = dm.prepare_multi_timeframe_data('BTC/USDT', ['15m', '1h', '4h'])
    print(f"\nMulti-timeframe data:")
    for tf, df in data.items():
        print(f"  {tf}: {len(df)} rows")

