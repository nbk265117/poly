#!/usr/bin/env python3
"""
STRATEGIE DYNAMIQUE V7 - ICT ENHANCED
=====================================
100% dynamique avec indicateurs ICT (Inner Circle Trader)

Basé sur V6 + filtres ICT:
- Range Position (Premium/Discount zones)
- Signal UP optimal: Range < 30% (discount zone)
- Signal DOWN optimal: Range > 70% (premium zone)

Cible: $15,000+ PnL par mois
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class TradeSignalV7:
    """Signal de trading V7 avec ICT"""
    signal: Optional[str]
    confidence: int
    rsi: float
    stoch: float
    range_position: float  # ICT Premium/Discount (0-100)
    volume_ratio: float
    atr_pct: float
    trend: str
    reasons: List[str]


class DynamicStrategyV7:
    """
    Strategie V7 - V6 + ICT Range Position

    Signal DOWN optimise + Premium/Discount zones
    """

    # Parametres signal V6
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 68
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 75

    # ICT Range Position
    DISCOUNT_ZONE = 30   # Signal UP optimal si range < 30%
    PREMIUM_ZONE = 70    # Signal DOWN optimal si range > 70%
    RANGE_PERIOD = 50    # Periode pour calculer le range

    # Seuil confidence
    MIN_CONFIDENCE = 70  # Plus bas que V6 car on a le filtre ICT

    def __init__(self, min_confidence: int = 70, use_ict_filter: bool = True):
        self.min_confidence = min_confidence
        self.use_ict_filter = use_ict_filter

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule tous les indicateurs incluant ICT"""
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

        # ============================================
        # ICT INDICATORS
        # ============================================

        # Range Position (Premium/Discount Zone)
        df['range_high'] = df['high'].rolling(window=self.RANGE_PERIOD).max()
        df['range_low'] = df['low'].rolling(window=self.RANGE_PERIOD).min()
        df['range_position'] = ((df['close'] - df['range_low']) /
                                (df['range_high'] - df['range_low']).replace(0, 1) * 100)

        return df

    def calculate_confidence(
        self,
        row: pd.Series,
        prev_candles: pd.DataFrame,
        signal: str
    ) -> Tuple[int, List[str]]:
        """
        Score de confiance V7 avec ICT
        """
        rsi = row['rsi']
        stoch = row['stoch']
        rel_vol = row['rel_volume']
        atr_pct = row['atr_pct']
        trend = row['trend']
        body_ratio = row['body_ratio']
        range_pos = row['range_position']

        confidence = 50
        reasons = []

        # ============================================
        # 1. ICT RANGE POSITION (max +20, min -15)
        # ============================================
        if self.use_ict_filter:
            if signal == "UP":
                if range_pos < 15:
                    confidence += 20
                    reasons.append(f"Deep Discount ({range_pos:.0f}%) +20")
                elif range_pos < 30:
                    confidence += 15
                    reasons.append(f"Discount Zone ({range_pos:.0f}%) +15")
                elif range_pos < 40:
                    confidence += 10
                    reasons.append(f"Low Range ({range_pos:.0f}%) +10")
                elif range_pos > 70:
                    confidence -= 15
                    reasons.append(f"Premium Zone ({range_pos:.0f}%) -15")
            else:  # DOWN
                if range_pos > 85:
                    confidence += 20
                    reasons.append(f"Deep Premium ({range_pos:.0f}%) +20")
                elif range_pos > 70:
                    confidence += 15
                    reasons.append(f"Premium Zone ({range_pos:.0f}%) +15")
                elif range_pos > 60:
                    confidence += 10
                    reasons.append(f"High Range ({range_pos:.0f}%) +10")
                elif range_pos < 30:
                    confidence -= 15
                    reasons.append(f"Discount Zone ({range_pos:.0f}%) -15")

        # ============================================
        # 2. RSI EXTREMITY (max +25)
        # ============================================
        if signal == "UP":
            if rsi < 20:
                confidence += 25
                reasons.append(f"RSI tres bas ({rsi:.1f}) +25")
            elif rsi < 25:
                confidence += 20
                reasons.append(f"RSI oversold ({rsi:.1f}) +20")
            elif rsi < 30:
                confidence += 15
                reasons.append(f"RSI oversold ({rsi:.1f}) +15")
            elif rsi < 35:
                confidence += 10
                reasons.append(f"RSI bas ({rsi:.1f}) +10")
        else:  # DOWN
            if rsi > 80:
                confidence += 25
                reasons.append(f"RSI tres haut ({rsi:.1f}) +25")
            elif rsi > 75:
                confidence += 20
                reasons.append(f"RSI overbought ({rsi:.1f}) +20")
            elif rsi > 72:
                confidence += 15
                reasons.append(f"RSI overbought ({rsi:.1f}) +15")
            elif rsi > 70:
                confidence += 10
                reasons.append(f"RSI haut ({rsi:.1f}) +10")

        # ============================================
        # 3. STOCHASTIC EXTREMITY (max +15)
        # ============================================
        if signal == "UP":
            if stoch < 10:
                confidence += 15
                reasons.append(f"Stoch tres bas ({stoch:.1f}) +15")
            elif stoch < 20:
                confidence += 10
                reasons.append(f"Stoch oversold ({stoch:.1f}) +10")
        else:
            if stoch > 90:
                confidence += 15
                reasons.append(f"Stoch tres haut ({stoch:.1f}) +15")
            elif stoch > 80:
                confidence += 10
                reasons.append(f"Stoch overbought ({stoch:.1f}) +10")

        # ============================================
        # 4. VOLUME FILTER (max +10, min -15)
        # ============================================
        if 0.7 <= rel_vol <= 1.5:
            confidence += 10
            reasons.append(f"Volume OK ({rel_vol:.2f}x) +10")
        elif rel_vol < 0.4:
            confidence -= 15
            reasons.append(f"Volume faible ({rel_vol:.2f}x) -15")
        elif rel_vol > 3.0:
            confidence -= 10
            reasons.append(f"Volume spike ({rel_vol:.2f}x) -10")

        # ============================================
        # 5. TREND ALIGNMENT (max +10, min -5)
        # ============================================
        if (signal == "UP" and trend == "UP") or (signal == "DOWN" and trend == "DOWN"):
            confidence += 10
            reasons.append("Avec tendance +10")
        elif (signal == "UP" and trend == "DOWN") or (signal == "DOWN" and trend == "UP"):
            confidence -= 5
            reasons.append("Contre tendance -5")

        return max(0, min(100, confidence)), reasons

    def get_signal(
        self,
        df: pd.DataFrame,
        index: int = -1
    ) -> TradeSignalV7:
        """
        Analyse et retourne un signal V7
        """
        df = self.calculate_indicators(df)

        if index == -1:
            index = len(df) - 1

        row = df.iloc[index]
        prev_candles = df.iloc[max(0, index-10):index]

        rsi = row['rsi']
        stoch = row['stoch']
        range_pos = row['range_position']

        # Signal V6 (DOWN plus strict)
        signal = None
        if rsi < self.RSI_OVERSOLD and stoch < self.STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > self.RSI_OVERBOUGHT and stoch > self.STOCH_OVERBOUGHT:
            signal = "DOWN"

        if signal is None:
            return TradeSignalV7(
                signal=None,
                confidence=0,
                rsi=rsi,
                stoch=stoch,
                range_position=range_pos,
                volume_ratio=row['rel_volume'],
                atr_pct=row['atr_pct'],
                trend=row['trend'],
                reasons=["Pas de signal RSI+Stoch"]
            )

        # Calculer confidence V7
        confidence, reasons = self.calculate_confidence(row, prev_candles, signal)

        return TradeSignalV7(
            signal=signal if confidence >= self.min_confidence else None,
            confidence=confidence,
            rsi=rsi,
            stoch=stoch,
            range_position=range_pos,
            volume_ratio=row['rel_volume'],
            atr_pct=row['atr_pct'],
            trend=row['trend'],
            reasons=reasons
        )


# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def get_signal_v7(
    rsi: float,
    stoch: float,
    range_position: float,
    rel_volume: float = 1.0,
    atr_pct: float = 0.3,
    trend: str = "UP"
) -> Tuple[Optional[str], int, bool]:
    """
    Fonction simple pour signal V7

    Args:
        rsi: RSI(7)
        stoch: Stochastic(5)
        range_position: ICT Range Position (0-100)
        rel_volume: Volume relatif
        atr_pct: ATR en %
        trend: "UP" ou "DOWN"

    Returns:
        (signal, confidence, should_trade)
    """
    # Signal de base V6
    signal = None
    if rsi < 38 and stoch < 30:
        signal = "UP"
    elif rsi > 68 and stoch > 75:
        signal = "DOWN"

    if signal is None:
        return None, 0, False

    # Calculer confidence avec ICT
    confidence = 50

    # ICT Range Position
    if signal == "UP":
        if range_position < 30:
            confidence += 15
        elif range_position > 70:
            confidence -= 15
    else:
        if range_position > 70:
            confidence += 15
        elif range_position < 30:
            confidence -= 15

    # RSI extremity
    if signal == "UP" and rsi < 25:
        confidence += 20
    elif signal == "DOWN" and rsi > 75:
        confidence += 20
    elif signal == "UP" and rsi < 35:
        confidence += 10
    elif signal == "DOWN" and rsi > 70:
        confidence += 10

    # Volume
    if 0.7 <= rel_volume <= 1.5:
        confidence += 10
    elif rel_volume < 0.4:
        confidence -= 15

    # Trend
    if (signal == "UP" and trend == "UP") or (signal == "DOWN" and trend == "DOWN"):
        confidence += 10

    confidence = max(0, min(100, confidence))

    return signal, confidence, confidence >= 70


def main():
    """Test de la strategie V7"""
    import ccxt

    print("=" * 70)
    print("TEST STRATEGIE DYNAMIQUE V7 - ICT ENHANCED")
    print("=" * 70)
    print()
    print("Parametres V7:")
    print("  Signal UP:   RSI < 38 AND Stoch < 30")
    print("  Signal DOWN: RSI > 68 AND Stoch > 75")
    print("  ICT Filter:  Range Position (Premium/Discount)")
    print("  Confidence:  >= 70")
    print()

    # Charger donnees
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', '15m', limit=200)

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Creer strategie
    strategy = DynamicStrategyV7(min_confidence=70, use_ict_filter=True)

    # Obtenir signal
    signal = strategy.get_signal(df)

    print(f"Derniere candle: {df.iloc[-1]['datetime']}")
    print(f"Prix: ${df.iloc[-1]['close']:,.2f}")
    print()
    print(f"Signal: {signal.signal or 'AUCUN'}")
    print(f"Confidence: {signal.confidence}/100")
    print(f"RSI(7): {signal.rsi:.1f}")
    print(f"Stoch(5): {signal.stoch:.1f}")
    print(f"Range Position: {signal.range_position:.1f}%")
    print(f"Volume Ratio: {signal.volume_ratio:.2f}x")
    print(f"Trend: {signal.trend}")
    print()
    print("Raisons:")
    for reason in signal.reasons:
        print(f"  - {reason}")

    if signal.signal:
        print(f"\n TRADE RECOMMANDE: {signal.signal}")
    else:
        print(f"\n PAS DE TRADE (confidence {signal.confidence} < 70)")


if __name__ == "__main__":
    main()
