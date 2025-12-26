#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtesting Engine - MODE POLYMARKET UP/DOWN
Système de backtesting pour prédictions binaires 15 minutes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from pathlib import Path

from src.config import get_config
from src.data_manager import DataManager
from src.strategy import TradingStrategy, Trade
from src.indicators import IndicatorPipeline

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Moteur de backtesting MODE POLYMARKET
    Simule des prédictions UP/DOWN sur 15 minutes
    """
    
    def __init__(
        self,
        initial_capital: float = 10000,
        commission: float = 0.001,
        slippage: float = 0.0005,
        config=None
    ):
        self.config = config or get_config()
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        
        # Mode Polymarket
        self.polymarket_mode = self.config.get('backtest.polymarket_mode', True)
        self.polymarket_payout = self.config.get('backtest.polymarket_payout', 1.9)
        
        self.capital = initial_capital
        self.equity_curve = []
        
        self.data_manager = DataManager(config)
        self.indicators = IndicatorPipeline(config)
        
        self.trades: List[Trade] = []
        self.open_trades: List[Trade] = []
        
        logger.info(f"💰 Backtest Engine initialisé")
        logger.info(f"   Capital initial: ${self.initial_capital:,.2f}")
        if self.polymarket_mode:
            logger.info(f"   Mode: POLYMARKET UP/DOWN (payout {self.polymarket_payout}x)")
        else:
            logger.info(f"   Mode: Trading classique (TP/SL)")
    
    def apply_costs(self, price: float, direction: str) -> float:
        """Applique les coûts (commission + slippage)"""
        cost = self.commission + self.slippage
        
        if direction == 'BUY':
            return price * (1 + cost)
        else:
            return price * (1 - cost)
    
    def run_backtest(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Exécute le backtest MODE POLYMARKET UP/DOWN
        
        Args:
            symbols: Liste des paires à trader
            start_date: Date de début (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)
            
        Returns:
            Dict avec résultats du backtest
        """
        logger.info("=" * 80)
        logger.info("🚀 DÉMARRAGE DU BACKTEST - MODE POLYMARKET UP/DOWN")
        logger.info("=" * 80)
        logger.info(f"Symboles: {', '.join(symbols)}")
        logger.info(f"Période: {start_date} à {end_date}")
        logger.info(f"Capital initial: ${self.initial_capital:,.2f}")
        logger.info(f"Payout: {self.polymarket_payout}x (90% gain si win)")
        logger.info(f"Commission: {self.commission * 100:.2f}%")
        logger.info("=" * 80)
        
        # Charger les données pour chaque symbole
        data_dict = {}
        multi_tf_data = {}
        
        for symbol in symbols:
            logger.info(f"Chargement des données pour {symbol}...")
            
            # Données multi-timeframe
            multi_tf_data[symbol] = self.data_manager.prepare_multi_timeframe_data(
                symbol,
                self.config.ftfc_timeframes
            )
            
            # Données principales (15m)
            df = multi_tf_data[symbol][self.config.primary_timeframe].copy()
            
            # Filtrer sur la période (UTC-aware)
            df = df[
                (df['timestamp'] >= pd.to_datetime(start_date, utc=True)) &
                (df['timestamp'] <= pd.to_datetime(end_date, utc=True))
            ]
            
            if len(df) < 100:
                logger.warning(f"Pas assez de données pour {symbol}")
                continue
            
            # Calculer les indicateurs
            df = self.indicators.calculate_all(df, multi_tf_data[symbol])
            
            data_dict[symbol] = df
            
            logger.info(f"  ✅ {len(df)} bougies chargées")
        
        if not data_dict:
            logger.error("Aucune donnée disponible pour le backtest")
            return {}
        
        # Simulation
        logger.info("\n" + "=" * 80)
        logger.info("📊 SIMULATION EN COURS (MODE POLYMARKET)...")
        logger.info("=" * 80)
        
        # Trouver la période commune
        all_timestamps = []
        for df in data_dict.values():
            all_timestamps.extend(df['timestamp'].tolist())
        
        timestamps = sorted(set(all_timestamps))
        
        logger.info(f"Nombre de bougies à traiter: {len(timestamps)}")
        
        # Itérer sur chaque bougie
        for i, ts in enumerate(timestamps):
            
            # Afficher la progression
            if i % 1000 == 0 and i > 0:
                progress = (i / len(timestamps)) * 100
                logger.info(f"Progression: {progress:.1f}% | Trades: {len(self.trades)} | Capital: ${self.capital:,.2f}")
            
            # MODE POLYMARKET : Vérifier les trades ouverts (15 minutes écoulées)
            if self.polymarket_mode:
                for trade in self.open_trades[:]:
                    # Trouver le prix actuel pour ce symbole
                    symbol_df = data_dict.get(trade.symbol)
                    if symbol_df is None:
                        continue
                    
                    # Vérifier si 15 minutes sont écoulées
                    time_elapsed = (ts - trade.entry_time).total_seconds() / 60
                    
                    if time_elapsed >= 15:  # 15 minutes écoulées
                        # Trouver le close de la bougie actuelle
                        idx = symbol_df['timestamp'].searchsorted(ts, side='right') - 1
                        if idx < 0 or idx >= len(symbol_df):
                            continue
                        
                        current_close = symbol_df.iloc[idx]['close']
                        
                        # Déterminer WIN/LOSS
                        if trade.direction == 'BUY':  # Prédiction UP
                            if current_close > trade.entry_price:
                                # WIN
                                self._close_polymarket_trade(trade, current_close, ts, 'polymarket_win')
                            else:
                                # LOSS
                                self._close_polymarket_trade(trade, current_close, ts, 'polymarket_loss')
                        
                        elif trade.direction == 'SELL':  # Prédiction DOWN
                            if current_close < trade.entry_price:
                                # WIN
                                self._close_polymarket_trade(trade, current_close, ts, 'polymarket_win')
                            else:
                                # LOSS
                                self._close_polymarket_trade(trade, current_close, ts, 'polymarket_loss')
            
            # Analyser chaque symbole pour nouveaux signaux
            for symbol, df in data_dict.items():
                
                # Trouver l'index correspondant au timestamp
                idx = df['timestamp'].searchsorted(ts, side='right') - 1
                if idx < 0 or idx >= len(df):
                    continue
                
                row = df.iloc[idx]
                
                # Générer le signal
                signal = self.indicators.generate_signal(row)
                
                if signal:
                    # Vérifier si on peut ouvrir une nouvelle position
                    if len(self.open_trades) < self.config.max_positions:
                        # Ouvrir un trade
                        entry_price = self.apply_costs(row['close'], signal)
                        
                        trade = self._open_polymarket_trade(
                            symbol=symbol,
                            direction=signal,
                            entry_price=entry_price,
                            entry_time=ts
                        )
            
            # Enregistrer l'equity
            current_equity = self.capital
            for trade in self.open_trades:
                # En cours (capital immobilisé)
                symbol_df = data_dict.get(trade.symbol)
                if symbol_df is not None:
                    idx = symbol_df['timestamp'].searchsorted(ts, side='right') - 1
                    if 0 <= idx < len(symbol_df):
                        # Capital investi
                        current_equity += (trade.position_size * trade.entry_price)
            
            self.equity_curve.append({
                'timestamp': ts,
                'equity': current_equity,
                'open_trades': len(self.open_trades)
            })
        
        # Fermer toutes les positions ouvertes
        logger.info("\nFermeture des positions ouvertes...")
        for trade in self.open_trades[:]:
            symbol_df = data_dict.get(trade.symbol)
            if symbol_df is not None:
                exit_price = symbol_df.iloc[-1]['close']
                self._close_polymarket_trade(trade, exit_price, timestamps[-1], 'backtest_end')
        
        # Calculer les statistiques
        results = self._calculate_statistics()
        
        # Afficher les résultats
        self._print_results(results)
        
        return results
    
    def _open_polymarket_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_time: datetime
    ) -> Optional[Trade]:
        """Ouvre une prédiction Polymarket UP/DOWN"""
        
        # Calculer taille de position (montant misé)
        # Utiliser position fixe ou capital restant (le plus petit)
        bet_amount = min(
            self.config.position_size_usd,
            self.capital * 0.95  # Max 95% du capital restant
        )
        
        # Minimum $5 pour continuer à trader
        if bet_amount < 5 or self.capital < 5:
            return None
        
        position_size = bet_amount / entry_price
        
        # Déduire le montant misé du capital
        self.capital -= bet_amount
        
        # Pas de SL/TP en mode Polymarket
        trade = Trade(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size=position_size,
            stop_loss=0,  # N/A
            take_profit=0  # N/A
        )
        
        self.open_trades.append(trade)
        self.trades.append(trade)
        
        return trade
    
    def _close_polymarket_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        reason: str
    ):
        """
        Ferme une prédiction Polymarket
        
        WIN: récupère mise + gain (payout - 1)
        LOSS: perd la mise
        """
        trade.close(exit_price, exit_time, reason)
        
        bet_amount = trade.position_size * trade.entry_price
        
        if reason == 'polymarket_win':
            # WIN: récupère mise + gain
            payout = bet_amount * self.polymarket_payout
            trade.pnl = payout - bet_amount  # Gain net
            self.capital += payout
        elif reason == 'polymarket_loss':
            # LOSS: perd la mise
            trade.pnl = -bet_amount
            # Capital déjà déduit à l'ouverture
        else:
            # Fin du backtest : neutral (récupère la mise)
            trade.pnl = 0
            self.capital += bet_amount
        
        # Déduire la commission
        commission = bet_amount * self.commission
        self.capital -= commission
        
        if trade in self.open_trades:
            self.open_trades.remove(trade)
    
    def _calculate_commission(self, trade: Trade) -> float:
        """Calcule la commission pour un trade"""
        bet_amount = trade.entry_price * trade.position_size
        return bet_amount * self.commission
    
    def _calculate_statistics(self) -> Dict:
        """Calcule les statistiques du backtest"""
        
        if not self.trades:
            return {}
        
        trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
        equity_df = pd.DataFrame(self.equity_curve)
        
        # Statistiques des trades
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        avg_pnl = trades_df['pnl'].mean()
        
        profit_factor = abs(
            trades_df[trades_df['pnl'] > 0]['pnl'].sum() / 
            trades_df[trades_df['pnl'] < 0]['pnl'].sum()
        ) if losing_trades > 0 else 0
        
        # Retour total
        final_capital = self.capital
        total_return = ((final_capital / self.initial_capital) - 1) * 100
        
        # Drawdown
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # Sharpe Ratio (annualisé)
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe = equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252) if len(equity_df) > 1 else 0
        
        # Trades par jour
        if len(trades_df) > 0:
            duration = (trades_df['entry_time'].max() - trades_df['entry_time'].min()).days
            trades_per_day = total_trades / duration if duration > 0 else 0
        else:
            trades_per_day = 0
        
        # Statistiques BUY vs SELL
        buy_trades = trades_df[trades_df['direction'] == 'BUY']
        sell_trades = trades_df[trades_df['direction'] == 'SELL']
        
        buy_win_rate = (len(buy_trades[buy_trades['pnl'] > 0]) / len(buy_trades) * 100) if len(buy_trades) > 0 else 0
        sell_win_rate = (len(sell_trades[sell_trades['pnl'] > 0]) / len(sell_trades) * 100) if len(sell_trades) > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_pnl': avg_pnl,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'trades_per_day': trades_per_day,
            'buy_win_rate': buy_win_rate,
            'sell_win_rate': sell_win_rate,
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'equity_curve': equity_df,
            'trades': trades_df
        }
    
    def _print_results(self, results: Dict):
        """Affiche les résultats du backtest"""
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 RÉSULTATS DU BACKTEST - MODE POLYMARKET UP/DOWN")
        logger.info("=" * 80)
        
        logger.info(f"\n💰 PERFORMANCE")
        logger.info(f"  Capital initial:      ${results['initial_capital']:,.2f}")
        logger.info(f"  Capital final:        ${results['final_capital']:,.2f}")
        logger.info(f"  PnL total:            ${results['total_pnl']:,.2f}")
        logger.info(f"  Retour total:         {results['total_return']:.2f}%")
        
        logger.info(f"\n📈 STATISTIQUES DES TRADES")
        logger.info(f"  Nombre total:         {results['total_trades']}")
        logger.info(f"  Gagnants:             {results['winning_trades']}")
        logger.info(f"  Perdants:             {results['losing_trades']}")
        logger.info(f"  Win rate:             {results['win_rate']:.2f}%")
        logger.info(f"  Trades par jour:      {results['trades_per_day']:.1f}")
        
        logger.info(f"\n🎯 BUY vs SELL")
        logger.info(f"  BUY trades:           {results['buy_trades']} (Win: {results['buy_win_rate']:.1f}%)")
        logger.info(f"  SELL trades:          {results['sell_trades']} (Win: {results['sell_win_rate']:.1f}%)")
        
        logger.info(f"\n💵 GAINS/PERTES")
        logger.info(f"  Gain moyen:           ${results['avg_win']:.2f}")
        logger.info(f"  Perte moyenne:        ${results['avg_loss']:.2f}")
        logger.info(f"  PnL moyen:            ${results['avg_pnl']:.2f}")
        logger.info(f"  Profit Factor:        {results['profit_factor']:.2f}")
        
        logger.info(f"\n📉 RISQUE")
        logger.info(f"  Drawdown max:         {results['max_drawdown']:.2f}%")
        logger.info(f"  Sharpe Ratio:         {results['sharpe_ratio']:.2f}")
        
        logger.info("\n" + "=" * 80)
        
        # Verdict POLYMARKET
        if results['win_rate'] >= 55 and results['total_return'] > 0 and results['trades_per_day'] >= 20:
            logger.info("✅ OBJECTIF ATTEINT - Stratégie prête pour Polymarket!")
        elif results['win_rate'] >= 50 and results['total_return'] > 0:
            logger.info("⚠️  PRESQUE - Amélioration possible")
        else:
            logger.info("❌ OBJECTIF NON ATTEINT - Stratégie à améliorer")
        
        logger.info("=" * 80)
    
    def save_results(self, output_dir: str = "backtest_results"):
        """Sauvegarde les résultats"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sauvegarder les trades
        if self.trades:
            trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
            trades_file = output_path / f"trades_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False)
            logger.info(f"Trades sauvegardés: {trades_file}")
        
        # Sauvegarder l'equity curve
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_file = output_path / f"equity_{timestamp}.csv"
            equity_df.to_csv(equity_file, index=False)
            logger.info(f"Equity curve sauvegardée: {equity_file}")


if __name__ == "__main__":
    # Test du backtest
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    config = get_config()
    
    backtest = BacktestEngine(
        initial_capital=config.initial_capital,
        commission=config.commission,
        slippage=config.slippage
    )
    
    results = backtest.run_backtest(
        symbols=['BTC/USDT'],
        start_date='2024-01-01',
        end_date='2024-12-31'
    )
    
    backtest.save_results()
