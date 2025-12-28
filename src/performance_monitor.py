#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Monitor - Monitoring avance des performances

FONCTIONNALITES:
- Win Rate par jour
- Win Rate par session (heures)
- Win Rate par paire (BTC, ETH, SOL)
- Filtrage des periodes faibles
- Alertes performance
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import json
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Enregistrement d'un trade pour analyse"""
    order_id: str
    symbol: str
    direction: str  # BUY/SELL ou UP/DOWN
    entry_price: float
    exit_price: float
    pnl: float
    is_win: bool
    entry_time: datetime
    exit_time: datetime
    session_hour: int  # Heure UTC (0-23)
    day_of_week: int   # 0=Lundi, 6=Dimanche
    fill_ratio: float = 1.0

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'pnl': self.pnl,
            'is_win': self.is_win,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'session_hour': self.session_hour,
            'day_of_week': self.day_of_week,
            'fill_ratio': self.fill_ratio
        }


@dataclass
class SessionStats:
    """Statistiques par session horaire"""
    hour: int
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_entry_price: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0

    @property
    def is_weak(self) -> bool:
        """Session faible si WR < 50% avec au moins 10 trades"""
        return self.total_trades >= 10 and self.win_rate < 50.0


@dataclass
class DailyStats:
    """Statistiques journalieres"""
    date: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_entry_price: float = 0.0
    best_hour: int = 0
    worst_hour: int = 0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0


@dataclass
class PairStats:
    """Statistiques par paire"""
    symbol: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_entry_price: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0


class PerformanceMonitor:
    """
    Moniteur de performance avance

    Analyse les performances par:
    - Jour
    - Session horaire (heures UTC)
    - Paire (BTC, ETH, SOL)

    Detecte les periodes faibles a eviter
    """

    def __init__(self, config=None, min_wr_threshold: float = 55.0):
        """
        Args:
            config: Configuration du bot
            min_wr_threshold: Seuil minimum de WR acceptable
        """
        self.config = config
        self.min_wr_threshold = min_wr_threshold

        # Historique des trades
        self.trades: List[TradeRecord] = []

        # Stats par dimension
        self.daily_stats: Dict[str, DailyStats] = {}
        self.session_stats: Dict[int, SessionStats] = {h: SessionStats(hour=h) for h in range(24)}
        self.pair_stats: Dict[str, PairStats] = {}

        # Periodes a eviter (heures faibles)
        self.weak_hours: List[int] = []
        self.weak_days: List[int] = []  # 0=Lundi, 6=Dimanche

        # Alertes
        self.alerts: List[Dict] = []

        logger.info(f"PerformanceMonitor initialise (seuil WR: {min_wr_threshold}%)")

    def record_trade(
        self,
        order_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        is_win: bool,
        entry_time: datetime,
        exit_time: datetime = None,
        fill_ratio: float = 1.0
    ):
        """
        Enregistre un trade pour analyse

        Args:
            order_id: ID de l'ordre
            symbol: Symbole (BTC, ETH, etc.)
            direction: Direction (UP/DOWN ou BUY/SELL)
            entry_price: Prix d'entree
            exit_price: Prix de sortie
            pnl: Profit/Loss
            is_win: True si gagnant
            entry_time: Heure d'entree
            exit_time: Heure de sortie
            fill_ratio: Ratio de fill (1.0 = 100%)
        """
        if exit_time is None:
            exit_time = datetime.now(timezone.utc)

        # Normaliser le symbole
        symbol = symbol.split('/')[0].upper()

        record = TradeRecord(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            is_win=is_win,
            entry_time=entry_time,
            exit_time=exit_time,
            session_hour=entry_time.hour,
            day_of_week=entry_time.weekday(),
            fill_ratio=fill_ratio
        )

        self.trades.append(record)

        # Mettre a jour les stats
        self._update_daily_stats(record)
        self._update_session_stats(record)
        self._update_pair_stats(record)

        # Verifier les alertes
        self._check_alerts()

        logger.debug(
            f"Trade enregistre | {symbol} {direction} | "
            f"PnL: ${pnl:.2f} | Win: {is_win} | Heure: {record.session_hour}h"
        )

    def _update_daily_stats(self, record: TradeRecord):
        """Met a jour les stats journalieres"""
        date_str = record.entry_time.strftime('%Y-%m-%d')

        if date_str not in self.daily_stats:
            self.daily_stats[date_str] = DailyStats(date=date_str)

        stats = self.daily_stats[date_str]
        stats.total_trades += 1

        if record.is_win:
            stats.wins += 1
        else:
            stats.losses += 1

        stats.total_pnl += record.pnl

        # Recalculer prix moyen
        prices = [t.entry_price for t in self.trades if t.entry_time.strftime('%Y-%m-%d') == date_str]
        stats.avg_entry_price = sum(prices) / len(prices) if prices else 0

    def _update_session_stats(self, record: TradeRecord):
        """Met a jour les stats par session horaire"""
        hour = record.session_hour
        stats = self.session_stats[hour]

        stats.total_trades += 1

        if record.is_win:
            stats.wins += 1
        else:
            stats.losses += 1

        stats.total_pnl += record.pnl

        # Recalculer prix moyen
        prices = [t.entry_price for t in self.trades if t.session_hour == hour]
        stats.avg_entry_price = sum(prices) / len(prices) if prices else 0

        # Verifier si c'est une heure faible
        if stats.is_weak and hour not in self.weak_hours:
            self.weak_hours.append(hour)
            logger.warning(f"ALERTE: Heure {hour}h detectee comme faible (WR: {stats.win_rate:.1f}%)")

    def _update_pair_stats(self, record: TradeRecord):
        """Met a jour les stats par paire"""
        symbol = record.symbol

        if symbol not in self.pair_stats:
            self.pair_stats[symbol] = PairStats(symbol=symbol)

        stats = self.pair_stats[symbol]
        stats.total_trades += 1

        if record.is_win:
            stats.wins += 1
        else:
            stats.losses += 1

        stats.total_pnl += record.pnl

        # Recalculer prix moyen
        prices = [t.entry_price for t in self.trades if t.symbol == symbol]
        stats.avg_entry_price = sum(prices) / len(prices) if prices else 0

    def _check_alerts(self):
        """Verifie les conditions d'alerte"""
        # Alerte si WR global < seuil
        if len(self.trades) >= 20:
            global_wr = self.get_global_win_rate()
            if global_wr < self.min_wr_threshold:
                alert = {
                    'type': 'low_win_rate',
                    'message': f'Win Rate global faible: {global_wr:.1f}% < {self.min_wr_threshold}%',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'value': global_wr
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTE: {alert['message']}")

    def get_global_win_rate(self) -> float:
        """Retourne le win rate global"""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.is_win)
        return (wins / len(self.trades)) * 100

    def get_session_performance(self) -> pd.DataFrame:
        """
        Retourne les performances par session horaire

        Returns:
            DataFrame avec stats par heure
        """
        data = []
        for hour, stats in self.session_stats.items():
            data.append({
                'hour': hour,
                'total_trades': stats.total_trades,
                'wins': stats.wins,
                'losses': stats.losses,
                'win_rate': stats.win_rate,
                'total_pnl': stats.total_pnl,
                'avg_entry_price': stats.avg_entry_price * 100,
                'is_weak': stats.is_weak
            })

        return pd.DataFrame(data).sort_values('hour')

    def get_daily_performance(self) -> pd.DataFrame:
        """
        Retourne les performances par jour

        Returns:
            DataFrame avec stats par jour
        """
        data = []
        for date, stats in self.daily_stats.items():
            data.append({
                'date': date,
                'total_trades': stats.total_trades,
                'wins': stats.wins,
                'losses': stats.losses,
                'win_rate': stats.win_rate,
                'total_pnl': stats.total_pnl,
                'avg_entry_price': stats.avg_entry_price * 100
            })

        return pd.DataFrame(data).sort_values('date')

    def get_pair_performance(self) -> pd.DataFrame:
        """
        Retourne les performances par paire

        Returns:
            DataFrame avec stats par paire
        """
        data = []
        for symbol, stats in self.pair_stats.items():
            data.append({
                'symbol': symbol,
                'total_trades': stats.total_trades,
                'wins': stats.wins,
                'losses': stats.losses,
                'win_rate': stats.win_rate,
                'total_pnl': stats.total_pnl,
                'avg_entry_price': stats.avg_entry_price * 100
            })

        return pd.DataFrame(data).sort_values('win_rate', ascending=False)

    def should_trade_now(self, current_hour: int = None) -> Tuple[bool, str]:
        """
        Verifie si on devrait trader a l'heure actuelle

        Args:
            current_hour: Heure actuelle (UTC), None = heure courante

        Returns:
            Tuple (peut_trader, raison)
        """
        if current_hour is None:
            current_hour = datetime.now(timezone.utc).hour

        # Verifier si c'est une heure faible
        if current_hour in self.weak_hours:
            return False, f"Heure {current_hour}h dans les heures faibles (WR < 50%)"

        # Verifier les stats de l'heure
        stats = self.session_stats.get(current_hour)
        if stats and stats.total_trades >= 10 and stats.win_rate < 50:
            return False, f"Performance faible a {current_hour}h: WR = {stats.win_rate:.1f}%"

        return True, "OK"

    def get_best_hours(self, min_trades: int = 10) -> List[int]:
        """
        Retourne les meilleures heures pour trader

        Args:
            min_trades: Nombre minimum de trades pour etre considere

        Returns:
            Liste des heures avec WR >= seuil
        """
        best_hours = []
        for hour, stats in self.session_stats.items():
            if stats.total_trades >= min_trades and stats.win_rate >= self.min_wr_threshold:
                best_hours.append(hour)

        return sorted(best_hours)

    def get_worst_hours(self, min_trades: int = 10) -> List[int]:
        """
        Retourne les pires heures pour trader

        Args:
            min_trades: Nombre minimum de trades pour etre considere

        Returns:
            Liste des heures avec WR < 50%
        """
        return sorted(self.weak_hours)

    def get_summary(self) -> Dict:
        """Retourne un resume complet des performances"""
        global_wr = self.get_global_win_rate()
        total_pnl = sum(t.pnl for t in self.trades)
        avg_price = sum(t.entry_price for t in self.trades) / len(self.trades) if self.trades else 0

        # Meilleures et pires heures
        session_df = self.get_session_performance()
        valid_sessions = session_df[session_df['total_trades'] >= 5]

        best_hour = valid_sessions.loc[valid_sessions['win_rate'].idxmax()]['hour'] if len(valid_sessions) > 0 else None
        worst_hour = valid_sessions.loc[valid_sessions['win_rate'].idxmin()]['hour'] if len(valid_sessions) > 0 else None

        # Meilleure et pire paire
        pair_df = self.get_pair_performance()
        best_pair = pair_df.iloc[0]['symbol'] if len(pair_df) > 0 else None
        worst_pair = pair_df.iloc[-1]['symbol'] if len(pair_df) > 0 else None

        return {
            'global': {
                'total_trades': len(self.trades),
                'wins': sum(1 for t in self.trades if t.is_win),
                'losses': sum(1 for t in self.trades if not t.is_win),
                'win_rate': global_wr,
                'total_pnl': total_pnl,
                'avg_entry_price': avg_price * 100
            },
            'sessions': {
                'best_hour': best_hour,
                'worst_hour': worst_hour,
                'weak_hours': self.weak_hours,
                'best_hours': self.get_best_hours()
            },
            'pairs': {
                'best_pair': best_pair,
                'worst_pair': worst_pair,
                'stats': {s: {'wr': self.pair_stats[s].win_rate, 'pnl': self.pair_stats[s].total_pnl}
                         for s in self.pair_stats}
            },
            'alerts': self.alerts[-10:]  # Dernieres 10 alertes
        }

    def log_summary(self):
        """Affiche le resume des performances"""
        summary = self.get_summary()

        logger.info("=" * 70)
        logger.info("RESUME DES PERFORMANCES")
        logger.info("=" * 70)

        # Global
        g = summary['global']
        logger.info(f"\nGLOBAL:")
        logger.info(f"  Total trades: {g['total_trades']}")
        logger.info(f"  Wins/Losses: {g['wins']}/{g['losses']}")
        logger.info(f"  Win Rate: {g['win_rate']:.1f}%")
        logger.info(f"  PnL total: ${g['total_pnl']:.2f}")
        logger.info(f"  Prix moyen entree: {g['avg_entry_price']:.1f}%")

        # Sessions
        s = summary['sessions']
        logger.info(f"\nSESSIONS:")
        logger.info(f"  Meilleure heure: {s['best_hour']}h UTC")
        logger.info(f"  Pire heure: {s['worst_hour']}h UTC")
        logger.info(f"  Heures faibles: {s['weak_hours']}")
        logger.info(f"  Heures recommandees: {s['best_hours']}")

        # Paires
        p = summary['pairs']
        logger.info(f"\nPAIRES:")
        logger.info(f"  Meilleure: {p['best_pair']}")
        logger.info(f"  Pire: {p['worst_pair']}")
        for symbol, stats in p['stats'].items():
            logger.info(f"  {symbol}: WR={stats['wr']:.1f}%, PnL=${stats['pnl']:.2f}")

        # Alertes
        if summary['alerts']:
            logger.info(f"\nALERTES RECENTES:")
            for alert in summary['alerts'][-5:]:
                logger.info(f"  {alert['timestamp']}: {alert['message']}")

        logger.info("=" * 70)

    def save_report(self, output_path: str = "data/performance_report.json"):
        """Sauvegarde le rapport de performance"""
        import numpy as np

        def to_python_types(obj):
            """Convertit recurssivement tous les types numpy en Python natifs"""
            if obj is None:
                return None
            if isinstance(obj, (np.bool_, np.generic)):
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: to_python_types(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [to_python_types(i) for i in obj]
            if isinstance(obj, pd.DataFrame):
                return to_python_types(obj.to_dict('records'))
            return obj

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            report = {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'summary': to_python_types(self.get_summary()),
                'session_performance': to_python_types(self.get_session_performance().to_dict('records')),
                'daily_performance': to_python_types(self.get_daily_performance().to_dict('records')),
                'pair_performance': to_python_types(self.get_pair_performance().to_dict('records')),
                'trades': [t.to_dict() for t in self.trades[-1000:]]
            }

            with open(path, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Rapport sauvegarde: {path}")

        except Exception as e:
            logger.warning(f"Erreur sauvegarde rapport: {e}")

    def load_trades(self, input_path: str = "data/performance_report.json"):
        """Charge les trades depuis un fichier"""
        path = Path(input_path)
        if not path.exists():
            logger.warning(f"Fichier non trouve: {path}")
            return

        with open(path, 'r') as f:
            report = json.load(f)

        for t in report.get('trades', []):
            self.record_trade(
                order_id=t['order_id'],
                symbol=t['symbol'],
                direction=t['direction'],
                entry_price=t['entry_price'],
                exit_price=t['exit_price'],
                pnl=t['pnl'],
                is_win=t['is_win'],
                entry_time=datetime.fromisoformat(t['entry_time']),
                exit_time=datetime.fromisoformat(t['exit_time']),
                fill_ratio=t.get('fill_ratio', 1.0)
            )

        logger.info(f"Charges {len(self.trades)} trades depuis {path}")


class SessionFilter:
    """
    Filtre de sessions pour eviter les periodes faibles
    """

    def __init__(
        self,
        monitor: PerformanceMonitor,
        min_wr: float = 50.0,
        min_trades: int = 10
    ):
        """
        Args:
            monitor: Instance de PerformanceMonitor
            min_wr: WR minimum requis pour trader
            min_trades: Nombre min de trades pour evaluer une session
        """
        self.monitor = monitor
        self.min_wr = min_wr
        self.min_trades = min_trades

        # Heures bloquees manuellement
        self.blocked_hours: List[int] = []

    def block_hour(self, hour: int):
        """Bloque une heure specifique"""
        if hour not in self.blocked_hours:
            self.blocked_hours.append(hour)
            logger.info(f"Heure {hour}h bloquee")

    def unblock_hour(self, hour: int):
        """Debloque une heure"""
        if hour in self.blocked_hours:
            self.blocked_hours.remove(hour)
            logger.info(f"Heure {hour}h debloquee")

    def is_tradeable(self, hour: int = None) -> Tuple[bool, str]:
        """
        Verifie si l'heure est tradeable

        Args:
            hour: Heure a verifier (None = heure actuelle)

        Returns:
            Tuple (peut_trader, raison)
        """
        if hour is None:
            hour = datetime.now(timezone.utc).hour

        # Heures bloquees manuellement
        if hour in self.blocked_hours:
            return False, f"Heure {hour}h bloquee manuellement"

        # Heures faibles detectees
        if hour in self.monitor.weak_hours:
            return False, f"Heure {hour}h detectee comme faible"

        # Verifier les stats
        stats = self.monitor.session_stats.get(hour)
        if stats and stats.total_trades >= self.min_trades:
            if stats.win_rate < self.min_wr:
                return False, f"WR {stats.win_rate:.1f}% < {self.min_wr}% a {hour}h"

        return True, "OK"

    def get_tradeable_hours(self) -> List[int]:
        """Retourne la liste des heures tradeables"""
        tradeable = []
        for hour in range(24):
            can_trade, _ = self.is_tradeable(hour)
            if can_trade:
                tradeable.append(hour)
        return tradeable


if __name__ == "__main__":
    # Test du module
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )

    print("\n" + "=" * 60)
    print("TEST PERFORMANCE MONITOR")
    print("=" * 60)

    import random
    random.seed(42)

    # Creer un moniteur
    monitor = PerformanceMonitor(min_wr_threshold=55.0)

    # Simuler des trades sur plusieurs jours/heures
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    for i in range(500):
        # Temps aleatoire
        trade_time = base_time + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )

        # Symbole aleatoire
        symbol = random.choice(['BTC', 'ETH', 'SOL'])

        # Direction
        direction = random.choice(['UP', 'DOWN'])

        # Prix d'entree (entre 45% et 55%)
        entry_price = 0.45 + random.random() * 0.10

        # Win rate variable selon l'heure (simule des periodes faibles)
        hour = trade_time.hour
        if hour in [2, 3, 4]:  # Heures faibles
            wr = 0.40
        elif hour in [14, 15, 16]:  # Heures fortes
            wr = 0.65
        else:
            wr = 0.55

        is_win = random.random() < wr

        # PnL
        if is_win:
            pnl = entry_price * 0.9  # Payout 1.9x
        else:
            pnl = -entry_price

        # Enregistrer
        monitor.record_trade(
            order_id=f"order_{i}",
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            exit_price=1.0 if is_win else 0.0,
            pnl=pnl,
            is_win=is_win,
            entry_time=trade_time,
            fill_ratio=0.8 + random.random() * 0.2
        )

    # Afficher le resume
    monitor.log_summary()

    # Test du filtre de session
    print("\n" + "=" * 60)
    print("TEST SESSION FILTER")
    print("=" * 60)

    session_filter = SessionFilter(monitor, min_wr=50.0, min_trades=10)

    print("\nHeures tradeables:", session_filter.get_tradeable_hours())
    print("Heures faibles:", monitor.get_worst_hours())
    print("Meilleures heures:", monitor.get_best_hours())

    # Test verification heure
    for hour in [2, 3, 14, 15]:
        can_trade, reason = session_filter.is_tradeable(hour)
        status = "OK" if can_trade else "BLOQUE"
        print(f"  Heure {hour}h: {status} - {reason}")

    # Sauvegarder
    monitor.save_report("data/test_performance_report.json")
