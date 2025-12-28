#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trade Validator - Module de validation des trades
REGLE CRITIQUE: Le prix moyen d'entree doit etre < WR - 2%

Si WR = 55.5%, prix moyen DOIT etre < 53.5%
Sinon -> perte long terme garantie
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TradeValidation:
    """Resultat de la validation d'un trade"""
    is_valid: bool
    reason: str
    market_price: float
    max_allowed_price: float
    current_win_rate: float
    price_margin: float  # Marge entre prix et limite


@dataclass
class PartialFillInfo:
    """Information sur un fill partiel"""
    order_id: str
    expected_size: float
    filled_size: float
    fill_ratio: float
    avg_fill_price: float
    timestamp: datetime

    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'expected_size': self.expected_size,
            'filled_size': self.filled_size,
            'fill_ratio': self.fill_ratio,
            'avg_fill_price': self.avg_fill_price,
            'timestamp': self.timestamp.isoformat()
        }


class TradeValidator:
    """
    Validateur de trades avec regle de prix moyen

    REGLE PRINCIPALE:
    - Si WR = 55%, prix moyen max = 53% (WR - 2%)
    - Si prix marche >= prix max -> TRADE INTERDIT
    """

    def __init__(self, config=None, win_rate: float = 55.0, margin: float = 2.0):
        """
        Args:
            config: Configuration du bot
            win_rate: Win rate attendu (defaut 55%)
            margin: Marge de securite (defaut 2%)
        """
        self.config = config
        self.expected_win_rate = win_rate
        self.margin = margin
        self.max_price = (win_rate - margin) / 100  # 53% pour WR=55%, margin=2%

        # Historique des validations
        self.validation_history: List[TradeValidation] = []

        # Statistiques
        self.stats = {
            'total_validations': 0,
            'trades_approved': 0,
            'trades_blocked': 0,
            'blocked_by_price': 0,
            'avg_entry_price': 0.0,
            'total_entry_prices': []
        }

        logger.info(f"TradeValidator initialise")
        logger.info(f"  Win Rate attendu: {win_rate}%")
        logger.info(f"  Marge securite: {margin}%")
        logger.info(f"  Prix max autorise: {self.max_price*100:.1f}%")

    def update_win_rate(self, new_win_rate: float):
        """
        Met a jour le win rate et recalcule le prix max

        Args:
            new_win_rate: Nouveau win rate observe
        """
        old_max = self.max_price
        self.expected_win_rate = new_win_rate
        self.max_price = (new_win_rate - self.margin) / 100

        logger.info(f"Win Rate mis a jour: {new_win_rate:.1f}%")
        logger.info(f"Prix max: {old_max*100:.1f}% -> {self.max_price*100:.1f}%")

    def validate_trade(
        self,
        market_price: float,
        symbol: str = None,
        direction: str = None
    ) -> TradeValidation:
        """
        Valide un trade avant execution

        REGLE: IF average_price >= (WR - 2%) -> trade interdit

        Args:
            market_price: Prix actuel du marche (0-1)
            symbol: Symbole du trade (optionnel)
            direction: Direction BUY/SELL (optionnel)

        Returns:
            TradeValidation avec is_valid et raison
        """
        self.stats['total_validations'] += 1

        # Calculer la marge
        price_margin = self.max_price - market_price

        # Validation
        if market_price >= self.max_price:
            # TRADE INTERDIT
            validation = TradeValidation(
                is_valid=False,
                reason=f"Prix {market_price*100:.1f}% >= limite {self.max_price*100:.1f}%",
                market_price=market_price,
                max_allowed_price=self.max_price,
                current_win_rate=self.expected_win_rate,
                price_margin=price_margin
            )

            self.stats['trades_blocked'] += 1
            self.stats['blocked_by_price'] += 1

            logger.warning(
                f"TRADE BLOQUE | {symbol or 'N/A'} {direction or 'N/A'} | "
                f"Prix: {market_price*100:.1f}% >= Limite: {self.max_price*100:.1f}%"
            )
        else:
            # TRADE AUTORISE
            validation = TradeValidation(
                is_valid=True,
                reason=f"Prix {market_price*100:.1f}% < limite {self.max_price*100:.1f}%",
                market_price=market_price,
                max_allowed_price=self.max_price,
                current_win_rate=self.expected_win_rate,
                price_margin=price_margin
            )

            self.stats['trades_approved'] += 1
            self.stats['total_entry_prices'].append(market_price)

            # Recalculer prix moyen
            if self.stats['total_entry_prices']:
                self.stats['avg_entry_price'] = sum(self.stats['total_entry_prices']) / len(self.stats['total_entry_prices'])

            logger.info(
                f"TRADE VALIDE | {symbol or 'N/A'} {direction or 'N/A'} | "
                f"Prix: {market_price*100:.1f}% | Marge: {price_margin*100:.1f}%"
            )

        self.validation_history.append(validation)
        return validation

    def get_stats(self) -> Dict:
        """Retourne les statistiques de validation"""
        return {
            **self.stats,
            'approval_rate': (self.stats['trades_approved'] / max(1, self.stats['total_validations'])) * 100,
            'avg_entry_price_percent': self.stats['avg_entry_price'] * 100,
            'max_allowed_price_percent': self.max_price * 100,
            'expected_win_rate': self.expected_win_rate
        }

    def log_stats(self):
        """Affiche les statistiques"""
        stats = self.get_stats()
        logger.info("=" * 60)
        logger.info("STATISTIQUES VALIDATION TRADES")
        logger.info("=" * 60)
        logger.info(f"  Total validations: {stats['total_validations']}")
        logger.info(f"  Trades approuves: {stats['trades_approved']}")
        logger.info(f"  Trades bloques: {stats['trades_blocked']}")
        logger.info(f"  Taux approbation: {stats['approval_rate']:.1f}%")
        logger.info(f"  Prix moyen entree: {stats['avg_entry_price_percent']:.2f}%")
        logger.info(f"  Prix max autorise: {stats['max_allowed_price_percent']:.1f}%")
        logger.info("=" * 60)


class PartialFillManager:
    """
    Gestionnaire des fills partiels

    Calcule le PnL base sur le montant reellement execute
    """

    def __init__(self, config=None):
        self.config = config
        self.fills: Dict[str, PartialFillInfo] = {}

        # Statistiques
        self.stats = {
            'total_orders': 0,
            'fully_filled': 0,
            'partially_filled': 0,
            'avg_fill_ratio': 0.0,
            'total_expected': 0.0,
            'total_filled': 0.0
        }

        logger.info("PartialFillManager initialise")

    def record_fill(
        self,
        order_id: str,
        expected_size: float,
        filled_size: float,
        avg_fill_price: float
    ) -> PartialFillInfo:
        """
        Enregistre un fill (complet ou partiel)

        Args:
            order_id: ID de l'ordre
            expected_size: Taille attendue
            filled_size: Taille reellement executee
            avg_fill_price: Prix moyen d'execution

        Returns:
            PartialFillInfo avec les details
        """
        fill_ratio = filled_size / expected_size if expected_size > 0 else 0

        fill_info = PartialFillInfo(
            order_id=order_id,
            expected_size=expected_size,
            filled_size=filled_size,
            fill_ratio=fill_ratio,
            avg_fill_price=avg_fill_price,
            timestamp=datetime.now(timezone.utc)
        )

        self.fills[order_id] = fill_info

        # Mettre a jour les stats
        self.stats['total_orders'] += 1
        self.stats['total_expected'] += expected_size
        self.stats['total_filled'] += filled_size

        if fill_ratio >= 0.99:  # Tolerance 1%
            self.stats['fully_filled'] += 1
            log_level = logging.INFO
        else:
            self.stats['partially_filled'] += 1
            log_level = logging.WARNING

        # Recalculer ratio moyen
        if self.stats['total_expected'] > 0:
            self.stats['avg_fill_ratio'] = self.stats['total_filled'] / self.stats['total_expected']

        logger.log(
            log_level,
            f"FILL | Order: {order_id[:10]}... | "
            f"Expected: {expected_size:.4f} | Filled: {filled_size:.4f} | "
            f"Ratio: {fill_ratio*100:.1f}% | Price: {avg_fill_price:.4f}"
        )

        return fill_info

    def calculate_real_pnl(
        self,
        order_id: str,
        outcome_price: float,
        is_win: bool
    ) -> Tuple[float, Dict]:
        """
        Calcule le PnL reel base sur le fill effectif

        Args:
            order_id: ID de l'ordre
            outcome_price: Prix de resolution (1.0 si win, 0.0 si loss)
            is_win: True si le trade a gagne

        Returns:
            Tuple (pnl_reel, details)
        """
        fill_info = self.fills.get(order_id)

        if not fill_info:
            logger.warning(f"Fill info not found for order {order_id}")
            return 0.0, {}

        # Capital reellement investi
        invested = fill_info.filled_size * fill_info.avg_fill_price

        # Payout si win (shares * 1.0 - invested)
        if is_win:
            payout = fill_info.filled_size * outcome_price  # = filled_size si outcome=1.0
            pnl = payout - invested
        else:
            # Loss = on perd l'investissement
            pnl = -invested

        details = {
            'order_id': order_id,
            'expected_size': fill_info.expected_size,
            'filled_size': fill_info.filled_size,
            'fill_ratio': fill_info.fill_ratio,
            'avg_fill_price': fill_info.avg_fill_price,
            'invested': invested,
            'outcome_price': outcome_price,
            'is_win': is_win,
            'pnl': pnl,
            'pnl_if_full_fill': (fill_info.expected_size * (outcome_price if is_win else 0)) - (fill_info.expected_size * fill_info.avg_fill_price)
        }

        logger.info(
            f"PNL CALCULE | Order: {order_id[:10]}... | "
            f"Investi: ${invested:.2f} | PnL: ${pnl:.2f} | "
            f"Fill: {fill_info.fill_ratio*100:.1f}%"
        )

        return pnl, details

    def get_stats(self) -> Dict:
        """Retourne les statistiques"""
        return {
            **self.stats,
            'avg_fill_ratio_percent': self.stats['avg_fill_ratio'] * 100,
            'partial_fill_rate': (self.stats['partially_filled'] / max(1, self.stats['total_orders'])) * 100
        }

    def log_stats(self):
        """Affiche les statistiques"""
        stats = self.get_stats()
        logger.info("=" * 60)
        logger.info("STATISTIQUES FILLS PARTIELS")
        logger.info("=" * 60)
        logger.info(f"  Total ordres: {stats['total_orders']}")
        logger.info(f"  Fully filled: {stats['fully_filled']}")
        logger.info(f"  Partially filled: {stats['partially_filled']}")
        logger.info(f"  Ratio moyen fill: {stats['avg_fill_ratio_percent']:.1f}%")
        logger.info(f"  Taux partial fills: {stats['partial_fill_rate']:.1f}%")
        logger.info(f"  Total attendu: ${stats['total_expected']:.2f}")
        logger.info(f"  Total execute: ${stats['total_filled']:.2f}")
        logger.info("=" * 60)

    def save_fills(self, output_path: str = "data/fills.json"):
        """Sauvegarde les fills dans un fichier"""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'fills': {k: v.to_dict() for k, v in self.fills.items()},
            'stats': self.get_stats()
        }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Fills sauvegardes: {path}")


class DynamicPriceValidator:
    """
    Validateur dynamique qui ajuste le prix max en fonction du WR observe
    """

    def __init__(
        self,
        initial_win_rate: float = 55.0,
        margin: float = 2.0,
        min_trades_for_update: int = 20
    ):
        """
        Args:
            initial_win_rate: WR initial attendu
            margin: Marge de securite
            min_trades_for_update: Nombre min de trades avant mise a jour WR
        """
        self.margin = margin
        self.min_trades_for_update = min_trades_for_update

        self.validator = TradeValidator(win_rate=initial_win_rate, margin=margin)

        # Historique pour calcul WR dynamique
        self.trade_results: List[bool] = []  # True=win, False=loss

        logger.info(f"DynamicPriceValidator initialise")
        logger.info(f"  WR initial: {initial_win_rate}%")
        logger.info(f"  Min trades pour update: {min_trades_for_update}")

    def validate_trade(
        self,
        market_price: float,
        symbol: str = None,
        direction: str = None
    ) -> TradeValidation:
        """Valide un trade avec le WR actuel"""
        return self.validator.validate_trade(market_price, symbol, direction)

    def record_trade_result(self, is_win: bool):
        """
        Enregistre le resultat d'un trade et met a jour le WR si necessaire

        Args:
            is_win: True si le trade a gagne
        """
        self.trade_results.append(is_win)

        # Mettre a jour le WR si assez de trades
        if len(self.trade_results) >= self.min_trades_for_update:
            # Calculer WR sur les N derniers trades
            recent_results = self.trade_results[-self.min_trades_for_update:]
            observed_wr = sum(recent_results) / len(recent_results) * 100

            # Mettre a jour le validateur
            self.validator.update_win_rate(observed_wr)

            logger.info(
                f"WR dynamique mis a jour | "
                f"Derniers {self.min_trades_for_update} trades: {observed_wr:.1f}%"
            )

    def get_current_win_rate(self) -> float:
        """Retourne le WR actuel"""
        return self.validator.expected_win_rate

    def get_max_price(self) -> float:
        """Retourne le prix max autorise"""
        return self.validator.max_price

    def get_stats(self) -> Dict:
        """Retourne les statistiques combinees"""
        validator_stats = self.validator.get_stats()

        # Ajouter stats WR observe
        if self.trade_results:
            observed_wr = sum(self.trade_results) / len(self.trade_results) * 100
        else:
            observed_wr = 0

        return {
            **validator_stats,
            'total_trades_recorded': len(self.trade_results),
            'observed_win_rate': observed_wr,
            'wins': sum(self.trade_results),
            'losses': len(self.trade_results) - sum(self.trade_results)
        }


if __name__ == "__main__":
    # Test du module
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )

    print("\n" + "=" * 60)
    print("TEST TRADE VALIDATOR")
    print("=" * 60)

    # Test TradeValidator
    validator = TradeValidator(win_rate=55.0, margin=2.0)

    # Test avec differents prix
    test_prices = [0.45, 0.50, 0.52, 0.53, 0.535, 0.54, 0.55, 0.60]

    print("\nTests de validation:")
    for price in test_prices:
        result = validator.validate_trade(price, "BTC", "UP")
        status = "VALIDE" if result.is_valid else "BLOQUE"
        print(f"  Prix {price*100:.1f}% -> {status}")

    validator.log_stats()

    print("\n" + "=" * 60)
    print("TEST PARTIAL FILL MANAGER")
    print("=" * 60)

    # Test PartialFillManager
    fill_manager = PartialFillManager()

    # Simuler des fills
    fill_manager.record_fill("order1", 100.0, 100.0, 0.50)  # Full fill
    fill_manager.record_fill("order2", 100.0, 75.0, 0.48)   # 75% fill
    fill_manager.record_fill("order3", 100.0, 50.0, 0.52)   # 50% fill

    # Calculer PnL
    pnl1, _ = fill_manager.calculate_real_pnl("order1", 1.0, True)
    pnl2, _ = fill_manager.calculate_real_pnl("order2", 1.0, True)
    pnl3, _ = fill_manager.calculate_real_pnl("order3", 0.0, False)

    print(f"\nPnL order1 (full fill, win): ${pnl1:.2f}")
    print(f"PnL order2 (75% fill, win): ${pnl2:.2f}")
    print(f"PnL order3 (50% fill, loss): ${pnl3:.2f}")

    fill_manager.log_stats()

    print("\n" + "=" * 60)
    print("TEST DYNAMIC PRICE VALIDATOR")
    print("=" * 60)

    # Test DynamicPriceValidator
    dynamic_validator = DynamicPriceValidator(
        initial_win_rate=55.0,
        margin=2.0,
        min_trades_for_update=10
    )

    # Simuler des trades
    import random
    random.seed(42)

    for i in range(20):
        # Valider le trade
        price = 0.48 + random.random() * 0.10  # Prix entre 48% et 58%
        validation = dynamic_validator.validate_trade(price, "BTC", "UP")

        # Simuler resultat (55% win rate)
        is_win = random.random() < 0.55
        dynamic_validator.record_trade_result(is_win)

    print(f"\nWR final: {dynamic_validator.get_current_win_rate():.1f}%")
    print(f"Prix max final: {dynamic_validator.get_max_price()*100:.1f}%")

    stats = dynamic_validator.get_stats()
    print(f"WR observe: {stats['observed_win_rate']:.1f}%")
    print(f"Trades: {stats['wins']}W / {stats['losses']}L")
