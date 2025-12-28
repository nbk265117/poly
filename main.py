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
from datetime import datetime, timedelta, timezone
from pathlib import Path
import schedule

# Ajouter le répertoire au path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config
from src.data_manager import DataManager
from src.strategy import TradingStrategy
from src.polymarket_client import PolymarketTradeExecutor
from src.telegram_bot import TelegramNotifier
from src.performance_monitor import PerformanceMonitor, SessionFilter
from src.trade_validator import DynamicPriceValidator

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

    FONCTIONNALITES CRITIQUES:
    - Validation du prix moyen (doit etre < WR - 2%)
    - Filtrage des sessions faibles
    - Monitoring des performances par jour/heure/paire
    - Gestion des partial fills
    """

    def __init__(self, win_rate: float = 55.0, price_margin: float = 2.0):
        self.config = get_config()
        self.strategy = TradingStrategy(self.config)
        self.executor = PolymarketTradeExecutor(self.config)
        self.notifier = TelegramNotifier(self.config)
        self.data_manager = DataManager(self.config)

        self.running = False
        self.daily_trades = 0
        self.daily_pnl = 0
        self.last_daily_summary = None

        # NOUVEAU: Performance Monitor
        self.performance_monitor = PerformanceMonitor(
            config=self.config,
            min_wr_threshold=win_rate
        )

        # NOUVEAU: Session Filter (ACTIF par defaut avec heures optimisees)
        self.session_filter = SessionFilter(
            monitor=self.performance_monitor,
            min_wr=50.0,
            min_trades=20
        )

        # Bloquer les heures faibles identifiees par backtest 2024
        # Ces heures ont un WR < 50% sur 1 an de donnees
        weak_hours = [3, 7, 15, 18, 19, 20]  # Heures UTC a eviter
        for hour in weak_hours:
            self.session_filter.block_hour(hour)

        self.enable_session_filter = True  # ACTIF par defaut

        # Parametres de validation
        self.win_rate = win_rate
        self.price_margin = price_margin
        self.max_price = (win_rate - price_margin) / 100  # 53% si WR=55%

        # Statistiques
        self.stats = {
            'trades_today': 0,
            'wins_today': 0,
            'losses_today': 0,
            'pnl_today': 0,
            'trades_blocked_price': 0,
            'trades_blocked_session': 0
        }

        logger.info("=" * 70)
        logger.info("TRADING BOT INITIALISE")
        logger.info("=" * 70)
        logger.info(f"  Win Rate attendu: {win_rate}%")
        logger.info(f"  Prix max autorise: {self.max_price*100:.1f}%")
        logger.info(f"  Filtrage sessions: {'ACTIF' if self.enable_session_filter else 'INACTIF'}")
        logger.info(f"  Heures bloquees: {weak_hours}")
        logger.info("=" * 70)
    
    def analyze_and_trade(self):
        """
        Analyse tous les symboles et exécute les trades si nécessaire

        VALIDATIONS:
        1. Limite journaliere
        2. Session horaire (si active)
        3. Prix moyen (via executor)
        """
        try:
            logger.info("=" * 80)
            logger.info("ANALYSE DES MARCHES")
            logger.info("=" * 80)

            # Vérifier limite journalière
            if self.daily_trades >= self.config.max_trades_per_day:
                logger.warning(f"Limite journaliere atteinte ({self.config.max_trades_per_day} trades)")
                return

            # NOUVEAU: Verifier la session horaire
            if self.enable_session_filter:
                current_hour = datetime.now(timezone.utc).hour
                can_trade, reason = self.session_filter.is_tradeable(current_hour)

                if not can_trade:
                    logger.warning(f"Session bloquee: {reason}")
                    self.stats['trades_blocked_session'] += 1
                    return

            # Analyser chaque symbole
            for symbol in self.config.symbols:
                logger.info(f"\nAnalyse de {symbol}...")

                # Obtenir le signal
                signal = self.strategy.analyze_market(symbol)

                if signal:
                    logger.info(f"Signal detecte: {symbol} -> {signal}")

                    # Récupérer le prix actuel
                    df = self.data_manager.get_live_data(symbol, self.config.primary_timeframe, limit=5)

                    if df.empty:
                        logger.error(f"Impossible de recuperer les donnees pour {symbol}")
                        continue

                    current_price = df.iloc[-1]['close']

                    # Exécuter le trade (validation prix dans executor)
                    self._execute_trade(symbol, signal, current_price)
                else:
                    logger.info(f"Aucun signal pour {symbol}")

            # Afficher stats
            logger.info("=" * 80)
            logger.info(f"Trades aujourd'hui: {self.daily_trades}/{self.config.max_trades_per_day}")
            logger.info(f"Bloques (prix): {self.stats['trades_blocked_price']}")
            logger.info(f"Bloques (session): {self.stats['trades_blocked_session']}")

            # Afficher WR actuel
            global_wr = self.performance_monitor.get_global_win_rate()
            logger.info(f"Win Rate actuel: {global_wr:.1f}%")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Erreur lors de l'analyse: {e}", exc_info=True)
            self.notifier.notify_error(f"Erreur analyse: {str(e)}")
    
    def _execute_trade(self, symbol: str, signal: str, current_price: float):
        """
        Execute un trade avec validation du prix

        La validation du prix moyen est faite dans l'executor.
        Si le prix >= WR - 2%, l'ordre sera bloque.
        """
        try:
            # Vérifier positions ouvertes
            if len(self.strategy.open_trades) >= self.config.max_positions:
                logger.warning("Nombre maximum de positions atteint")
                return

            # Déterminer l'outcome
            outcome = 'UP' if signal == 'BUY' else 'DOWN'

            # Exécuter sur Polymarket (validation prix integree)
            order = self.executor.execute_signal(symbol, signal, current_price)

            if not order:
                # Ordre bloque (probablement par le prix)
                self.stats['trades_blocked_price'] += 1
                logger.warning(f"Ordre bloque pour {symbol} (prix trop eleve)")
                return

            # Ouvrir le trade dans la stratégie
            trade = self.strategy.open_trade(
                symbol=symbol,
                direction=signal,
                entry_price=order.get('price', current_price),
                entry_time=datetime.now(timezone.utc),
                capital=self.executor.client.get_balance()
            )

            if trade:
                # Stocker l'order_id pour le tracking
                trade.order_id = order.get('order_id', '')

                # Stocker les infos de fill
                fill_info = order.get('fill', {})
                trade.fill_ratio = fill_info.get('fill_ratio', 1.0)

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

                # Log validation info
                validation = order.get('validation', {})
                logger.info(
                    f"Trade execute: {symbol} {signal} | "
                    f"Prix: {trade.entry_price*100:.1f}% | "
                    f"Fill: {trade.fill_ratio*100:.0f}% | "
                    f"Marge: {validation.get('price_margin', 0)*100:.1f}%"
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'execution du trade: {e}", exc_info=True)
            self.notifier.notify_error(f"Erreur trade {symbol}: {str(e)}")
    
    def check_open_positions(self):
        """
        Verifie les positions ouvertes (SL/TP)

        Enregistre les resultats dans:
        - PerformanceMonitor (pour stats par heure/jour/paire)
        - Executor (pour mise a jour du WR dynamique)
        """
        if not self.strategy.open_trades:
            return

        logger.info(f"Verification de {len(self.strategy.open_trades)} positions ouvertes...")

        for trade in self.strategy.open_trades[:]:  # Copie pour éviter modification
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
                    # Determiner WIN/LOSS
                    is_win = trade.pnl > 0

                    # Fermer sur Polymarket
                    outcome = 'UP' if trade.direction == 'BUY' else 'DOWN'
                    # IMPORTANT: amount = nombre de shares (pas dollars)
                    self.executor.close_position(
                        symbol=trade.symbol,
                        outcome=outcome,
                        amount=self.config.position_size_usd  # Nombre de shares
                    )

                    # NOUVEAU: Enregistrer dans le PerformanceMonitor
                    self.performance_monitor.record_trade(
                        order_id=getattr(trade, 'order_id', ''),
                        symbol=trade.symbol,
                        direction=trade.direction,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        pnl=trade.pnl,
                        is_win=is_win,
                        entry_time=trade.entry_time,
                        exit_time=trade.exit_time,
                        fill_ratio=getattr(trade, 'fill_ratio', 1.0)
                    )

                    # NOUVEAU: Mettre a jour le WR dynamique dans l'executor
                    self.executor.client.record_trade_result(is_win)

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
                    if is_win:
                        self.stats['wins_today'] += 1
                    else:
                        self.stats['losses_today'] += 1

                    # Log avec details
                    logger.info(
                        f"Trade ferme: {trade.symbol} | "
                        f"{'WIN' if is_win else 'LOSS'} | "
                        f"PnL: ${trade.pnl:.2f} | "
                        f"WR actuel: {self.performance_monitor.get_global_win_rate():.1f}%"
                    )

                    # NOUVEAU: Activer le filtre de session apres 100 trades
                    total_trades = len(self.performance_monitor.trades)
                    if total_trades >= 100 and not self.enable_session_filter:
                        self.enable_session_filter = True
                        logger.info(f"Session filter ACTIVE apres {total_trades} trades")

            except Exception as e:
                logger.error(f"Erreur verification position {trade.symbol}: {e}")
    
    def send_daily_summary(self):
        """
        Envoie le résumé journalier avec stats avancees

        Inclut:
        - Stats de base (trades, WR, PnL)
        - Trades bloques par prix/session
        - Meilleures/pires heures
        - Performance par paire
        """
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

        # Stats avancees
        blocked_price = self.stats['trades_blocked_price']
        blocked_session = self.stats['trades_blocked_session']

        # Stats globales du moniteur
        summary = self.performance_monitor.get_summary()

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

        # Log les stats avancees
        logger.info("=" * 70)
        logger.info("RESUME JOURNALIER")
        logger.info("=" * 70)
        logger.info(f"  Trades: {total_trades} ({wins}W / {losses}L)")
        logger.info(f"  Win Rate: {win_rate:.1f}%")
        logger.info(f"  PnL: ${pnl:.2f}")
        logger.info(f"  Bloques (prix): {blocked_price}")
        logger.info(f"  Bloques (session): {blocked_session}")
        logger.info(f"  WR global: {summary['global']['win_rate']:.1f}%")
        logger.info(f"  Heures faibles: {summary['sessions']['weak_hours']}")
        logger.info("=" * 70)

        # Sauvegarder le rapport de performance
        self.performance_monitor.save_report()
        self.executor.client.log_trading_stats()

        # Réinitialiser les compteurs journaliers
        self.stats = {
            'trades_today': 0,
            'wins_today': 0,
            'losses_today': 0,
            'pnl_today': 0,
            'trades_blocked_price': 0,
            'trades_blocked_session': 0
        }
        self.daily_trades = 0
        self.last_daily_summary = today

        logger.info("Resume journalier envoye et compteurs reinitialises")
    
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

