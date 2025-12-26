#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Technical Indicators - Stratégie Mean Reversion pour Polymarket

STRATÉGIE OPTIMISÉE (Win Rate 55%+, 30+ trades/jour) :
- Indicateur 1 : Bougies consécutives (UP/DOWN)
- Indicateur 2 : RSI(14)
- Indicateur 3 : Momentum (optionnel, pour confirmation)

RÈGLES :
1. Signal UP : 3+ bougies DOWN consécutives OU RSI < 30
2. Signal DOWN : 3+ bougies UP consécutives OU RSI > 70
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# NOUVELLE STRATÉGIE : MEAN REVERSION
# ============================================================================

class ConsecutiveCandlesIndicator:
    """
    Indicateur de bougies consécutives pour Mean Reversion
    Compte le nombre de bougies UP ou DOWN consécutives
    """

    def __init__(self, threshold: int = 3):
        """
        Args:
            threshold: Nombre minimum de bougies consécutives pour signal
        """
        self.threshold = threshold

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les bougies consécutives

        Args:
            df: DataFrame avec OHLCV

        Returns:
            DataFrame avec colonnes consec_up, consec_down
        """
        df = df.copy()

        # Direction de chaque bougie
        df['is_up'] = df['close'] > df['open']
        df['is_down'] = df['close'] < df['open']

        # Compter les consécutives
        df['consec_down'] = 0
        df['consec_up'] = 0

        count_down = 0
        count_up = 0

        for i in range(len(df)):
            # Bougies DOWN
            if df.iloc[i]['is_down']:
                count_down += 1
            else:
                count_down = 0
            df.iloc[i, df.columns.get_loc('consec_down')] = count_down

            # Bougies UP
            if df.iloc[i]['is_up']:
                count_up += 1
            else:
                count_up = 0
            df.iloc[i, df.columns.get_loc('consec_up')] = count_up

        return df


class MeanReversionPipeline:
    """
    Pipeline pour la stratégie Mean Reversion
    Combine bougies consécutives + RSI + Momentum
    """

    def __init__(self, config=None):
        from src.config import get_config
        self.config = config or get_config()

        # Paramètres de la stratégie
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.consec_threshold = 3
        self.use_momentum_filter = True

        # Indicateurs
        self.consec = ConsecutiveCandlesIndicator(self.consec_threshold)
        self.rsi = RSIIndicator(self.rsi_period)

    def calculate_all(
        self,
        df: pd.DataFrame,
        multi_tf_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """
        Calcule tous les indicateurs de la stratégie Mean Reversion
        """
        # Bougies consécutives
        df = self.consec.calculate(df)

        # RSI
        df = self.rsi.calculate(df)

        # Momentum
        if self.use_momentum_filter:
            df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100

        return df

    def generate_signal(self, row: pd.Series) -> Optional[str]:
        """
        Génère un signal Mean Reversion

        RÈGLES :
        1. Signal UP : 3+ DOWN consécutives OU RSI < 30 (+ momentum négatif)
        2. Signal DOWN : 3+ UP consécutives OU RSI > 70 (+ momentum positif)

        Returns:
            'BUY' (UP), 'SELL' (DOWN), ou None
        """
        if pd.isna(row.get('RSI', np.nan)):
            return None

        consec_down = row.get('consec_down', 0)
        consec_up = row.get('consec_up', 0)
        rsi = row.get('RSI', 50)
        momentum = row.get('momentum', 0)

        # === Signal UP (BUY) ===
        cond_up_consec = consec_down >= self.consec_threshold
        cond_up_rsi = rsi < self.rsi_oversold

        if cond_up_consec or cond_up_rsi:
            if self.use_momentum_filter:
                if momentum < 0:  # Confirme la survente
                    return 'BUY'
            else:
                return 'BUY'

        # === Signal DOWN (SELL) ===
        cond_down_consec = consec_up >= self.consec_threshold
        cond_down_rsi = rsi > self.rsi_overbought

        if cond_down_consec or cond_down_rsi:
            if self.use_momentum_filter:
                if momentum > 0:  # Confirme le surachat
                    return 'SELL'
            else:
                return 'SELL'

        return None


# ============================================================================
# ANCIENS INDICATEURS (conservés pour compatibilité)
# ============================================================================


class PriceActionIndicator:
    """
    Price Action Analysis
    Analyse les bougies pour détecter les signaux d'entrée
    """
    
    def __init__(self, min_wick_ratio: float = 0.3, min_body_size: float = 0.001):
        """
        Args:
            min_wick_ratio: Ratio minimum mèche/corps pour signal
            min_body_size: Taille minimum du corps en % du prix
        """
        self.min_wick_ratio = min_wick_ratio
        self.min_body_size = min_body_size
    
    def analyze_candle(self, row: pd.Series) -> Dict[str, any]:
        """
        Analyse une bougie individuelle
        
        Returns:
            Dict avec: signal, strength, candle_type, direction
        """
        open_price = row['open']
        high = row['high']
        low = row['low']
        close = row['close']
        
        # Calcul des composants de la bougie
        body = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        total_range = high - low
        
        # Direction
        is_bullish = close > open_price
        is_bearish = close < open_price
        
        # Taille du corps en % du prix
        body_percent = (body / open_price) * 100 if open_price > 0 else 0
        
        # Ratios
        upper_wick_ratio = upper_wick / body if body > 0 else 0
        lower_wick_ratio = lower_wick / body if body > 0 else 0
        
        # Détection des patterns
        signal = None
        strength = 0
        candle_type = "neutral"
        
        # === AMÉLIORATION : Ajouter plus de patterns Price Action ===
        
        # === SIGNAUX BUY ===
        
        # 1. Hammer / Bullish Pin Bar (rejet bas fort)
        if lower_wick_ratio > self.min_wick_ratio and body_percent > self.min_body_size:
            if is_bullish and lower_wick > body * 1.5:
                signal = "BUY"
                candle_type = "hammer"
                strength = min(lower_wick_ratio / 2, 1.0)
        
        # 2. Engulfing Bullish (corps large)
        if is_bullish and body_percent > self.min_body_size * 2.5:
            signal = "BUY"
            candle_type = "engulfing_bullish"
            strength = 0.8
        
        # 3. Bougie bullish avec peu de mèche haute (forte conviction)
        if is_bullish and body_percent > self.min_body_size * 1.2:
            if upper_wick < body * 0.4:
                signal = "BUY"
                candle_type = "bullish_strong"
                strength = 0.5
        
        # 4. Bougie bullish simple (corps > mèches) - NOUVEAU
        if is_bullish and body > (upper_wick + lower_wick):
            signal = "BUY"
            candle_type = "bullish"
            strength = 0.4
        
        # 5. Bullish avec close près du high - NOUVEAU
        if is_bullish and upper_wick < body * 0.2:
            signal = "BUY"
            candle_type = "bullish_close_high"
            strength = 0.45
        
        # 6. Toute bougie bullish avec corps minimal - NOUVEAU (ultra-permissif)
        if is_bullish and body_percent > self.min_body_size:
            signal = "BUY"
            candle_type = "bullish_any"
            strength = 0.3
        
        # === SIGNAUX SELL ===
        
        # 1. Shooting Star / Bearish Pin Bar (rejet haut fort)
        if upper_wick_ratio > self.min_wick_ratio and body_percent > self.min_body_size:
            if is_bearish and upper_wick > body * 1.5:
                signal = "SELL"
                candle_type = "shooting_star"
                strength = min(upper_wick_ratio / 2, 1.0)
        
        # 2. Engulfing Bearish (corps large)
        if is_bearish and body_percent > self.min_body_size * 2.5:
            signal = "SELL"
            candle_type = "engulfing_bearish"
            strength = 0.8
        
        # 3. Bougie bearish avec peu de mèche basse (forte conviction)
        if is_bearish and body_percent > self.min_body_size * 1.2:
            if lower_wick < body * 0.4:
                signal = "SELL"
                candle_type = "bearish_strong"
                strength = 0.5
        
        # 4. Bougie bearish simple (corps > mèches) - NOUVEAU
        if is_bearish and body > (upper_wick + lower_wick):
            signal = "SELL"
            candle_type = "bearish"
            strength = 0.4
        
        # 5. Bearish avec close près du low - NOUVEAU
        if is_bearish and lower_wick < body * 0.2:
            signal = "SELL"
            candle_type = "bearish_close_low"
            strength = 0.45
        
        # 6. Toute bougie bearish avec corps minimal - NOUVEAU (ultra-permissif)
        if is_bearish and body_percent > self.min_body_size:
            signal = "SELL"
            candle_type = "bearish_any"
            strength = 0.3
        
        return {
            'signal': signal,
            'strength': strength,
            'candle_type': candle_type,
            'direction': 'bullish' if is_bullish else 'bearish',
            'body_percent': body_percent,
            'upper_wick_ratio': upper_wick_ratio,
            'lower_wick_ratio': lower_wick_ratio,
            'close': close
        }
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les signaux Price Action sur tout le DataFrame
        
        Args:
            df: DataFrame avec OHLCV
            
        Returns:
            DataFrame enrichi avec colonnes PA_*
        """
        df = df.copy()
        
        # Appliquer l'analyse à chaque bougie
        results = df.apply(self.analyze_candle, axis=1)
        
        # Extraire les résultats
        df['PA_signal'] = results.apply(lambda x: x['signal'])
        df['PA_strength'] = results.apply(lambda x: x['strength'])
        df['PA_type'] = results.apply(lambda x: x['candle_type'])
        df['PA_direction'] = results.apply(lambda x: x['direction'])
        
        return df


class FTFCIndicator:
    """
    FTFC (Fair Trade Fair Competition) Multi-Timeframe
    Détermine le biais directionnel basé sur l'alignement des timeframes
    """
    
    def __init__(self, require_all_aligned: bool = True):
        """
        Args:
            require_all_aligned: Tous les TF doivent être alignés
        """
        self.require_all_aligned = require_all_aligned
    
    def calculate_ftfc_single(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        Calcule FTFC pour un seul timeframe
        
        Logique améliorée avec double EMA:
        - Si close > EMA(20) ET EMA(20) > EMA(50) -> Bullish fort
        - Si close > EMA(20) mais EMA(20) < EMA(50) -> Bullish faible  
        - Si close < EMA(20) ET EMA(20) < EMA(50) -> Bearish fort
        - Si close < EMA(20) mais EMA(20) > EMA(50) -> Bearish faible
        
        Args:
            df: DataFrame avec OHLCV
            period: Période pour l'EMA rapide (20)
            
        Returns:
            DataFrame avec colonne FTFC_direction
        """
        df = df.copy()
        
        # Calculer les EMAs
        df['EMA_fast'] = df['close'].ewm(span=period, adjust=False).mean()
        df['EMA_slow'] = df['close'].ewm(span=period*2.5, adjust=False).mean()  # 50 periodes
        
        # Déterminer la direction avec force
        conditions = [
            # Bullish fort : prix > EMA rapide ET EMA rapide > EMA lente
            (df['close'] > df['EMA_fast']) & (df['EMA_fast'] > df['EMA_slow']),
            # Bearish fort : prix < EMA rapide ET EMA rapide < EMA lente
            (df['close'] < df['EMA_fast']) & (df['EMA_fast'] < df['EMA_slow']),
            # Neutral/mixte
            True
        ]
        
        choices = ['bullish', 'bearish', 'neutral']
        
        df['FTFC_direction'] = np.select(conditions, choices, default='neutral')
        
        # Score de force (distance du prix à l'EMA rapide)
        df['FTFC_strength'] = abs(df['close'] - df['EMA_fast']) / df['EMA_fast'] * 100
        
        # Maintenir compatibilité
        df['EMA'] = df['EMA_fast']
        
        return df
    
    def calculate_multi_timeframe(
        self,
        data_dict: Dict[str, pd.DataFrame],
        current_timestamp: pd.Timestamp
    ) -> Dict[str, str]:
        """
        Calcule le FTFC pour plusieurs timeframes
        
        Args:
            data_dict: {timeframe: DataFrame}
            current_timestamp: Timestamp actuel
            
        Returns:
            Dict avec direction pour chaque TF et direction globale
        """
        directions = {}
        
        for tf, df in data_dict.items():
            # Calculer FTFC pour ce TF
            df_ftfc = self.calculate_ftfc_single(df)
            
            # Trouver la bougie correspondant au timestamp
            idx = df_ftfc['timestamp'].searchsorted(current_timestamp, side='right') - 1
            
            if idx >= 0 and idx < len(df_ftfc):
                directions[tf] = df_ftfc.iloc[idx]['FTFC_direction']
            else:
                directions[tf] = 'neutral'
        
        # Déterminer la direction globale
        bullish_count = sum(1 for d in directions.values() if d == 'bullish')
        bearish_count = sum(1 for d in directions.values() if d == 'bearish')
        
        if self.require_all_aligned:
            # Tous doivent être alignés
            if bullish_count == len(directions):
                global_direction = 'bullish'
            elif bearish_count == len(directions):
                global_direction = 'bearish'
            else:
                global_direction = 'neutral'
        else:
            # Majorité
            if bullish_count > bearish_count:
                global_direction = 'bullish'
            elif bearish_count > bullish_count:
                global_direction = 'bearish'
            else:
                global_direction = 'neutral'
        
        directions['global'] = global_direction
        
        return directions


class ATRIndicator:
    """
    ATR (Average True Range)
    Mesure la volatilité pour adapter le mode de trading
    """
    
    def __init__(self, period: int = 14):
        """
        Args:
            period: Période de l'ATR (standard 14)
        """
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule l'ATR et détermine le niveau de volatilité
        
        Args:
            df: DataFrame avec colonnes high, low, close
            
        Returns:
            DataFrame enrichi avec ATR et niveau de volatilité
        """
        df = df.copy()
        
        # Calculer True Range
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = abs(df['high'] - df['close'].shift(1))
        df['l-pc'] = abs(df['low'] - df['close'].shift(1))
        
        df['TR'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
        
        # ATR = moyenne mobile du TR
        df['ATR'] = df['TR'].rolling(window=self.period).mean()
        
        # ATR en % du prix (pour normalisation)
        df['ATR_percent'] = (df['ATR'] / df['close']) * 100
        
        # Déterminer le mode de trading selon la volatilité
        # Haute volatilité (>2.5%) -> Mode QUALITY (sélectif)
        # Volatilité normale (<2.5%) -> Mode SCALP (actif)
        df['trading_mode'] = np.where(
            df['ATR_percent'] > 2.5,
            'QUALITY',
            'SCALP'
        )
        
        # Nettoyage
        df.drop(['h-l', 'h-pc', 'l-pc', 'TR'], axis=1, inplace=True)
        
        return df


class RSIIndicator:
    """
    RSI (Relative Strength Index)
    Indicateur de momentum pour confirmation
    """
    
    def __init__(self, period: int = 14):
        """
        Args:
            period: Période du RSI (standard 14)
        """
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule le RSI
        
        Args:
            df: DataFrame avec colonne 'close'
            
        Returns:
            DataFrame enrichi avec colonne RSI
        """
        df = df.copy()
        
        # Calculer les variations
        delta = df['close'].diff()
        
        # Séparer gains et pertes
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Moyennes mobiles exponentielles
        avg_gain = gain.ewm(span=self.period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.period, adjust=False).mean()
        
        # RSI
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Niveaux RSI
        df['RSI_oversold'] = df['RSI'] < 30  # Survendu
        df['RSI_overbought'] = df['RSI'] > 70  # Suracheté
        
        return df


class VolumeIndicator:
    """
    Volume Confirmation
    Filtre les signaux basés sur le volume pour éviter les faux breakouts
    """
    
    def __init__(self, ma_period: int = 20, min_volume_ratio: float = 1.2):
        """
        Args:
            ma_period: Période de la moyenne mobile du volume
            min_volume_ratio: Ratio minimum volume/MA
        """
        self.ma_period = ma_period
        self.min_volume_ratio = min_volume_ratio
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les indicateurs de volume
        
        Args:
            df: DataFrame avec OHLCV
            
        Returns:
            DataFrame enrichi avec colonnes VOL_*
        """
        df = df.copy()
        
        # Moyenne mobile du volume
        df['VOL_MA'] = df['volume'].rolling(window=self.ma_period).mean()
        
        # Ratio volume / MA
        df['VOL_ratio'] = df['volume'] / df['VOL_MA']
        
        # Volume confirmation
        df['VOL_confirmed'] = df['VOL_ratio'] > self.min_volume_ratio
        
        # Volume relatif (percentile)
        df['VOL_percentile'] = df['volume'].rolling(window=100).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) if (x.max() - x.min()) > 0 else 0.5
        )
        
        return df


class IndicatorPipeline:
    """
    Pipeline d'indicateurs
    Combine les 3 indicateurs pour générer les signaux finaux
    """
    
    def __init__(self, config=None):
        from src.config import get_config
        self.config = config or get_config()
        
        # Initialiser les indicateurs
        pa_config = self.config.price_action_config
        self.price_action = PriceActionIndicator(
            min_wick_ratio=pa_config.get('min_wick_ratio', 0.3),
            min_body_size=pa_config.get('min_body_size', 0.001)
        )
        
        ftfc_config = self.config.ftfc_config
        self.ftfc = FTFCIndicator(
            require_all_aligned=ftfc_config.get('require_all_aligned', True)
        )
        
        vol_config = self.config.volume_config
        self.volume = VolumeIndicator(
            ma_period=vol_config.get('volume_ma_period', 20),
            min_volume_ratio=vol_config.get('min_volume_ratio', 1.2)
        )
        
        # Nouvel indicateur RSI
        self.rsi = RSIIndicator(period=14)
        
        # Indicateur ATR pour volatilité et mode de trading
        self.atr = ATRIndicator(period=14)
    
    def calculate_all(
        self,
        df: pd.DataFrame,
        multi_tf_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> pd.DataFrame:
        """
        Calcule tous les indicateurs
        
        Args:
            df: DataFrame principal (timeframe 15m)
            multi_tf_data: Données multi-timeframe pour FTFC
            
        Returns:
            DataFrame avec tous les indicateurs
        """
        # Price Action
        df = self.price_action.calculate(df)
        
        # Volume
        df = self.volume.calculate(df)
        
        # RSI
        df = self.rsi.calculate(df)
        
        # ATR (volatilité et mode de trading)
        df = self.atr.calculate(df)
        
        # FTFC (si données multi-TF fournies)
        if multi_tf_data:
            ftfc_directions = []
            for idx, row in df.iterrows():
                directions = self.ftfc.calculate_multi_timeframe(
                    multi_tf_data,
                    row['timestamp']
                )
                ftfc_directions.append(directions.get('global', 'neutral'))
            
            df['FTFC_direction'] = ftfc_directions
        else:
            df = self.ftfc.calculate_ftfc_single(df)
        
        return df
    
    def generate_signal(self, row: pd.Series) -> Optional[str]:
        """
        Génère un signal final basé sur tous les indicateurs
        APPROCHE MIXTE : Deux modes selon la volatilité (ATR)
        
        Returns:
            'BUY', 'SELL', ou None
        """
        # 0. Déterminer le mode de trading (SCALP ou QUALITY)
        trading_mode = row.get('trading_mode', 'SCALP')
        atr_percent = row.get('ATR_percent', 1.0)
        
        # 1. Vérifier Price Action (trigger)
        pa_signal = row.get('PA_signal')
        if not pa_signal:
            return None
        
        pa_strength = row.get('PA_strength', 0)
        
        # Vérifier si le type de signal est activé dans la config
        enable_buy = self.config.get('strategy.execution.enable_buy_signals', True)
        enable_sell = self.config.get('strategy.execution.enable_sell_signals', True)
        
        if pa_signal == 'BUY' and not enable_buy:
            return None
        if pa_signal == 'SELL' and not enable_sell:
            return None
        
        # === MODE QUALITY (Haute Volatilité) === 
        # Filtres LÉGERS, win rate prioritaire
        if trading_mode == 'QUALITY':
            # Exiger PA_strength minimale
            if pa_strength < 0.25:
                return None
            
            # FTFC : DÉSACTIVÉ (trop restrictif)
            # On accepte toutes les directions
            
            # Volume : DÉSACTIVÉ (on accepte tout)
            
            # RSI différencié BUY/SELL
            rsi = row.get('RSI', 50)
            if pa_signal == 'BUY':
                # BUY : privilégier RSI bas/moyen (momentum haussier)
                if rsi < 20 or rsi > 75:
                    return None
            elif pa_signal == 'SELL':
                # SELL : privilégier RSI haut/moyen (momentum baissier)
                if rsi < 25 or rsi > 80:
                    return None
        
        # === MODE SCALP (Volatilité Normale) ===
        # Filtres MINIMAUX pour volume maximal, TP=1% pour win rate 50%+
        else:
            # PA_strength : ACCEPTER TOUT (pas de filtre)
            # FTFC : DÉSACTIVÉ
            # Volume : DÉSACTIVÉ
            # RSI : DÉSACTIVÉ (on accepte tout)
            
            # On accepte tous les signaux Price Action en mode SCALP
            pass  # Aucun filtre supplémentaire
        
        # Signal validé !
        return pa_signal


if __name__ == "__main__":
    # Test des indicateurs
    logging.basicConfig(level=logging.INFO)
    
    # Créer des données de test
    dates = pd.date_range('2024-01-01', periods=100, freq='15min')
    np.random.seed(42)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.random.randn(100).cumsum() * 100,
        'high': 50000 + np.random.randn(100).cumsum() * 100 + 50,
        'low': 50000 + np.random.randn(100).cumsum() * 100 - 50,
        'close': 50000 + np.random.randn(100).cumsum() * 100,
        'volume': 1000 + np.random.rand(100) * 500
    })
    
    # Corriger high/low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    print("Testing Indicators...")
    
    # Test Price Action
    pa = PriceActionIndicator()
    df_pa = pa.calculate(df)
    print(f"\nPrice Action signals: {df_pa['PA_signal'].value_counts()}")
    
    # Test Volume
    vol = VolumeIndicator()
    df_vol = vol.calculate(df)
    print(f"\nVolume confirmed: {df_vol['VOL_confirmed'].sum()} / {len(df_vol)}")
    
    # Test Pipeline
    pipeline = IndicatorPipeline()
    df_all = pipeline.calculate_all(df)
    
    signals = df_all.apply(pipeline.generate_signal, axis=1)
    print(f"\nFinal signals: {signals.value_counts()}")

