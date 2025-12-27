#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stratégie Mean Reversion pour Polymarket
Objectif : Win Rate > 55% avec 20+ trades/jour

RÈGLES DE TRADING :
1. Signal UP : 3+ bougies DOWN consécutives OU RSI < 30
2. Signal DOWN : 3+ bougies UP consécutives OU RSI > 70

Indicateurs :
- Direction des bougies (consécutives)
- RSI(14)
- [Optionnel] Momentum pour confirmation

BLACKLIST HEURES (optimisées par backtest 2024-2025) :
- BTC: 04, 05, 07, 15, 16, 17, 18, 19h UTC
- ETH: 00, 07, 15, 16, 17, 19h UTC
- XRP: 00, 04, 07, 08, 16, 18, 19h UTC
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Set
import logging

logger = logging.getLogger(__name__)

# Blacklists d'heures optimisées par actif (heures UTC avec WR < 54%)
HOUR_BLACKLIST = {
    'BTC': {4, 5, 7, 15, 16, 17, 18, 19},
    'ETH': {0, 7, 15, 16, 17, 19},
    'XRP': {0, 4, 7, 8, 16, 18, 19},
    'DEFAULT': {7, 16, 19},  # Heures communes problématiques
}


class MeanReversionStrategy:
    """
    Stratégie de Mean Reversion pour Polymarket Up/Down 15 minutes
    """

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
        consec_threshold: int = 3,
        use_momentum_filter: bool = True,
        symbol: str = None,
        blacklist_hours: Set[int] = None,
        use_hour_filter: bool = True
    ):
        """
        Args:
            rsi_period: Période du RSI (défaut 14)
            rsi_oversold: Seuil RSI survente (défaut 30)
            rsi_overbought: Seuil RSI surachat (défaut 70)
            consec_threshold: Nombre de bougies consécutives (défaut 3)
            use_momentum_filter: Utiliser le filtre momentum (défaut True)
            symbol: Symbole de l'actif (BTC, ETH, XRP) pour blacklist automatique
            blacklist_hours: Set d'heures à éviter (0-23 UTC), prioritaire sur symbol
            use_hour_filter: Activer le filtre d'heures (défaut True)
        """
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.consec_threshold = consec_threshold
        self.use_momentum_filter = use_momentum_filter
        self.use_hour_filter = use_hour_filter

        # Déterminer la blacklist d'heures
        if blacklist_hours is not None:
            self.blacklist_hours = set(blacklist_hours)
        elif symbol and symbol.upper() in HOUR_BLACKLIST:
            self.blacklist_hours = HOUR_BLACKLIST[symbol.upper()]
        else:
            self.blacklist_hours = HOUR_BLACKLIST['DEFAULT']

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule tous les indicateurs nécessaires

        Args:
            df: DataFrame avec colonnes OHLCV

        Returns:
            DataFrame enrichi avec les indicateurs
        """
        df = df.copy()

        # === Direction des bougies ===
        df['is_up'] = df['close'] > df['open']
        df['is_down'] = df['close'] < df['open']

        # === Bougies consécutives ===
        # Calcul du nombre de bougies DOWN consécutives
        df['consec_down'] = 0
        count = 0
        for i in range(len(df)):
            if df.iloc[i]['is_down']:
                count += 1
            else:
                count = 0
            df.iloc[i, df.columns.get_loc('consec_down')] = count

        # Calcul du nombre de bougies UP consécutives
        df['consec_up'] = 0
        count = 0
        for i in range(len(df)):
            if df.iloc[i]['is_up']:
                count += 1
            else:
                count = 0
            df.iloc[i, df.columns.get_loc('consec_up')] = count

        # === RSI ===
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # === Momentum (optionnel) ===
        if self.use_momentum_filter:
            df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

        return df

    def generate_signal(self, df: pd.DataFrame, idx: int = -1, hour: int = None) -> Optional[str]:
        """
        Génère un signal pour une bougie donnée

        Args:
            df: DataFrame avec indicateurs calculés
            idx: Index de la bougie (-1 = dernière)
            hour: Heure de la bougie (0-23 UTC) pour filtre blacklist

        Returns:
            'UP', 'DOWN', ou None
        """
        if len(df) < self.rsi_period + 5:
            return None

        row = df.iloc[idx]

        # Vérifier le filtre d'heures
        if self.use_hour_filter and hour is not None:
            if hour in self.blacklist_hours:
                return None

        # Vérifier que les indicateurs sont calculés
        if pd.isna(row.get('RSI', np.nan)):
            return None

        # === Conditions pour signal UP ===
        consec_down = row.get('consec_down', 0)
        rsi = row.get('RSI', 50)

        cond_up_consec = consec_down >= self.consec_threshold
        cond_up_rsi = rsi < self.rsi_oversold

        # === Conditions pour signal DOWN ===
        consec_up = row.get('consec_up', 0)

        cond_down_consec = consec_up >= self.consec_threshold
        cond_down_rsi = rsi > self.rsi_overbought

        # === Filtre momentum (optionnel) ===
        if self.use_momentum_filter:
            momentum = row.get('momentum', 0)

            # Pour UP : on veut un momentum négatif (confirme la survente)
            if cond_up_consec or cond_up_rsi:
                if momentum < 0:
                    return 'UP'

            # Pour DOWN : on veut un momentum positif (confirme le surachat)
            if cond_down_consec or cond_down_rsi:
                if momentum > 0:
                    return 'DOWN'
        else:
            # Sans filtre momentum
            if cond_up_consec or cond_up_rsi:
                return 'UP'

            if cond_down_consec or cond_down_rsi:
                return 'DOWN'

        return None

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyse complète avec génération de tous les signaux

        Args:
            df: DataFrame OHLCV brut

        Returns:
            DataFrame avec colonne 'signal'
        """
        df = self.calculate_indicators(df)

        # Extraire l'heure si timestamp disponible
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        else:
            df['hour'] = None

        # Générer signaux pour chaque ligne
        signals = []
        for i in range(len(df)):
            if i < self.rsi_period + 5:
                signals.append(None)
            else:
                hour = df.iloc[i]['hour'] if df.iloc[i]['hour'] is not None else None
                signals.append(self.generate_signal(df, i, hour=hour))

        df['signal'] = signals

        return df

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000,
        bet_size: float = 100,
        payout: float = 1.9
    ) -> dict:
        """
        Backtest de la stratégie en mode Polymarket

        Args:
            df: DataFrame OHLCV avec timestamps
            initial_capital: Capital initial
            bet_size: Taille de mise par trade
            payout: Payout Polymarket (1.9 = 90% de gain)

        Returns:
            Dict avec résultats du backtest
        """
        df = self.analyze(df.copy())

        # Calculer si le signal était correct
        df['next_close'] = df['close'].shift(-1)
        df['next_up'] = df['next_close'] > df['close']
        df['next_down'] = df['next_close'] < df['close']

        # Vérifier chaque signal
        df['correct'] = False
        df.loc[(df['signal'] == 'UP') & df['next_up'], 'correct'] = True
        df.loc[(df['signal'] == 'DOWN') & df['next_down'], 'correct'] = True

        # Filtrer les signaux actifs
        trades = df[df['signal'].isin(['UP', 'DOWN'])].copy()

        if len(trades) == 0:
            return {'error': 'Aucun trade généré'}

        # Calculer les statistiques
        total_trades = len(trades)
        wins = trades['correct'].sum()
        losses = total_trades - wins
        win_rate = wins / total_trades * 100

        # Calculer PnL (mode Polymarket)
        gain_per_win = bet_size * (payout - 1)  # 90$ si payout 1.9x
        loss_per_loss = bet_size

        total_gain = wins * gain_per_win
        total_loss = losses * loss_per_loss
        net_pnl = total_gain - total_loss

        final_capital = initial_capital + net_pnl
        total_return = (final_capital / initial_capital - 1) * 100

        # Trades par jour
        days = (df['timestamp'].max() - df['timestamp'].min()).days
        trades_per_day = total_trades / days if days > 0 else 0

        # Séparation UP/DOWN
        up_trades = trades[trades['signal'] == 'UP']
        down_trades = trades[trades['signal'] == 'DOWN']

        up_win_rate = up_trades['correct'].mean() * 100 if len(up_trades) > 0 else 0
        down_win_rate = down_trades['correct'].mean() * 100 if len(down_trades) > 0 else 0

        # Drawdown
        equity = [initial_capital]
        for _, trade in trades.iterrows():
            if trade['correct']:
                equity.append(equity[-1] + gain_per_win)
            else:
                equity.append(equity[-1] - loss_per_loss)

        equity = pd.Series(equity)
        peak = equity.cummax()
        drawdown = (equity - peak) / peak * 100
        max_drawdown = drawdown.min()

        return {
            'total_trades': total_trades,
            'wins': int(wins),
            'losses': int(losses),
            'win_rate': win_rate,
            'trades_per_day': trades_per_day,
            'up_trades': len(up_trades),
            'up_win_rate': up_win_rate,
            'down_trades': len(down_trades),
            'down_win_rate': down_win_rate,
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_pnl': net_pnl,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'profit_factor': total_gain / total_loss if total_loss > 0 else 0,
            'days': days
        }


def run_backtest():
    """Exécute le backtest et affiche les résultats"""
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print("=" * 80)
    print("BACKTEST STRATÉGIE MEAN REVERSION - POLYMARKET")
    print("=" * 80)

    # Charger les données
    df = pd.read_csv('/Users/mac/poly/data/historical/BTC_USDT_15m.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    print(f"\nDonnées : {len(df)} bougies")
    print(f"Période : {df['timestamp'].min()} à {df['timestamp'].max()}")

    # Créer la stratégie
    strategy = MeanReversionStrategy(
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        consec_threshold=3,
        use_momentum_filter=True
    )

    # Backtest
    print("\n" + "=" * 80)
    print("RÉSULTATS DU BACKTEST")
    print("=" * 80)

    results = strategy.backtest(df, initial_capital=10000, bet_size=100)

    print(f"\n📊 PERFORMANCE GLOBALE")
    print(f"   Trades totaux:        {results['total_trades']}")
    print(f"   Trades gagnants:      {results['wins']}")
    print(f"   Trades perdants:      {results['losses']}")
    print(f"   Win Rate:             {results['win_rate']:.2f}%")
    print(f"   Trades/jour:          {results['trades_per_day']:.1f}")

    print(f"\n📈 DÉTAILS PAR DIRECTION")
    print(f"   UP trades:  {results['up_trades']:>6} | Win Rate: {results['up_win_rate']:.1f}%")
    print(f"   DOWN trades:{results['down_trades']:>6} | Win Rate: {results['down_win_rate']:.1f}%")

    print(f"\n💰 RÉSULTATS FINANCIERS")
    print(f"   Capital initial:      ${results['initial_capital']:,.2f}")
    print(f"   Capital final:        ${results['final_capital']:,.2f}")
    print(f"   PnL total:            ${results['total_pnl']:+,.2f}")
    print(f"   Retour total:         {results['total_return']:+.2f}%")
    print(f"   Drawdown max:         {results['max_drawdown']:.2f}%")
    print(f"   Profit Factor:        {results['profit_factor']:.2f}")

    print("\n" + "=" * 80)

    # Vérification des objectifs
    objectives = []

    if results['win_rate'] >= 55:
        objectives.append(f"✅ Win Rate ≥ 55% ({results['win_rate']:.1f}%)")
    else:
        objectives.append(f"❌ Win Rate < 55% ({results['win_rate']:.1f}%)")

    if results['trades_per_day'] >= 20:
        objectives.append(f"✅ Trades/jour ≥ 20 ({results['trades_per_day']:.0f})")
    else:
        objectives.append(f"❌ Trades/jour < 20 ({results['trades_per_day']:.1f})")

    if results['total_return'] > 0:
        objectives.append(f"✅ Retour positif ({results['total_return']:+.2f}%)")
    else:
        objectives.append(f"❌ Retour négatif ({results['total_return']:.2f}%)")

    print("VÉRIFICATION DES OBJECTIFS :")
    for obj in objectives:
        print(f"   {obj}")

    print("\n" + "=" * 80)

    return results


if __name__ == "__main__":
    run_backtest()
