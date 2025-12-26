#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest Main
Script principal pour lancer le backtesting
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.backtest import BacktestEngine

# Configuration du logging
def setup_logging(log_level='INFO'):
    """Configure le système de logging"""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)


def plot_equity_curve(equity_df: pd.DataFrame, output_file: str = None):
    """
    Affiche la courbe d'equity
    
    Args:
        equity_df: DataFrame avec timestamp et equity
        output_file: Fichier de sortie (optionnel)
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Backend non-interactif
        
        plt.figure(figsize=(15, 8))
        
        # Courbe d'equity
        plt.subplot(2, 1, 1)
        plt.plot(equity_df['timestamp'], equity_df['equity'], linewidth=2, color='#2E86DE')
        plt.title('Courbe d\'Equity', fontsize=16, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Capital ($)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Drawdown
        plt.subplot(2, 1, 2)
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        plt.fill_between(
            equity_df['timestamp'], 
            equity_df['drawdown'], 
            0, 
            color='#EE5A6F', 
            alpha=0.5
        )
        plt.title('Drawdown (%)', fontsize=16, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Drawdown (%)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        if output_file:
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            logger.info(f"Graphique sauvegardé: {output_file}")
        else:
            plt.show()
        
        plt.close()
        
    except ImportError:
        logger.warning("matplotlib non installé. Graphiques désactivés.")
    except Exception as e:
        logger.error(f"Erreur lors de la création du graphique: {e}")


def analyze_trades(trades_df: pd.DataFrame):
    """
    Analyse détaillée des trades
    
    Args:
        trades_df: DataFrame des trades
    """
    if trades_df.empty:
        logger.warning("Aucun trade à analyser")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 ANALYSE DÉTAILLÉE DES TRADES")
    logger.info("=" * 80)
    
    # Par symbole
    logger.info("\n📈 Performance par symbole:")
    for symbol in trades_df['symbol'].unique():
        symbol_trades = trades_df[trades_df['symbol'] == symbol]
        win_rate = (len(symbol_trades[symbol_trades['pnl'] > 0]) / len(symbol_trades)) * 100
        total_pnl = symbol_trades['pnl'].sum()
        
        logger.info(f"  {symbol:10s} | Trades: {len(symbol_trades):3d} | "
                   f"Win Rate: {win_rate:5.1f}% | PnL: ${total_pnl:+10,.2f}")
    
    # Par direction
    logger.info("\n📊 Performance par direction:")
    for direction in trades_df['direction'].unique():
        dir_trades = trades_df[trades_df['direction'] == direction]
        win_rate = (len(dir_trades[dir_trades['pnl'] > 0]) / len(dir_trades)) * 100
        total_pnl = dir_trades['pnl'].sum()
        
        logger.info(f"  {direction:5s} | Trades: {len(dir_trades):3d} | "
                   f"Win Rate: {win_rate:5.1f}% | PnL: ${total_pnl:+10,.2f}")
    
    # Par raison de sortie
    logger.info("\n🎯 Raisons de sortie:")
    for reason in trades_df['exit_reason'].unique():
        reason_trades = trades_df[trades_df['exit_reason'] == reason]
        win_rate = (len(reason_trades[reason_trades['pnl'] > 0]) / len(reason_trades)) * 100
        total_pnl = reason_trades['pnl'].sum()
        
        logger.info(f"  {reason:15s} | Trades: {len(reason_trades):3d} | "
                   f"Win Rate: {win_rate:5.1f}% | PnL: ${total_pnl:+10,.2f}")
    
    # Meilleurs et pires trades
    logger.info("\n🏆 Top 5 meilleurs trades:")
    best_trades = trades_df.nlargest(5, 'pnl')
    for _, trade in best_trades.iterrows():
        logger.info(f"  {trade['symbol']:10s} | {trade['direction']:5s} | "
                   f"${trade['pnl']:+10,.2f} ({trade['pnl_percent']:+6.2f}%) | "
                   f"{trade['entry_time']}")
    
    logger.info("\n💔 Top 5 pires trades:")
    worst_trades = trades_df.nsmallest(5, 'pnl')
    for _, trade in worst_trades.iterrows():
        logger.info(f"  {trade['symbol']:10s} | {trade['direction']:5s} | "
                   f"${trade['pnl']:+10,.2f} ({trade['pnl_percent']:+6.2f}%) | "
                   f"{trade['entry_time']}")
    
    # Distribution des PnL
    logger.info("\n📊 Distribution des PnL:")
    bins = [-float('inf'), -100, -50, -10, 0, 10, 50, 100, float('inf')]
    labels = ['< -$100', '-$100 à -$50', '-$50 à -$10', '-$10 à $0', 
              '$0 à $10', '$10 à $50', '$50 à $100', '> $100']
    
    trades_df['pnl_range'] = pd.cut(trades_df['pnl'], bins=bins, labels=labels)
    distribution = trades_df['pnl_range'].value_counts().sort_index()
    
    for range_label, count in distribution.items():
        pct = (count / len(trades_df)) * 100
        logger.info(f"  {range_label:15s} | {count:3d} trades ({pct:5.1f}%)")
    
    logger.info("=" * 80)


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(
        description='Backtesting du robot de trading Polymarket'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        default=None,
        help='Symboles à tester (séparés par des virgules). Défaut: config.yaml'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Date de début (YYYY-MM-DD). Défaut: config.yaml'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='Date de fin (YYYY-MM-DD). Défaut: config.yaml'
    )
    parser.add_argument(
        '--capital',
        type=float,
        default=None,
        help='Capital initial. Défaut: config.yaml'
    )
    parser.add_argument(
        '--commission',
        type=float,
        default=None,
        help='Commission (ex: 0.001 = 0.1%%). Défaut: config.yaml'
    )
    parser.add_argument(
        '--slippage',
        type=float,
        default=None,
        help='Slippage (ex: 0.0005 = 0.05%%). Défaut: config.yaml'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Afficher les graphiques'
    )
    parser.add_argument(
        '--save-results',
        action='store_true',
        help='Sauvegarder les résultats'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Niveau de log'
    )
    
    args = parser.parse_args()
    
    # Configuration du logging
    setup_logging(args.log_level)
    
    logger.info("\n" + "=" * 80)
    logger.info("🚀 BACKTESTING ROBOT DE TRADING POLYMARKET")
    logger.info("=" * 80)
    
    # Charger la configuration
    config = get_config()
    
    # Paramètres du backtest
    symbols = args.symbols.split(',') if args.symbols else config.symbols
    start_date = args.start_date or config.backtest_start_date
    end_date = args.end_date or config.backtest_end_date
    capital = args.capital or config.initial_capital
    commission = args.commission or config.commission
    slippage = args.slippage or config.slippage
    
    logger.info(f"\n📋 Paramètres:")
    logger.info(f"  Symboles: {', '.join(symbols)}")
    logger.info(f"  Période: {start_date} à {end_date}")
    logger.info(f"  Capital initial: ${capital:,.2f}")
    logger.info(f"  Commission: {commission * 100:.2f}%")
    logger.info(f"  Slippage: {slippage * 100:.3f}%")
    logger.info("")
    
    # Créer le moteur de backtest
    backtest = BacktestEngine(
        initial_capital=capital,
        commission=commission,
        slippage=slippage,
        config=config
    )
    
    # Lancer le backtest
    try:
        results = backtest.run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        if not results:
            logger.error("Échec du backtest")
            sys.exit(1)
        
        # Analyse détaillée
        if 'trades' in results and not results['trades'].empty:
            analyze_trades(results['trades'])
        
        # Graphiques
        if args.plot and 'equity_curve' in results:
            output_file = f"backtest_equity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plot_equity_curve(results['equity_curve'], output_file)
        
        # Sauvegarder les résultats
        if args.save_results:
            backtest.save_results()
        
        # Verdict final
        logger.info("\n" + "=" * 80)
        logger.info("🎯 VERDICT FINAL")
        logger.info("=" * 80)
        
        win_rate = results.get('win_rate', 0)
        total_return = results.get('total_return', 0)
        max_dd = results.get('max_drawdown', 0)
        trades_per_day = results.get('trades_per_day', 0)
        
        # Critères de validation
        criteria = []
        
        if win_rate >= 55:
            criteria.append("✅ Win rate ≥ 55%")
        else:
            criteria.append(f"❌ Win rate < 55% ({win_rate:.1f}%)")
        
        if total_return > 0:
            criteria.append("✅ Retour total positif")
        else:
            criteria.append(f"❌ Retour total négatif ({total_return:.2f}%)")
        
        if 40 <= trades_per_day <= 60:
            criteria.append("✅ Nombre de trades/jour dans la cible (40-60)")
        else:
            criteria.append(f"⚠️  Trades/jour hors cible ({trades_per_day:.1f})")
        
        if abs(max_dd) < 10:
            criteria.append("✅ Drawdown acceptable (< 10%)")
        else:
            criteria.append(f"⚠️  Drawdown élevé ({max_dd:.2f}%)")
        
        for criterion in criteria:
            logger.info(f"  {criterion}")
        
        # Validation globale
        validated = win_rate >= 55 and total_return > 0
        
        logger.info("")
        if validated:
            logger.info("🎉 STRATÉGIE VALIDÉE - Prête pour la production!")
        else:
            logger.info("⚠️  STRATÉGIE À AMÉLIORER - Ajuster les paramètres")
        
        logger.info("=" * 80)
        
        sys.exit(0 if validated else 1)
        
    except Exception as e:
        logger.error(f"Erreur lors du backtest: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

