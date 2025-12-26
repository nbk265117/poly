#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strategy Engine
Moteur de stratégie de trading
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from src.config import get_config
from src.data_manager import DataManager
from src.indicators import IndicatorPipeline

logger = logging.getLogger(__name__)


class Trade:
    """Représente un trade"""
    
    def __init__(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_time: datetime,
        position_size: float,
        stop_loss: float = None,
        take_profit: float = None
    ):
        self.symbol = symbol
        self.direction = direction  # BUY ou SELL
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        self.exit_price = None
        self.exit_time = None
        self.pnl = 0
        self.pnl_percent = 0
        self.status = 'open'  # open, closed
        self.exit_reason = None  # sl, tp, signal, timeout
    
    def close(
        self,
        exit_price: float,
        exit_time: datetime,
        reason: str = 'signal'
    ):
        """Ferme le trade"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.status = 'closed'
        
        # Calculer PnL
        if self.direction == 'BUY':
            self.pnl = (exit_price - self.entry_price) * self.position_size
            self.pnl_percent = ((exit_price / self.entry_price) - 1) * 100
        else:  # SELL
            self.pnl = (self.entry_price - exit_price) * self.position_size
            self.pnl_percent = ((self.entry_price / exit_price) - 1) * 100
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time,
            'position_size': self.position_size,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'status': self.status,
            'exit_reason': self.exit_reason
        }


class TradingStrategy:
    """
    Stratégie de trading principale
    Combine les 3 indicateurs et génère les signaux
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.data_manager = DataManager(config)
        self.indicators = IndicatorPipeline(config)
        
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
    
    def analyze_market(
        self,
        symbol: str,
        current_time: datetime = None
    ) -> Optional[str]:
        """
        Analyse le marché et retourne un signal
        
        Args:
            symbol: Paire à analyser
            current_time: Temps actuel (pour backtest)
            
        Returns:
            'BUY', 'SELL', ou None
        """
        try:
            # Charger les données multi-timeframe
            tf_data = self.data_manager.prepare_multi_timeframe_data(
                symbol,
                self.config.ftfc_timeframes
            )
            
            # Données principales (15m)
            df_main = tf_data[self.config.primary_timeframe].copy()
            
            if len(df_main) < 100:
                logger.warning(f"Pas assez de données pour {symbol}")
                return None
            
            # Calculer les indicateurs
            df_main = self.indicators.calculate_all(df_main, tf_data)
            
            # Obtenir le signal de la dernière bougie
            if current_time:
                # Mode backtest: trouver la bougie correspondante
                idx = df_main['timestamp'].searchsorted(current_time, side='right') - 1
                if idx < 0 or idx >= len(df_main):
                    return None
                row = df_main.iloc[idx]
            else:
                # Mode live: dernière bougie
                row = df_main.iloc[-1]
            
            # Générer le signal
            signal = self.indicators.generate_signal(row)
            
            if signal:
                logger.info(
                    f"{symbol} | Signal: {signal} | "
                    f"PA: {row['PA_signal']} | "
                    f"FTFC: {row['FTFC_direction']} | "
                    f"VOL: {row['VOL_confirmed']}"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Erreur analyse {symbol}: {e}", exc_info=True)
            return None
    
    def calculate_position_size(
        self,
        price: float,
        capital: float
    ) -> float:
        """
        Calcule la taille de position
        
        Args:
            price: Prix d'entrée
            capital: Capital disponible
            
        Returns:
            Taille de position (en unités)
        """
        # Utiliser la taille configurée
        position_value = min(
            self.config.position_size_usd,
            capital * 0.95  # Max 95% du capital
        )
        
        position_size = position_value / price
        
        return position_size
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str
    ) -> float:
        """Calcule le niveau de stop loss"""
        sl_percent = self.config.stop_loss_percent / 100
        
        if direction == 'BUY':
            return entry_price * (1 - sl_percent)
        else:
            return entry_price * (1 + sl_percent)
    
    def calculate_take_profit(
        self,
        entry_price: float,
        direction: str
    ) -> float:
        """Calcule le niveau de take profit"""
        tp_percent = self.config.take_profit_percent / 100
        
        if direction == 'BUY':
            return entry_price * (1 + tp_percent)
        else:
            return entry_price * (1 - tp_percent)
    
    def open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_time: datetime,
        capital: float
    ) -> Optional[Trade]:
        """
        Ouvre un nouveau trade
        
        Returns:
            Trade object ou None si position pas ouverte
        """
        # Vérifier nombre max de positions
        if len(self.open_trades) >= self.config.max_positions:
            logger.warning("Nombre maximum de positions atteint")
            return None
        
        # Calculer taille de position
        position_size = self.calculate_position_size(entry_price, capital)
        
        # Calculer SL/TP
        stop_loss = self.calculate_stop_loss(entry_price, direction)
        take_profit = self.calculate_take_profit(entry_price, direction)
        
        # Créer le trade
        trade = Trade(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        self.open_trades.append(trade)
        
        logger.info(
            f"✅ TRADE OUVERT | {symbol} | {direction} | "
            f"Prix: {entry_price:.2f} | "
            f"Taille: {position_size:.4f} | "
            f"SL: {stop_loss:.2f} | TP: {take_profit:.2f}"
        )
        
        return trade
    
    def check_stop_loss_take_profit(
        self,
        trade: Trade,
        current_price: float,
        current_time: datetime
    ) -> bool:
        """
        Vérifie si SL ou TP sont touchés
        
        Returns:
            True si trade fermé
        """
        if trade.direction == 'BUY':
            # Stop loss
            if current_price <= trade.stop_loss:
                trade.close(trade.stop_loss, current_time, 'sl')
                logger.info(f"🛑 STOP LOSS | {trade.symbol} | PnL: {trade.pnl:.2f}")
                return True
            
            # Take profit
            if current_price >= trade.take_profit:
                trade.close(trade.take_profit, current_time, 'tp')
                logger.info(f"🎯 TAKE PROFIT | {trade.symbol} | PnL: {trade.pnl:.2f}")
                return True
        
        else:  # SELL
            # Stop loss
            if current_price >= trade.stop_loss:
                trade.close(trade.stop_loss, current_time, 'sl')
                logger.info(f"🛑 STOP LOSS | {trade.symbol} | PnL: {trade.pnl:.2f}")
                return True
            
            # Take profit
            if current_price <= trade.take_profit:
                trade.close(trade.take_profit, current_time, 'tp')
                logger.info(f"🎯 TAKE PROFIT | {trade.symbol} | PnL: {trade.pnl:.2f}")
                return True
        
        return False
    
    def close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        reason: str = 'signal'
    ):
        """Ferme un trade"""
        trade.close(exit_price, exit_time, reason)
        self.open_trades.remove(trade)
        self.closed_trades.append(trade)
        
        logger.info(
            f"🔒 TRADE FERMÉ | {trade.symbol} | "
            f"PnL: {trade.pnl:.2f} ({trade.pnl_percent:.2f}%) | "
            f"Raison: {reason}"
        )
    
    def get_performance_stats(self) -> Dict:
        """Calcule les statistiques de performance"""
        if not self.closed_trades:
            return {}
        
        trades_df = pd.DataFrame([t.to_dict() for t in self.closed_trades])
        
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }


if __name__ == "__main__":
    # Test de la stratégie
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    strategy = TradingStrategy()
    
    # Test analyse
    signal = strategy.analyze_market('BTC/USDT')
    print(f"\nSignal: {signal}")

