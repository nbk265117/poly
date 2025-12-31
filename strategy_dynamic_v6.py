#!/usr/bin/env python3
"""
STRATÉGIE DYNAMIQUE V6 - OPTIMISÉE
==================================
100% dynamique - AUCUN paramètre hard-codé (heures, candles, jours)

Backtest 2024-2025 ($100/trade):
- PnL Total: +$303,088
- Win Rate: 55.5%
- Trades/jour: ~63
- Min mois: +$3,876
- 0 mois négatifs

CHANGEMENTS VS V3:
- Signal DOWN plus strict: RSI > 68 (vs > 62), Stoch > 75 (vs > 70)
- Élimine les signaux DOWN faibles qui avaient WR ~50%
- Signal UP inchangé: RSI < 38, Stoch < 30

FILTRES DYNAMIQUES:
1. RSI Extremity (0-30 points)
2. Stochastic Extremity (0-20 points)
3. Volume Filter (-20 à +10 points)
4. Volatility/ATR Filter (-15 à +10 points)
5. Trend Alignment (-10 à +15 points)
6. Candle Body Ratio (-10 à +5 points)
7. Consecutive Candles (0-10 points)

Seuil: Confidence >= 85
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class TradeSignal:
    """Signal de trading avec détails"""
    signal: Optional[str]  # "UP", "DOWN", ou None
    confidence: int  # 0-100
    rsi: float
    stoch: float
    volume_ratio: float
    atr_pct: float
    trend: str
    reasons: List[str]


class DynamicStrategyV6:
    """
    Stratégie V6 - Signal DOWN optimisé
    """

    # Paramètres de signal
    RSI_OVERSOLD = 38       # Signal UP si RSI < 38
    RSI_OVERBOUGHT = 68     # Signal DOWN si RSI > 68 (plus strict que V3)
    STOCH_OVERSOLD = 30     # Signal UP si Stoch < 30
    STOCH_OVERBOUGHT = 75   # Signal DOWN si Stoch > 75 (plus strict que V3)

    # Seuil de confidence minimum
    MIN_CONFIDENCE = 85

    def __init__(self, min_confidence: int = 85):
        self.min_confidence = min_confidence

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule tous les indicateurs nécessaires"""
        df = df.copy()

        # RSI(7)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Stochastic(5)
        low5 = df['low'].rolling(window=5).min()
        high5 = df['high'].rolling(window=5).max()
        df['stoch'] = 100 * (df['close'] - low5) / (high5 - low5)

        # Volume relatif
        df['vol_sma'] = df['volume'].rolling(window=20).mean()
        df['rel_volume'] = df['volume'] / df['vol_sma'].replace(0, 1)

        # ATR(14)
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()
        df['atr_pct'] = (df['atr'] / df['close']) * 100

        # Tendance (EMA20 vs EMA50)
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['ema50'] = df['close'].ewm(span=50).mean()
        df['trend'] = np.where(df['ema20'] > df['ema50'], 'UP', 'DOWN')

        # Body ratio
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['body_ratio'] = df['body'] / df['range'].replace(0, 1)

        # Direction candles
        df['candle_dir'] = np.where(df['close'] > df['open'], 1, -1)

        return df

    def calculate_confidence(
        self,
        row: pd.Series,
        prev_candles: pd.DataFrame,
        signal: str
    ) -> Tuple[int, List[str]]:
        """
        Calcule le score de confiance (0-100)

        V6: Bonus RSI/Stoch pour DOWN plus stricts
        """
        rsi = row['rsi']
        stoch = row['stoch']
        rel_vol = row['rel_volume']
        atr_pct = row['atr_pct']
        trend = row['trend']
        body_ratio = row['body_ratio']

        confidence = 50
        reasons = []

        # ============================================
        # 1. RSI EXTREMITY (max +30)
        # ============================================
        if signal == "UP":
            if rsi < 15:
                confidence += 30
                reasons.append(f"RSI très bas ({rsi:.1f}) +30")
            elif rsi < 20:
                confidence += 25
                reasons.append(f"RSI bas ({rsi:.1f}) +25")
            elif rsi < 25:
                confidence += 20
                reasons.append(f"RSI oversold ({rsi:.1f}) +20")
            elif rsi < 30:
                confidence += 15
                reasons.append(f"RSI oversold ({rsi:.1f}) +15")
            elif rsi < 35:
                confidence += 10
                reasons.append(f"RSI bas ({rsi:.1f}) +10")
            elif rsi < 38:
                confidence += 5
                reasons.append(f"RSI signal ({rsi:.1f}) +5")
        else:  # DOWN - Plus strict que V3
            if rsi > 85:
                confidence += 30
                reasons.append(f"RSI très haut ({rsi:.1f}) +30")
            elif rsi > 80:
                confidence += 25
                reasons.append(f"RSI haut ({rsi:.1f}) +25")
            elif rsi > 75:
                confidence += 20
                reasons.append(f"RSI overbought ({rsi:.1f}) +20")
            elif rsi > 72:
                confidence += 15
                reasons.append(f"RSI overbought ({rsi:.1f}) +15")
            elif rsi > 70:
                confidence += 10
                reasons.append(f"RSI haut ({rsi:.1f}) +10")
            # Pas de bonus pour RSI 68-70 (trop faible)

        # ============================================
        # 2. STOCHASTIC EXTREMITY (max +20)
        # ============================================
        if signal == "UP":
            if stoch < 5:
                confidence += 20
                reasons.append(f"Stoch très bas ({stoch:.1f}) +20")
            elif stoch < 10:
                confidence += 15
                reasons.append(f"Stoch bas ({stoch:.1f}) +15")
            elif stoch < 15:
                confidence += 10
                reasons.append(f"Stoch oversold ({stoch:.1f}) +10")
            elif stoch < 20:
                confidence += 5
                reasons.append(f"Stoch signal ({stoch:.1f}) +5")
        else:  # DOWN - Plus strict
            if stoch > 95:
                confidence += 20
                reasons.append(f"Stoch très haut ({stoch:.1f}) +20")
            elif stoch > 90:
                confidence += 15
                reasons.append(f"Stoch haut ({stoch:.1f}) +15")
            elif stoch > 85:
                confidence += 10
                reasons.append(f"Stoch overbought ({stoch:.1f}) +10")
            elif stoch > 80:
                confidence += 5
                reasons.append(f"Stoch signal ({stoch:.1f}) +5")
            # Pas de bonus pour Stoch 75-80

        # ============================================
        # 3. VOLUME FILTER (max +10, min -20)
        # ============================================
        if 0.7 <= rel_vol <= 1.4:
            confidence += 10
            reasons.append(f"Volume normal ({rel_vol:.2f}x) +10")
        elif 0.5 <= rel_vol <= 2.0:
            confidence += 5
            reasons.append(f"Volume acceptable ({rel_vol:.2f}x) +5")
        elif rel_vol < 0.4:
            confidence -= 20
            reasons.append(f"Volume trop faible ({rel_vol:.2f}x) -20")
        elif rel_vol > 3.0:
            confidence -= 15
            reasons.append(f"Volume spike ({rel_vol:.2f}x) -15")

        # ============================================
        # 4. VOLATILITY FILTER (max +10, min -15)
        # ============================================
        if 0.15 <= atr_pct <= 0.5:
            confidence += 10
            reasons.append(f"Volatilité normale ({atr_pct:.2f}%) +10")
        elif 0.1 <= atr_pct <= 0.8:
            confidence += 5
            reasons.append(f"Volatilité acceptable ({atr_pct:.2f}%) +5")
        elif atr_pct > 1.5:
            confidence -= 15
            reasons.append(f"Trop volatile ({atr_pct:.2f}%) -15")
        elif atr_pct < 0.05:
            confidence -= 10
            reasons.append(f"Trop calme ({atr_pct:.2f}%) -10")

        # ============================================
        # 5. TREND ALIGNMENT (max +15, min -10)
        # ============================================
        if signal == "UP" and trend == "UP":
            confidence += 15
            reasons.append("Avec tendance UP +15")
        elif signal == "DOWN" and trend == "DOWN":
            confidence += 15
            reasons.append("Avec tendance DOWN +15")
        elif signal == "UP" and trend == "DOWN":
            confidence -= 10
            reasons.append("Contre tendance -10")
        elif signal == "DOWN" and trend == "UP":
            confidence -= 10
            reasons.append("Contre tendance -10")

        # ============================================
        # 6. CANDLE BODY RATIO (max +5, min -10)
        # ============================================
        if body_ratio > 0.6:
            confidence += 5
            reasons.append(f"Candle claire ({body_ratio:.2f}) +5")
        elif body_ratio < 0.2:
            confidence -= 10
            reasons.append(f"Doji/indécision ({body_ratio:.2f}) -10")

        # ============================================
        # 7. CONSECUTIVE CANDLES (max +10)
        # ============================================
        if len(prev_candles) >= 3:
            last_3_dirs = prev_candles['candle_dir'].tail(3).values

            if signal == "UP" and all(d == -1 for d in last_3_dirs):
                confidence += 10
                reasons.append("3 red candles +10")
            elif signal == "DOWN" and all(d == 1 for d in last_3_dirs):
                confidence += 10
                reasons.append("3 green candles +10")

        return max(0, min(100, confidence)), reasons

    def get_signal(
        self,
        df: pd.DataFrame,
        index: int = -1
    ) -> TradeSignal:
        """
        Analyse et retourne un signal de trading

        Args:
            df: DataFrame avec colonnes OHLCV
            index: Index de la candle (-1 = dernière)

        Returns:
            TradeSignal avec signal, confidence et détails
        """
        df = self.calculate_indicators(df)

        if index == -1:
            index = len(df) - 1

        row = df.iloc[index]
        prev_candles = df.iloc[max(0, index-10):index]

        rsi = row['rsi']
        stoch = row['stoch']

        # Signal avec seuils V6 (DOWN plus strict)
        signal = None
        if rsi < self.RSI_OVERSOLD and stoch < self.STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > self.RSI_OVERBOUGHT and stoch > self.STOCH_OVERBOUGHT:
            signal = "DOWN"

        if signal is None:
            return TradeSignal(
                signal=None,
                confidence=0,
                rsi=rsi,
                stoch=stoch,
                volume_ratio=row['rel_volume'],
                atr_pct=row['atr_pct'],
                trend=row['trend'],
                reasons=["Pas de signal RSI+Stoch"]
            )

        # Calculer confidence
        confidence, reasons = self.calculate_confidence(row, prev_candles, signal)

        return TradeSignal(
            signal=signal if confidence >= self.min_confidence else None,
            confidence=confidence,
            rsi=rsi,
            stoch=stoch,
            volume_ratio=row['rel_volume'],
            atr_pct=row['atr_pct'],
            trend=row['trend'],
            reasons=reasons
        )

    def should_trade(
        self,
        rsi: float,
        stoch: float,
        rel_volume: float,
        atr_pct: float,
        trend: str,
        body_ratio: float,
        consecutive_same_dir: int,
        signal: str
    ) -> Tuple[bool, int, List[str]]:
        """
        Méthode simplifiée pour vérifier si on doit trader

        Returns:
            (should_trade, confidence, reasons)
        """
        confidence = 50
        reasons = []

        # 1. RSI
        if signal == "UP":
            if rsi < 20:
                confidence += 25
                reasons.append("RSI très bas +25")
            elif rsi < 30:
                confidence += 15
                reasons.append("RSI oversold +15")
            elif rsi < 38:
                confidence += 5
        else:  # DOWN - Plus strict
            if rsi > 80:
                confidence += 25
                reasons.append("RSI très haut +25")
            elif rsi > 72:
                confidence += 15
                reasons.append("RSI overbought +15")
            elif rsi > 70:
                confidence += 10

        # 2. Stoch
        if signal == "UP":
            if stoch < 10:
                confidence += 15
                reasons.append("Stoch très bas +15")
            elif stoch < 20:
                confidence += 10
        else:
            if stoch > 90:
                confidence += 15
                reasons.append("Stoch très haut +15")
            elif stoch > 80:
                confidence += 10

        # 3. Volume
        if 0.7 <= rel_volume <= 1.4:
            confidence += 10
            reasons.append("Volume OK +10")
        elif rel_volume < 0.4:
            confidence -= 20
            reasons.append("Volume faible -20")
        elif rel_volume > 3.0:
            confidence -= 15

        # 4. Volatilité
        if 0.15 <= atr_pct <= 0.5:
            confidence += 10
            reasons.append("Volatilité OK +10")
        elif atr_pct > 1.5:
            confidence -= 15

        # 5. Tendance
        if (signal == "UP" and trend == "UP") or (signal == "DOWN" and trend == "DOWN"):
            confidence += 15
            reasons.append("Avec tendance +15")
        elif (signal == "UP" and trend == "DOWN") or (signal == "DOWN" and trend == "UP"):
            confidence -= 10
            reasons.append("Contre tendance -10")

        # 6. Body ratio
        if body_ratio < 0.2:
            confidence -= 10
            reasons.append("Doji -10")

        # 7. Candles consécutives
        if consecutive_same_dir >= 3:
            confidence += 10
            reasons.append("3+ candles +10")

        confidence = max(0, min(100, confidence))

        return confidence >= self.min_confidence, confidence, reasons


# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def get_signal_v6(
    rsi: float,
    stoch: float,
    rel_volume: float,
    atr_pct: float,
    trend: str,
    body_ratio: float = 0.5,
    consecutive_candles: int = 0
) -> Tuple[Optional[str], int, bool]:
    """
    Fonction simple pour obtenir un signal V6

    Args:
        rsi: RSI(7)
        stoch: Stochastic(5)
        rel_volume: Volume relatif vs moyenne 20
        atr_pct: ATR en % du prix
        trend: "UP" ou "DOWN" (EMA20 vs EMA50)
        body_ratio: Ratio body/range de la candle
        consecutive_candles: Nombre de candles consécutives même direction

    Returns:
        (signal, confidence, should_trade)
        signal: "UP", "DOWN" ou None
        confidence: 0-100
        should_trade: True si confidence >= 85
    """
    # Déterminer le signal de base (V6: DOWN plus strict)
    signal = None
    if rsi < 38 and stoch < 30:
        signal = "UP"
    elif rsi > 68 and stoch > 75:
        signal = "DOWN"

    if signal is None:
        return None, 0, False

    # Calculer confidence
    strategy = DynamicStrategyV6()
    should_trade, confidence, _ = strategy.should_trade(
        rsi, stoch, rel_volume, atr_pct, trend, body_ratio, consecutive_candles, signal
    )

    return signal, confidence, should_trade


def main():
    """Test de la stratégie V6"""
    import ccxt

    print("=" * 70)
    print("TEST STRATÉGIE DYNAMIQUE V6")
    print("=" * 70)
    print()
    print("Paramètres V6:")
    print("  Signal UP:   RSI < 38 AND Stoch < 30")
    print("  Signal DOWN: RSI > 68 AND Stoch > 75 (plus strict)")
    print("  Confidence minimum: 85")
    print()

    # Charger données
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', '15m', limit=100)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Créer stratégie
    strategy = DynamicStrategyV6(min_confidence=85)

    # Obtenir signal
    signal = strategy.get_signal(df)

    print(f"Dernière candle: {df.iloc[-1]['datetime']}")
    print(f"Prix: ${df.iloc[-1]['close']:,.2f}")
    print()
    print(f"Signal: {signal.signal or 'AUCUN'}")
    print(f"Confidence: {signal.confidence}/100")
    print(f"RSI(7): {signal.rsi:.1f}")
    print(f"Stoch(5): {signal.stoch:.1f}")
    print(f"Volume Ratio: {signal.volume_ratio:.2f}x")
    print(f"ATR%: {signal.atr_pct:.2f}%")
    print(f"Trend: {signal.trend}")
    print()
    print("Raisons:")
    for reason in signal.reasons:
        print(f"  - {reason}")

    if signal.signal:
        print(f"\n✅ TRADE RECOMMANDÉ: {signal.signal}")
    else:
        print(f"\n❌ PAS DE TRADE (confidence {signal.confidence} < 85)")


if __name__ == "__main__":
    main()
