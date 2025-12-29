#!/usr/bin/env python3
"""
STRATEGIE OPTIMISEE RSI + STOCHASTIC
====================================
Config: RSI(7) 38/58 + Stoch(5) 30/80
Target: $15,000+/mois avec 3 pairs @ $120/trade
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple


class OptimizedStrategy:
    """
    Strategie ultra simple et optimisee pour maximum PnL
    """

    def __init__(self, config: dict = None):
        # Defaults optimises
        self.rsi_period = 7
        self.rsi_oversold = 38
        self.rsi_overbought = 58

        self.stoch_period = 5
        self.stoch_oversold = 30
        self.stoch_overbought = 80

        # Override from config
        if config:
            rsi_config = config.get('strategy', {}).get('rsi', {})
            stoch_config = config.get('strategy', {}).get('stochastic', {})

            self.rsi_period = rsi_config.get('period', self.rsi_period)
            self.rsi_oversold = rsi_config.get('oversold', self.rsi_oversold)
            self.rsi_overbought = rsi_config.get('overbought', self.rsi_overbought)

            self.stoch_period = stoch_config.get('period', self.stoch_period)
            self.stoch_oversold = stoch_config.get('oversold', self.stoch_oversold)
            self.stoch_overbought = stoch_config.get('overbought', self.stoch_overbought)

    def calculate_rsi(self, closes: pd.Series) -> pd.Series:
        """Calcule le RSI"""
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Calcule le Stochastic %K"""
        low_min = low.rolling(self.stoch_period).min()
        high_max = high.rolling(self.stoch_period).max()
        return 100 * (close - low_min) / (high_max - low_min)

    def generate_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Genere un signal basé sur la derniere bougie

        Returns:
            'UP', 'DOWN', ou None
        """
        if len(df) < max(self.rsi_period, self.stoch_period) + 5:
            return None

        # Calculer indicateurs
        rsi = self.calculate_rsi(df['close'])
        stoch = self.calculate_stochastic(df['high'], df['low'], df['close'])

        # Derniere valeur
        current_rsi = rsi.iloc[-1]
        current_stoch = stoch.iloc[-1]

        # Signal UP: RSI < 38 AND Stoch < 30
        if current_rsi < self.rsi_oversold and current_stoch < self.stoch_oversold:
            return 'UP'

        # Signal DOWN: RSI > 58 AND Stoch > 80
        if current_rsi > self.rsi_overbought and current_stoch > self.stoch_overbought:
            return 'DOWN'

        return None

    def get_signal_strength(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """
        Retourne le signal avec sa force (0-1)

        Returns:
            (signal, strength)
        """
        if len(df) < max(self.rsi_period, self.stoch_period) + 5:
            return None, 0

        rsi = self.calculate_rsi(df['close'])
        stoch = self.calculate_stochastic(df['high'], df['low'], df['close'])

        current_rsi = rsi.iloc[-1]
        current_stoch = stoch.iloc[-1]

        # Signal UP
        if current_rsi < self.rsi_oversold and current_stoch < self.stoch_oversold:
            # Force basee sur a quel point on est oversold
            rsi_strength = (self.rsi_oversold - current_rsi) / self.rsi_oversold
            stoch_strength = (self.stoch_oversold - current_stoch) / self.stoch_oversold
            strength = (rsi_strength + stoch_strength) / 2
            return 'UP', min(strength, 1.0)

        # Signal DOWN
        if current_rsi > self.rsi_overbought and current_stoch > self.stoch_overbought:
            rsi_strength = (current_rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
            stoch_strength = (current_stoch - self.stoch_overbought) / (100 - self.stoch_overbought)
            strength = (rsi_strength + stoch_strength) / 2
            return 'DOWN', min(strength, 1.0)

        return None, 0

    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Analyse complete du dataframe

        Returns:
            Dict avec RSI, Stoch, signal, etc.
        """
        if len(df) < max(self.rsi_period, self.stoch_period) + 5:
            return {'error': 'Not enough data'}

        rsi = self.calculate_rsi(df['close'])
        stoch = self.calculate_stochastic(df['high'], df['low'], df['close'])

        current_rsi = rsi.iloc[-1]
        current_stoch = stoch.iloc[-1]
        signal, strength = self.get_signal_strength(df)

        return {
            'rsi': round(current_rsi, 2),
            'stoch': round(current_stoch, 2),
            'signal': signal,
            'strength': round(strength, 2),
            'rsi_oversold': current_rsi < self.rsi_oversold,
            'rsi_overbought': current_rsi > self.rsi_overbought,
            'stoch_oversold': current_stoch < self.stoch_oversold,
            'stoch_overbought': current_stoch > self.stoch_overbought,
        }


# Singleton pour utilisation rapide
_strategy = None


def get_strategy(config: dict = None) -> OptimizedStrategy:
    """Retourne l'instance de la strategie"""
    global _strategy
    if _strategy is None or config is not None:
        _strategy = OptimizedStrategy(config)
    return _strategy


def generate_signal(df: pd.DataFrame, config: dict = None) -> Optional[str]:
    """Helper function pour generer un signal"""
    return get_strategy(config).generate_signal(df)


if __name__ == "__main__":
    # Test
    print("Strategy Optimisee RSI + Stochastic")
    print("=" * 40)

    strategy = OptimizedStrategy()
    print(f"RSI: {strategy.rsi_period} period, {strategy.rsi_oversold}/{strategy.rsi_overbought}")
    print(f"Stoch: {strategy.stoch_period} period, {strategy.stoch_oversold}/{strategy.stoch_overbought}")
    print("\nSignal Rules:")
    print(f"  UP:   RSI < {strategy.rsi_oversold} AND Stoch < {strategy.stoch_oversold}")
    print(f"  DOWN: RSI > {strategy.rsi_overbought} AND Stoch > {strategy.stoch_overbought}")
