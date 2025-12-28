#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest Avance - Analyse complete avec validation prix et periodes faibles

FONCTIONNALITES:
- Backtest >= 1 an
- Validation du prix moyen (doit etre < WR - 2%)
- Analyse des jours a WR < 55%
- Identification des plages horaires a eviter
- Calcul PnL base sur fills reels
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path

try:
    from src.config import get_config
    from src.data_manager import DataManager
    from src.strategy import TradingStrategy, Trade
    from src.indicators import IndicatorPipeline, MeanReversionPipeline
    from src.trade_validator import TradeValidator, PartialFillManager, DynamicPriceValidator
    from src.performance_monitor import PerformanceMonitor, SessionFilter
except ImportError:
    from config import get_config
    from data_manager import DataManager
    from strategy import TradingStrategy, Trade
    from indicators import IndicatorPipeline, MeanReversionPipeline
    from trade_validator import TradeValidator, PartialFillManager, DynamicPriceValidator
    from performance_monitor import PerformanceMonitor, SessionFilter

logger = logging.getLogger(__name__)


class AdvancedBacktest:
    """
    Backtest avance avec validation prix moyen et analyse des periodes faibles

    REGLES CRITIQUES:
    1. Prix moyen d'entree < WR - 2% (sinon trade bloque)
    2. Identification des heures faibles (WR < 50%)
    3. Calcul PnL base sur fills reels
    """

    def __init__(
        self,
        initial_capital: float = 10000,
        win_rate: float = 55.0,
        price_margin: float = 2.0,
        polymarket_payout: float = 1.9,
        commission: float = 0.001,
        config=None
    ):
        """
        Args:
            initial_capital: Capital initial
            win_rate: Win rate attendu (defaut 55%)
            price_margin: Marge de prix (defaut 2%)
            polymarket_payout: Payout Polymarket (defaut 1.9x)
            commission: Commission par trade
            config: Configuration
        """
        self.config = config or get_config()
        self.initial_capital = initial_capital
        self.win_rate = win_rate
        self.price_margin = price_margin
        self.polymarket_payout = polymarket_payout
        self.commission = commission

        self.capital = initial_capital
        self.equity_curve = []

        # Composants critiques
        self.price_validator = DynamicPriceValidator(
            initial_win_rate=win_rate,
            margin=price_margin,
            min_trades_for_update=50
        )
        self.fill_manager = PartialFillManager(config)
        self.performance_monitor = PerformanceMonitor(min_wr_threshold=55.0)
        self.session_filter = SessionFilter(self.performance_monitor, min_wr=50.0)

        # Data
        self.data_manager = DataManager(config)

        # Strategie (Mean Reversion par defaut)
        self.use_mean_reversion = True
        if self.use_mean_reversion:
            self.indicators = MeanReversionPipeline(config)
        else:
            self.indicators = IndicatorPipeline(config)

        # Resultats
        self.trades: List[Trade] = []
        self.open_trades: List[Trade] = []

        # Statistiques avancees
        self.stats = {
            'trades_blocked_by_price': 0,
            'trades_blocked_by_session': 0,
            'avg_entry_price': 0.0,
            'entry_prices': [],
            'partial_fills': 0
        }

        logger.info("=" * 70)
        logger.info("BACKTEST AVANCE INITIALISE")
        logger.info("=" * 70)
        logger.info(f"  Capital initial: ${initial_capital:,.2f}")
        logger.info(f"  Win Rate attendu: {win_rate}%")
        logger.info(f"  Prix max autorise: {(win_rate - price_margin)}%")
        logger.info(f"  Payout: {polymarket_payout}x")
        logger.info(f"  Strategie: {'Mean Reversion' if self.use_mean_reversion else 'Price Action'}")
        logger.info("=" * 70)

    def run_backtest(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        validate_prices: bool = True,
        filter_sessions: bool = False
    ) -> Dict:
        """
        Execute le backtest avance

        Args:
            symbols: Liste des paires a trader
            start_date: Date de debut (YYYY-MM-DD)
            end_date: Date de fin (YYYY-MM-DD)
            validate_prices: Activer la validation des prix
            filter_sessions: Activer le filtrage des sessions faibles

        Returns:
            Dict avec resultats du backtest
        """
        logger.info("\n" + "=" * 70)
        logger.info("DEMARRAGE BACKTEST AVANCE")
        logger.info("=" * 70)
        logger.info(f"Symboles: {', '.join(symbols)}")
        logger.info(f"Periode: {start_date} a {end_date}")
        logger.info(f"Validation prix: {'OUI' if validate_prices else 'NON'}")
        logger.info(f"Filtrage sessions: {'OUI' if filter_sessions else 'NON'}")
        logger.info("=" * 70)

        # Charger les donnees
        data_dict = {}
        multi_tf_data = {}

        for symbol in symbols:
            logger.info(f"\nChargement des donnees pour {symbol}...")

            multi_tf_data[symbol] = self.data_manager.prepare_multi_timeframe_data(
                symbol,
                self.config.ftfc_timeframes
            )

            df = multi_tf_data[symbol][self.config.primary_timeframe].copy()

            # Filtrer sur la periode
            df = df[
                (df['timestamp'] >= pd.to_datetime(start_date, utc=True)) &
                (df['timestamp'] <= pd.to_datetime(end_date, utc=True))
            ]

            if len(df) < 100:
                logger.warning(f"Pas assez de donnees pour {symbol}")
                continue

            # Calculer les indicateurs
            df = self.indicators.calculate_all(df, multi_tf_data[symbol])

            data_dict[symbol] = df
            logger.info(f"  {len(df)} bougies chargees")

        if not data_dict:
            logger.error("Aucune donnee disponible")
            return {}

        # Trouver la periode commune
        all_timestamps = []
        for df in data_dict.values():
            all_timestamps.extend(df['timestamp'].tolist())

        timestamps = sorted(set(all_timestamps))
        logger.info(f"\nNombre de bougies a traiter: {len(timestamps)}")

        # Simulation
        logger.info("\n" + "=" * 70)
        logger.info("SIMULATION EN COURS...")
        logger.info("=" * 70)

        for i, ts in enumerate(timestamps):
            # Progression
            if i % 2000 == 0 and i > 0:
                progress = (i / len(timestamps)) * 100
                wr = self.performance_monitor.get_global_win_rate()
                logger.info(
                    f"Progression: {progress:.1f}% | "
                    f"Trades: {len(self.trades)} | "
                    f"WR: {wr:.1f}% | "
                    f"Capital: ${self.capital:,.2f}"
                )

            # Verifier les trades ouverts (15 min ecoulees)
            for trade in self.open_trades[:]:
                symbol_df = data_dict.get(trade.symbol)
                if symbol_df is None:
                    continue

                time_elapsed = (ts - trade.entry_time).total_seconds() / 60

                if time_elapsed >= 15:
                    idx = symbol_df['timestamp'].searchsorted(ts, side='right') - 1
                    if idx < 0 or idx >= len(symbol_df):
                        continue

                    current_close = symbol_df.iloc[idx]['close']

                    # Determiner WIN/LOSS
                    if trade.direction == 'BUY':
                        is_win = current_close > trade.entry_price
                    else:
                        is_win = current_close < trade.entry_price

                    reason = 'polymarket_win' if is_win else 'polymarket_loss'
                    self._close_trade(trade, current_close, ts, reason, is_win)

            # Analyser chaque symbole pour nouveaux signaux
            for symbol, df in data_dict.items():
                idx = df['timestamp'].searchsorted(ts, side='right') - 1
                if idx < 0 or idx >= len(df):
                    continue

                row = df.iloc[idx]

                # Generer le signal
                signal = self.indicators.generate_signal(row)

                if signal:
                    # Verifier si on peut ouvrir une position
                    if len(self.open_trades) < self.config.max_positions:
                        # Simuler un prix d'entree (entre 45% et 55%)
                        # En realite, le prix depend de l'orderbook
                        entry_price = 0.48 + np.random.random() * 0.07  # 48% - 55%

                        # VALIDATION 1: Prix moyen
                        if validate_prices:
                            validation = self.price_validator.validate_trade(
                                entry_price, symbol, signal
                            )

                            if not validation.is_valid:
                                self.stats['trades_blocked_by_price'] += 1
                                continue

                        # VALIDATION 2: Session horaire
                        if filter_sessions:
                            hour = ts.hour
                            can_trade, reason = self.session_filter.is_tradeable(hour)

                            if not can_trade:
                                self.stats['trades_blocked_by_session'] += 1
                                continue

                        # Ouvrir le trade
                        self._open_trade(symbol, signal, entry_price, ts)

            # Enregistrer equity
            self.equity_curve.append({
                'timestamp': ts,
                'equity': self.capital,
                'open_trades': len(self.open_trades)
            })

        # Fermer les positions restantes
        logger.info("\nFermeture des positions ouvertes...")
        for trade in self.open_trades[:]:
            symbol_df = data_dict.get(trade.symbol)
            if symbol_df is not None:
                exit_price = symbol_df.iloc[-1]['close']
                self._close_trade(trade, exit_price, timestamps[-1], 'backtest_end', False)

        # Calculer les statistiques
        results = self._calculate_statistics()

        # Afficher les resultats
        self._print_results(results)

        # Analyser les periodes faibles
        self._analyze_weak_periods()

        return results

    def _open_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        entry_time: datetime
    ) -> Optional[Trade]:
        """Ouvre un trade avec validation"""
        # Montant a miser
        bet_amount = min(
            self.config.position_size_usd,
            self.capital * 0.95
        )

        if bet_amount < 5 or self.capital < 5:
            return None

        position_size = bet_amount / entry_price

        # Deduire du capital
        self.capital -= bet_amount

        # Simuler un fill partiel (80-100%)
        fill_ratio = 0.80 + np.random.random() * 0.20
        actual_size = position_size * fill_ratio

        if fill_ratio < 1.0:
            self.stats['partial_fills'] += 1

        # Enregistrer le prix d'entree
        self.stats['entry_prices'].append(entry_price)

        trade = Trade(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size=actual_size,
            stop_loss=0,
            take_profit=0
        )

        # Stocker le fill ratio
        trade.fill_ratio = fill_ratio

        self.open_trades.append(trade)
        self.trades.append(trade)

        return trade

    def _close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        reason: str,
        is_win: bool
    ):
        """Ferme un trade et calcule le PnL reel"""
        trade.close(exit_price, exit_time, reason)

        bet_amount = trade.position_size * trade.entry_price

        if reason == 'polymarket_win':
            payout = bet_amount * self.polymarket_payout
            trade.pnl = payout - bet_amount
            self.capital += payout
        elif reason == 'polymarket_loss':
            trade.pnl = -bet_amount
        else:
            trade.pnl = 0
            self.capital += bet_amount

        # Commission
        commission = bet_amount * self.commission
        self.capital -= commission

        # Enregistrer dans le moniteur
        self.performance_monitor.record_trade(
            order_id=f"bt_{len(self.trades)}",
            symbol=trade.symbol,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            pnl=trade.pnl,
            is_win=is_win,
            entry_time=trade.entry_time,
            exit_time=exit_time,
            fill_ratio=getattr(trade, 'fill_ratio', 1.0)
        )

        # Mettre a jour le WR dynamique
        self.price_validator.record_trade_result(is_win)

        if trade in self.open_trades:
            self.open_trades.remove(trade)

    def _calculate_statistics(self) -> Dict:
        """Calcule les statistiques du backtest"""
        if not self.trades:
            return {}

        trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
        equity_df = pd.DataFrame(self.equity_curve)

        # Stats de base
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = trades_df['pnl'].sum()
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0

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

        # Sharpe
        equity_df['returns'] = equity_df['equity'].pct_change()
        sharpe = equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252) if len(equity_df) > 1 else 0

        # Trades par jour
        if len(trades_df) > 0:
            duration = (trades_df['entry_time'].max() - trades_df['entry_time'].min()).days
            trades_per_day = total_trades / duration if duration > 0 else 0
        else:
            trades_per_day = 0

        # Prix moyen d'entree
        avg_entry_price = np.mean(self.stats['entry_prices']) if self.stats['entry_prices'] else 0

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
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'trades_per_day': trades_per_day,
            'avg_entry_price': avg_entry_price * 100,
            'trades_blocked_by_price': self.stats['trades_blocked_by_price'],
            'trades_blocked_by_session': self.stats['trades_blocked_by_session'],
            'partial_fills': self.stats['partial_fills'],
            'equity_curve': equity_df,
            'trades': trades_df
        }

    def _print_results(self, results: Dict):
        """Affiche les resultats"""
        logger.info("\n" + "=" * 70)
        logger.info("RESULTATS DU BACKTEST AVANCE")
        logger.info("=" * 70)

        logger.info(f"\nPERFORMANCE")
        logger.info(f"  Capital initial: ${results['initial_capital']:,.2f}")
        logger.info(f"  Capital final: ${results['final_capital']:,.2f}")
        logger.info(f"  PnL total: ${results['total_pnl']:,.2f}")
        logger.info(f"  Retour total: {results['total_return']:.2f}%")

        logger.info(f"\nSTATISTIQUES DES TRADES")
        logger.info(f"  Nombre total: {results['total_trades']}")
        logger.info(f"  Gagnants: {results['winning_trades']}")
        logger.info(f"  Perdants: {results['losing_trades']}")
        logger.info(f"  Win Rate: {results['win_rate']:.2f}%")
        logger.info(f"  Trades/jour: {results['trades_per_day']:.1f}")

        logger.info(f"\nVALIDATION PRIX")
        logger.info(f"  Prix moyen entree: {results['avg_entry_price']:.2f}%")
        logger.info(f"  Trades bloques (prix): {results['trades_blocked_by_price']}")
        logger.info(f"  Trades bloques (session): {results['trades_blocked_by_session']}")
        logger.info(f"  Partial fills: {results['partial_fills']}")

        logger.info(f"\nRISQUE")
        logger.info(f"  Drawdown max: {results['max_drawdown']:.2f}%")
        logger.info(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"  Profit Factor: {results['profit_factor']:.2f}")

        # Verdict
        logger.info("\n" + "=" * 70)
        if results['win_rate'] >= 55 and results['total_return'] > 0:
            if results['avg_entry_price'] < 53:
                logger.info("EXCELLENT - WR >= 55% ET prix moyen < 53%")
            else:
                logger.info("ATTENTION - WR bon mais prix moyen trop eleve!")
        elif results['win_rate'] >= 50:
            logger.info("ACCEPTABLE - WR >= 50% mais amelioration possible")
        else:
            logger.info("ECHEC - WR < 50%, strategie a revoir")
        logger.info("=" * 70)

    def _analyze_weak_periods(self):
        """Analyse les periodes faibles"""
        logger.info("\n" + "=" * 70)
        logger.info("ANALYSE DES PERIODES FAIBLES")
        logger.info("=" * 70)

        # Stats par session
        session_df = self.performance_monitor.get_session_performance()

        logger.info("\nPERFORMANCE PAR HEURE (UTC):")
        logger.info("-" * 50)

        weak_hours = []
        strong_hours = []

        for _, row in session_df.iterrows():
            if row['total_trades'] >= 10:
                status = ""
                if row['win_rate'] >= 55:
                    status = "FORT"
                    strong_hours.append(int(row['hour']))
                elif row['win_rate'] < 50:
                    status = "FAIBLE"
                    weak_hours.append(int(row['hour']))
                else:
                    status = "OK"

                logger.info(
                    f"  {int(row['hour']):02d}h: "
                    f"WR={row['win_rate']:.1f}% | "
                    f"Trades={row['total_trades']} | "
                    f"PnL=${row['total_pnl']:.2f} | "
                    f"{status}"
                )

        logger.info("\n" + "-" * 50)
        logger.info(f"HEURES FAIBLES (WR < 50%): {weak_hours}")
        logger.info(f"HEURES FORTES (WR >= 55%): {strong_hours}")

        # Stats par jour
        daily_df = self.performance_monitor.get_daily_performance()

        if len(daily_df) > 0:
            weak_days = daily_df[daily_df['win_rate'] < 55]
            logger.info(f"\nJOURS FAIBLES (WR < 55%): {len(weak_days)}/{len(daily_df)}")

            if len(weak_days) > 0:
                logger.info("  Dates concernees:")
                for _, row in weak_days.iterrows():
                    logger.info(f"    {row['date']}: WR={row['win_rate']:.1f}%, PnL=${row['total_pnl']:.2f}")

        # Stats par paire
        pair_df = self.performance_monitor.get_pair_performance()

        logger.info("\nPERFORMANCE PAR PAIRE:")
        for _, row in pair_df.iterrows():
            status = "FORT" if row['win_rate'] >= 55 else ("FAIBLE" if row['win_rate'] < 50 else "OK")
            logger.info(
                f"  {row['symbol']}: "
                f"WR={row['win_rate']:.1f}% | "
                f"Trades={row['total_trades']} | "
                f"PnL=${row['total_pnl']:.2f} | "
                f"{status}"
            )

        logger.info("=" * 70)

        # Sauvegarder le rapport
        self.performance_monitor.save_report("data/backtest_performance_report.json")

    def save_results(self, output_dir: str = "backtest_results"):
        """Sauvegarde les resultats"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Trades
        if self.trades:
            trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
            trades_file = output_path / f"trades_advanced_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False)
            logger.info(f"Trades sauvegardes: {trades_file}")

        # Equity
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_file = output_path / f"equity_advanced_{timestamp}.csv"
            equity_df.to_csv(equity_file, index=False)
            logger.info(f"Equity sauvegardee: {equity_file}")


def run_full_backtest():
    """Execute un backtest complet sur 1 an+"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )

    config = get_config()

    # Creer le backtest
    backtest = AdvancedBacktest(
        initial_capital=10000,
        win_rate=55.0,
        price_margin=2.0,
        polymarket_payout=1.9,
        commission=0.001,
        config=config
    )

    # Executer sur 1 an
    results = backtest.run_backtest(
        symbols=['BTC/USDT'],
        start_date='2024-01-01',
        end_date='2024-12-31',
        validate_prices=True,
        filter_sessions=False  # Activer apres la premiere passe
    )

    # Sauvegarder
    backtest.save_results()

    return results


if __name__ == "__main__":
    run_full_backtest()
