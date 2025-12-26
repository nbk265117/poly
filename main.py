#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main Trading Bot
Point d'entrée principal pour le robot de trading Polymarket
"""

import sys
import time
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path
import schedule

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.data_manager import DataManager
from src.strategy import TradingStrategy
from src.polymarket_client import PolymarketTradeExecutor
from src.telegram_bot import TelegramNotifier

# Configuration du logging
def setup_logging(config):
    """Configure le système de logging"""
    log_file = config.logs_dir / 'trading_bot.log'
    
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)


class TradingBot:
    """
    Robot de trading principal
    """
    
    def __init__(self):
        self.config = get_config()
        self.strategy = TradingStrategy(self.config)
        self.executor = PolymarketTradeExecutor(self.config)
        self.notifier = TelegramNotifier(self.config)
        self.data_manager = DataManager(self.config)
        
        self.running = False
        self.daily_trades = 0
        self.daily_pnl = 0
        self.last_daily_summary = None
        
        # Statistiques
        self.stats = {
            'trades_today': 0,
            'wins_today': 0,
            'losses_today': 0,
            'pnl_today': 0
        }
    
    def analyze_and_trade(self):
        """
        Analyse tous les symboles et exécute les trades si nécessaire
        """
        try:
            logger.info("=" * 80)
            logger.info("🔍 ANALYSE DES MARCHÉS")
            logger.info("=" * 80)
            
            # Vérifier limite journalière
            if self.daily_trades >= self.config.max_trades_per_day:
                logger.warning(f"Limite journalière atteinte ({self.config.max_trades_per_day} trades)")
                return
            
            # Analyser chaque symbole
            for symbol in self.config.symbols:
                logger.info(f"\n📊 Analyse de {symbol}...")
                
                # Obtenir le signal
                signal = self.strategy.analyze_market(symbol)
                
                if signal:
                    logger.info(f"✅ Signal détecté: {symbol} -> {signal}")
                    
                    # Récupérer le prix actuel
                    df = self.data_manager.get_live_data(symbol, self.config.primary_timeframe, limit=5)
                    
                    if df.empty:
                        logger.error(f"Impossible de récupérer les données pour {symbol}")
                        continue
                    
                    current_price = df.iloc[-1]['close']
                    
                    # Exécuter le trade
                    self._execute_trade(symbol, signal, current_price)
                else:
                    logger.info(f"ℹ️  Aucun signal pour {symbol}")
            
            logger.info("=" * 80)
            logger.info(f"Trades aujourd'hui: {self.daily_trades}/{self.config.max_trades_per_day}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {e}", exc_info=True)
            self.notifier.notify_error(f"Erreur analyse: {str(e)}")
    
    def _execute_trade(self, symbol: str, signal: str, current_price: float):
        """Exécute un trade"""
        try:
            # Vérifier positions ouvertes
            if len(self.strategy.open_trades) >= self.config.max_positions:
                logger.warning("Nombre maximum de positions atteint")
                return
            
            # Déterminer l'outcome
            outcome = 'UP' if signal == 'BUY' else 'DOWN'
            
            # Exécuter sur Polymarket
            order = self.executor.execute_signal(symbol, signal, current_price)
            
            if not order:
                logger.error(f"Échec de l'exécution de l'ordre pour {symbol}")
                return
            
            # Ouvrir le trade dans la stratégie
            trade = self.strategy.open_trade(
                symbol=symbol,
                direction=signal,
                entry_price=order.get('price', current_price),
                entry_time=datetime.now(),
                capital=self.executor.client.get_balance()
            )
            
            if trade:
                # Notifier
                self.notifier.notify_trade_entry(
                    symbol=symbol,
                    direction=signal,
                    outcome=outcome,
                    entry_price=trade.entry_price,
                    position_size=trade.position_size,
                    stop_loss=trade.stop_loss,
                    take_profit=trade.take_profit
                )
                
                # Mettre à jour les statistiques
                self.daily_trades += 1
                self.stats['trades_today'] += 1
                
                logger.info(f"✅ Trade exécuté avec succès: {symbol} {signal}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du trade: {e}", exc_info=True)
            self.notifier.notify_error(f"Erreur trade {symbol}: {str(e)}")
    
    def check_open_positions(self):
        """Vérifie les positions ouvertes (SL/TP)"""
        if not self.strategy.open_trades:
            return
        
        logger.info(f"Vérification de {len(self.strategy.open_trades)} positions ouvertes...")
        
        for trade in self.strategy.open_trades[:]:  # Copie pour éviter modification pendant itération
            try:
                # Récupérer le prix actuel
                df = self.data_manager.get_live_data(trade.symbol, self.config.primary_timeframe, limit=2)
                
                if df.empty:
                    continue
                
                current_price = df.iloc[-1]['close']
                current_time = df.iloc[-1]['timestamp']
                
                # Vérifier SL/TP
                closed = self.strategy.check_stop_loss_take_profit(trade, current_price, current_time)
                
                if closed:
                    # Fermer sur Polymarket
                    outcome = 'UP' if trade.direction == 'BUY' else 'DOWN'
                    self.executor.close_position(
                        symbol=trade.symbol,
                        outcome=outcome,
                        amount=trade.position_size * current_price
                    )
                    
                    # Notifier
                    self.notifier.notify_trade_exit(
                        symbol=trade.symbol,
                        direction=trade.direction,
                        outcome=outcome,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        pnl=trade.pnl,
                        pnl_percent=trade.pnl_percent,
                        exit_reason=trade.exit_reason
                    )
                    
                    # Mettre à jour statistiques
                    self.stats['pnl_today'] += trade.pnl
                    if trade.pnl > 0:
                        self.stats['wins_today'] += 1
                    else:
                        self.stats['losses_today'] += 1
                    
            except Exception as e:
                logger.error(f"Erreur vérification position {trade.symbol}: {e}")
    
    def send_daily_summary(self):
        """Envoie le résumé journalier"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if self.last_daily_summary == today:
            return  # Déjà envoyé aujourd'hui
        
        # Calculer les statistiques
        total_trades = self.stats['trades_today']
        wins = self.stats['wins_today']
        losses = self.stats['losses_today']
        pnl = self.stats['pnl_today']
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        capital = self.executor.client.get_balance()
        
        # Envoyer la notification
        self.notifier.notify_daily_summary(
            date=today,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            total_pnl=pnl,
            win_rate=win_rate,
            capital=capital
        )
        
        # Réinitialiser les compteurs
        self.stats = {
            'trades_today': 0,
            'wins_today': 0,
            'losses_today': 0,
            'pnl_today': 0
        }
        self.daily_trades = 0
        self.last_daily_summary = today
        
        logger.info("📊 Résumé journalier envoyé et compteurs réinitialisés")
    
    def run(self):
        """Lance le robot"""
        logger.info("\n" + "=" * 80)
        logger.info("🤖 DÉMARRAGE DU ROBOT DE TRADING POLYMARKET")
        logger.info("=" * 80)
        logger.info(f"Environment: {self.config.environment}")
        logger.info(f"Symboles: {', '.join(self.config.symbols)}")
        logger.info(f"Timeframe: {self.config.primary_timeframe}")
        logger.info(f"Position size: ${self.config.position_size_usd}")
        logger.info("=" * 80)
        
        # Notifier le démarrage
        self.notifier.notify_bot_start()
        
        # Planifier les tâches
        # Analyse toutes les 15 minutes (8 secondes avant la clôture)
        schedule.every(15).minutes.do(self.analyze_and_trade)
        
        # Vérification des positions toutes les minutes
        schedule.every(1).minutes.do(self.check_open_positions)
        
        # Résumé journalier à 23:55
        schedule.every().day.at("23:55").do(self.send_daily_summary)
        
        self.running = True
        
        logger.info("✅ Robot démarré. Appuyez sur Ctrl+C pour arrêter.\n")
        
        # Boucle principale
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("\n⚠️  Arrêt demandé par l'utilisateur")
        finally:
            self.stop()
    
    def stop(self):
        """Arrête le robot"""
        logger.info("Arrêt du robot...")
        self.running = False
        
        # Envoyer résumé final
        if self.stats['trades_today'] > 0:
            self.send_daily_summary()
        
        # Notifier l'arrêt
        self.notifier.notify_bot_stop("Arrêt manuel")
        
        logger.info("✅ Robot arrêté")


def signal_handler(signum, frame):
    """Gestionnaire de signaux pour arrêt propre"""
    logger.info(f"\nSignal {signum} reçu, arrêt en cours...")
    sys.exit(0)


def main():
    """Point d'entrée principal"""
    # Configuration du logging
    config = get_config()
    setup_logging(config)
    
    # Gestionnaire de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Créer et lancer le bot
    bot = TradingBot()
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        bot.notifier.notify_error(f"Erreur fatale: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

