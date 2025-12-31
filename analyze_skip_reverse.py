#!/usr/bin/env python3
"""
ANALYSE: Trouver des indicateurs dynamiques pour remplacer SKIP/REVERSE

Objectif: Au lieu de hard-coder 235 SKIP + 12 REVERSE basés sur l'historique,
trouver des indicateurs qui détectent dynamiquement quand SKIP ou REVERSE.

Hypothèses:
- SKIP: Volume faible, volatilité anormale, faible liquidité
- REVERSE: Momentum fort, tendance en continuation
"""

import ccxt
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Les candles SKIP/REVERSE actuelles (pour comparaison)
REVERSE_CANDLES = {
    (6, 8, 30), (6, 11, 15), (4, 18, 15), (4, 2, 0), (2, 19, 30),
    (6, 13, 15), (6, 2, 30), (4, 14, 30), (2, 6, 30), (3, 14, 30),
    (1, 14, 15), (0, 2, 45),
}

BLOCKED_CANDLES = {
    (0, 0, 0), (0, 0, 15), (0, 0, 30), (0, 1, 30), (0, 1, 45), (0, 2, 0), (0, 2, 45),
    (0, 3, 0), (0, 3, 15), (0, 3, 30), (0, 4, 30), (0, 5, 30), (0, 6, 15), (0, 6, 30),
    (0, 7, 0), (0, 7, 15), (0, 7, 30), (0, 8, 0), (0, 9, 0), (0, 11, 30),
    (0, 14, 15), (0, 14, 30), (0, 14, 45), (0, 15, 0), (0, 15, 15), (0, 15, 30), (0, 15, 45),
    (0, 16, 45), (0, 17, 15), (0, 17, 30), (0, 18, 0), (0, 18, 15), (0, 18, 30),
    (0, 19, 0), (0, 19, 15), (0, 19, 30), (0, 20, 15), (0, 20, 30), (0, 20, 45),
    (0, 21, 0), (0, 21, 30), (0, 22, 0), (0, 23, 0), (0, 23, 30),
    (1, 0, 0), (1, 1, 15), (1, 1, 30), (1, 2, 45), (1, 3, 15), (1, 4, 15), (1, 4, 30),
    (1, 5, 0), (1, 5, 15), (1, 6, 0), (1, 7, 0), (1, 7, 30), (1, 7, 45),
    (1, 9, 0), (1, 9, 30), (1, 10, 15), (1, 11, 15), (1, 14, 15), (1, 15, 0), (1, 15, 30),
    (1, 16, 30), (1, 17, 0), (1, 18, 0), (1, 18, 15), (1, 18, 45),
    (1, 19, 0), (1, 19, 15), (1, 19, 30), (1, 20, 0), (1, 22, 15), (1, 22, 30), (1, 22, 45), (1, 23, 0),
    (2, 0, 0), (2, 0, 15), (2, 0, 30), (2, 2, 45), (2, 3, 15), (2, 3, 30), (2, 4, 15),
    (2, 5, 0), (2, 6, 30), (2, 7, 0), (2, 7, 30), (2, 8, 0), (2, 8, 15), (2, 8, 30),
    (2, 9, 15), (2, 9, 30), (2, 10, 30), (2, 11, 15), (2, 15, 0), (2, 16, 0), (2, 16, 45),
    (2, 17, 15), (2, 17, 30), (2, 18, 0), (2, 18, 30), (2, 19, 30), (2, 20, 30),
    (2, 21, 45), (2, 23, 0), (2, 23, 15), (2, 23, 45),
    (3, 0, 0), (3, 0, 15), (3, 1, 30), (3, 2, 0), (3, 2, 15), (3, 3, 0), (3, 3, 30),
    (3, 4, 0), (3, 4, 15), (3, 4, 30), (3, 5, 15), (3, 5, 30), (3, 5, 45),
    (3, 6, 15), (3, 6, 30), (3, 7, 0), (3, 7, 30), (3, 7, 45), (3, 8, 0), (3, 8, 30),
    (3, 9, 0), (3, 9, 30), (3, 10, 30), (3, 11, 0), (3, 11, 15), (3, 12, 30),
    (3, 13, 15), (3, 13, 30), (3, 13, 45), (3, 14, 30), (3, 15, 15), (3, 15, 30),
    (3, 16, 0), (3, 16, 30), (3, 18, 30), (3, 19, 30), (3, 20, 30), (3, 21, 0),
    (3, 22, 0), (3, 22, 15), (3, 22, 30), (3, 23, 15),
    (4, 0, 30), (4, 2, 0), (4, 2, 15), (4, 2, 30), (4, 3, 0), (4, 4, 15), (4, 4, 30),
    (4, 5, 0), (4, 5, 15), (4, 5, 30), (4, 6, 0), (4, 6, 30), (4, 7, 0), (4, 7, 15), (4, 7, 30),
    (4, 8, 0), (4, 8, 45), (4, 10, 0), (4, 10, 30), (4, 10, 45), (4, 11, 0),
    (4, 13, 15), (4, 14, 15), (4, 14, 30), (4, 14, 45), (4, 15, 15), (4, 15, 30), (4, 15, 45),
    (4, 16, 15), (4, 16, 45), (4, 17, 0), (4, 17, 15), (4, 17, 30), (4, 18, 15),
    (4, 19, 0), (4, 20, 0), (4, 22, 0), (4, 22, 15), (4, 23, 0), (4, 23, 15),
    (5, 0, 0), (5, 0, 15), (5, 1, 15), (5, 3, 0), (5, 3, 15), (5, 4, 15),
    (5, 6, 0), (5, 8, 15), (5, 8, 30), (5, 9, 45), (5, 10, 30), (5, 12, 15),
    (5, 13, 0), (5, 15, 15), (5, 19, 15), (5, 20, 30), (5, 22, 30), (5, 22, 45),
    (6, 0, 45), (6, 1, 30), (6, 2, 30), (6, 4, 0), (6, 4, 30), (6, 5, 30), (6, 5, 45),
    (6, 6, 30), (6, 7, 15), (6, 8, 30), (6, 8, 45), (6, 11, 15), (6, 13, 15), (6, 13, 30),
    (6, 15, 30), (6, 16, 30), (6, 17, 0), (6, 17, 15), (6, 19, 0), (6, 19, 45),
    (6, 21, 45), (6, 22, 0), (6, 22, 30), (6, 22, 45), (6, 23, 0), (6, 23, 15), (6, 23, 30),
}


def calculate_rsi(prices, period=14):
    """RSI standard"""
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = pd.Series(gains).ewm(span=period, adjust=False).mean().iloc[-1]
    avg_loss = pd.Series(losses).ewm(span=period, adjust=False).mean().iloc[-1]

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_stoch(highs, lows, closes, period=5):
    """Stochastic %K"""
    lowest_low = min(lows[-period:])
    highest_high = max(highs[-period:])
    if highest_high == lowest_low:
        return 50
    return ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100


def calculate_atr(highs, lows, closes, period=14):
    """Average True Range"""
    tr_list = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)
    if len(tr_list) < period:
        return np.mean(tr_list) if tr_list else 0
    return np.mean(tr_list[-period:])


def calculate_adx(highs, lows, closes, period=14):
    """Average Directional Index (trend strength)"""
    if len(highs) < period + 1:
        return 25  # neutral

    plus_dm = []
    minus_dm = []
    tr_list = []

    for i in range(1, len(highs)):
        up = highs[i] - highs[i-1]
        down = lows[i-1] - lows[i]

        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return 25

    atr = np.mean(tr_list[-period:])
    if atr == 0:
        return 25

    plus_di = 100 * np.mean(plus_dm[-period:]) / atr
    minus_di = 100 * np.mean(minus_dm[-period:]) / atr

    if plus_di + minus_di == 0:
        return 25

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return dx


def calculate_momentum(closes, period=10):
    """Rate of change / Momentum"""
    if len(closes) < period + 1:
        return 0
    return ((closes[-1] - closes[-period-1]) / closes[-period-1]) * 100


def get_candle_body_ratio(open_p, high, low, close):
    """Ratio body/range - mesure de l'indécision"""
    range_size = high - low
    if range_size == 0:
        return 0
    body_size = abs(close - open_p)
    return body_size / range_size


def fetch_historical_data(exchange, symbol, start_date, end_date):
    """Récupère les données historiques"""
    all_data = []
    current = start_date

    while current < end_date:
        since = int(current.timestamp() * 1000)
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            current = datetime.fromtimestamp(ohlcv[-1][0] / 1000, tz=timezone.utc) + timedelta(minutes=15)
            time.sleep(0.2)
        except Exception as e:
            print(f"Error: {e}")
            break

    return all_data


def analyze_candle_characteristics(ohlcv):
    """
    Pour chaque candle où on a un signal RSI/Stoch, calculer des indicateurs
    et classifier en NORMAL, SKIP, ou REVERSE selon les règles hard-codées.
    Puis analyser les différences.
    """
    LOOKBACK = 20
    RSI_PERIOD = 7
    STOCH_PERIOD = 5
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 58
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 80

    results = {
        'normal': [],
        'skip': [],
        'reverse': []
    }

    for i in range(LOOKBACK + 1, len(ohlcv) - 1):
        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        candle_key = (timestamp.weekday(), timestamp.hour, timestamp.minute)

        # Calculer RSI et Stoch
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i+1]]
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i+1]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i+1]]
        opens = [c[1] for c in ohlcv[i-LOOKBACK:i+1]]
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i+1]]

        rsi = calculate_rsi(closes, RSI_PERIOD)
        stoch = calculate_stoch(highs, lows, closes, STOCH_PERIOD)

        # Vérifier si on a un signal
        signal = None
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            signal = "DOWN"

        if not signal:
            continue

        # Calculer les indicateurs dynamiques
        atr = calculate_atr(highs, lows, closes, 14)
        adx = calculate_adx(highs, lows, closes, 14)
        momentum = calculate_momentum(closes, 10)

        # Volume relatif
        avg_volume = np.mean(volumes[:-1])
        current_volume = volumes[-1]
        rel_volume = current_volume / avg_volume if avg_volume > 0 else 1

        # Volatilité relative (ATR normalisé)
        price = closes[-1]
        atr_pct = (atr / price) * 100 if price > 0 else 0

        # Body ratio
        body_ratio = get_candle_body_ratio(opens[-1], highs[-1], lows[-1], closes[-1])

        # Consecutive candles
        directions = []
        for j in range(-4, 0):
            if opens[j] < closes[j]:
                directions.append("UP")
            else:
                directions.append("DOWN")
        consec_up = sum(1 for d in directions if d == "UP")
        consec_down = sum(1 for d in directions if d == "DOWN")

        # RSI momentum (RSI change)
        prev_rsi = calculate_rsi(closes[:-1], RSI_PERIOD) if len(closes) > 1 else rsi
        rsi_change = rsi - prev_rsi

        # Résultat réel
        actual_direction = "UP" if ohlcv[i+1][4] > ohlcv[i+1][1] else "DOWN"
        is_win = (signal == actual_direction)

        # Classifier
        if candle_key in REVERSE_CANDLES:
            category = 'reverse'
        elif candle_key in BLOCKED_CANDLES:
            category = 'skip'
        else:
            category = 'normal'

        results[category].append({
            'timestamp': timestamp,
            'signal': signal,
            'rsi': rsi,
            'stoch': stoch,
            'adx': adx,
            'atr_pct': atr_pct,
            'momentum': momentum,
            'rel_volume': rel_volume,
            'body_ratio': body_ratio,
            'consec_up': consec_up,
            'consec_down': consec_down,
            'rsi_change': rsi_change,
            'is_win': is_win
        })

    return results


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("ANALYSE: DETECTION DYNAMIQUE SKIP/REVERSE")
    print("=" * 90)
    print()
    print("Objectif: Trouver des indicateurs pour remplacer les 235 SKIP + 12 REVERSE")
    print("=" * 90)

    # Période d'analyse
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    all_results = {'normal': [], 'skip': [], 'reverse': []}

    for symbol in symbols:
        print(f"\nTéléchargement {symbol}...")
        data = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(data)} candles")

        results = analyze_candle_characteristics(data)
        for cat in all_results:
            all_results[cat].extend(results[cat])

    # Analyser les différences
    print("\n" + "=" * 90)
    print("STATISTIQUES PAR CATEGORIE")
    print("=" * 90)

    for category in ['normal', 'skip', 'reverse']:
        data = all_results[category]
        if not data:
            continue

        wins = sum(1 for d in data if d['is_win'])
        total = len(data)
        wr = (wins / total * 100) if total > 0 else 0

        print(f"\n{category.upper()} ({total} signaux, WR: {wr:.1f}%)")
        print("-" * 60)

        # Moyennes des indicateurs
        avg_adx = np.mean([d['adx'] for d in data])
        avg_atr = np.mean([d['atr_pct'] for d in data])
        avg_momentum = np.mean([d['momentum'] for d in data])
        avg_volume = np.mean([d['rel_volume'] for d in data])
        avg_body = np.mean([d['body_ratio'] for d in data])
        avg_rsi_change = np.mean([d['rsi_change'] for d in data])

        print(f"  ADX (trend strength):  {avg_adx:.1f}")
        print(f"  ATR% (volatility):     {avg_atr:.3f}%")
        print(f"  Momentum (10):         {avg_momentum:.2f}%")
        print(f"  Rel. Volume:           {avg_volume:.2f}x")
        print(f"  Body Ratio:            {avg_body:.2f}")
        print(f"  RSI Change:            {avg_rsi_change:.2f}")

    # Comparer SKIP vs NORMAL
    print("\n" + "=" * 90)
    print("COMPARAISON: SKIP vs NORMAL")
    print("=" * 90)

    if all_results['skip'] and all_results['normal']:
        skip_data = all_results['skip']
        normal_data = all_results['normal']

        indicators = ['adx', 'atr_pct', 'momentum', 'rel_volume', 'body_ratio', 'rsi_change']

        print(f"\n{'Indicateur':<20} | {'NORMAL':>10} | {'SKIP':>10} | {'Diff':>10} | Insight")
        print("-" * 80)

        for ind in indicators:
            normal_avg = np.mean([d[ind] for d in normal_data])
            skip_avg = np.mean([d[ind] for d in skip_data])
            diff = skip_avg - normal_avg
            diff_pct = (diff / normal_avg * 100) if normal_avg != 0 else 0

            insight = ""
            if abs(diff_pct) > 10:
                if ind == 'adx' and diff > 0:
                    insight = "SKIP quand trend fort"
                elif ind == 'atr_pct' and diff > 0:
                    insight = "SKIP quand volatilité haute"
                elif ind == 'rel_volume' and diff < 0:
                    insight = "SKIP quand volume faible"
                elif ind == 'momentum' and abs(diff) > 0.1:
                    insight = "SKIP quand momentum fort"

            print(f"{ind:<20} | {normal_avg:>10.3f} | {skip_avg:>10.3f} | {diff:>+10.3f} | {insight}")

    # Comparer REVERSE vs NORMAL
    print("\n" + "=" * 90)
    print("COMPARAISON: REVERSE vs NORMAL")
    print("=" * 90)

    if all_results['reverse'] and all_results['normal']:
        reverse_data = all_results['reverse']
        normal_data = all_results['normal']

        print(f"\n{'Indicateur':<20} | {'NORMAL':>10} | {'REVERSE':>10} | {'Diff':>10} | Insight")
        print("-" * 80)

        for ind in indicators:
            normal_avg = np.mean([d[ind] for d in normal_data])
            reverse_avg = np.mean([d[ind] for d in reverse_data])
            diff = reverse_avg - normal_avg
            diff_pct = (diff / normal_avg * 100) if normal_avg != 0 else 0

            insight = ""
            if abs(diff_pct) > 10:
                if ind == 'adx' and diff > 0:
                    insight = "REVERSE quand trend fort"
                elif ind == 'momentum' and abs(diff) > 0.1:
                    insight = "REVERSE quand momentum fort"
                elif ind == 'rel_volume' and abs(diff) > 0.1:
                    insight = "REVERSE quand volume different"

            print(f"{ind:<20} | {normal_avg:>10.3f} | {reverse_avg:>10.3f} | {diff:>+10.3f} | {insight}")

    # Trouver des seuils dynamiques
    print("\n" + "=" * 90)
    print("PROPOSITION: REGLES DYNAMIQUES")
    print("=" * 90)

    # Analyser les distributions
    if all_results['skip'] and all_results['normal']:
        # Volume
        skip_volumes = [d['rel_volume'] for d in all_results['skip']]
        normal_volumes = [d['rel_volume'] for d in all_results['normal']]

        print("\n1. VOLUME FILTER (pour SKIP)")
        print(f"   Normal: Volume moyen = {np.mean(normal_volumes):.2f}x")
        print(f"   Skip:   Volume moyen = {np.mean(skip_volumes):.2f}x")

        # Percentiles
        skip_vol_25 = np.percentile(skip_volumes, 25)
        skip_vol_75 = np.percentile(skip_volumes, 75)
        print(f"   Skip percentiles: 25%={skip_vol_25:.2f}x, 75%={skip_vol_75:.2f}x")

        # ADX
        skip_adx = [d['adx'] for d in all_results['skip']]
        normal_adx = [d['adx'] for d in all_results['normal']]

        print("\n2. ADX FILTER (pour SKIP - trend strength)")
        print(f"   Normal: ADX moyen = {np.mean(normal_adx):.1f}")
        print(f"   Skip:   ADX moyen = {np.mean(skip_adx):.1f}")

        # Momentum pour REVERSE
        if all_results['reverse']:
            reverse_mom = [d['momentum'] for d in all_results['reverse']]
            normal_mom = [d['momentum'] for d in all_results['normal']]

            print("\n3. MOMENTUM FILTER (pour REVERSE)")
            print(f"   Normal:  Momentum moyen = {np.mean(normal_mom):.3f}%")
            print(f"   Reverse: Momentum moyen = {np.mean(reverse_mom):.3f}%")

            # Si momentum va dans sens opposé au signal, REVERSE
            print("\n   Logique: Si signal=UP mais momentum<-X% -> REVERSE")
            print("            Si signal=DOWN mais momentum>+X% -> REVERSE")

    # Tester une stratégie dynamique
    print("\n" + "=" * 90)
    print("TEST: STRATEGIE DYNAMIQUE vs HARD-CODED")
    print("=" * 90)

    # Stratégie dynamique proposée
    # SKIP si: Volume < 0.8x OU ADX > 35 OU ATR% > seuil
    # REVERSE si: Momentum dans sens opposé au signal > 0.5%

    dynamic_skip = 0
    dynamic_reverse = 0
    dynamic_wins = 0
    dynamic_total = 0

    hardcoded_wins = 0
    hardcoded_total = 0

    all_signals = all_results['normal'] + all_results['skip'] + all_results['reverse']

    for d in all_signals:
        # Stratégie hard-codée
        candle_key = (d['timestamp'].weekday(), d['timestamp'].hour, d['timestamp'].minute)

        if candle_key in BLOCKED_CANDLES:
            continue  # Skip
        elif candle_key in REVERSE_CANDLES:
            # Reverse: le win devient loss et vice versa
            hardcoded_wins += 0 if d['is_win'] else 1
        else:
            hardcoded_wins += 1 if d['is_win'] else 0
        hardcoded_total += 1

        # Stratégie dynamique
        should_skip = False
        should_reverse = False

        # SKIP conditions
        if d['rel_volume'] < 0.7:
            should_skip = True
            dynamic_skip += 1
        elif d['adx'] > 40:
            should_skip = True
            dynamic_skip += 1

        # REVERSE conditions
        if not should_skip:
            if d['signal'] == "UP" and d['momentum'] < -0.5:
                should_reverse = True
                dynamic_reverse += 1
            elif d['signal'] == "DOWN" and d['momentum'] > 0.5:
                should_reverse = True
                dynamic_reverse += 1

        if should_skip:
            continue
        elif should_reverse:
            dynamic_wins += 0 if d['is_win'] else 1
        else:
            dynamic_wins += 1 if d['is_win'] else 0
        dynamic_total += 1

    hardcoded_wr = (hardcoded_wins / hardcoded_total * 100) if hardcoded_total > 0 else 0
    dynamic_wr = (dynamic_wins / dynamic_total * 100) if dynamic_total > 0 else 0

    print(f"\n{'Stratégie':<25} | {'Trades':>8} | {'Wins':>8} | {'WR':>8}")
    print("-" * 60)
    print(f"{'Hard-coded (235+12)':<25} | {hardcoded_total:>8} | {hardcoded_wins:>8} | {hardcoded_wr:>7.1f}%")
    print(f"{'Dynamique':<25} | {dynamic_total:>8} | {dynamic_wins:>8} | {dynamic_wr:>7.1f}%")
    print(f"\nDynamique: {dynamic_skip} SKIP, {dynamic_reverse} REVERSE")

    print("\n" + "=" * 90)
    print("CONCLUSION")
    print("=" * 90)
    print("""
INDICATEURS DYNAMIQUES PROPOSES:

1. SKIP CONDITIONS (ne pas trader):
   - Volume < 0.7x moyenne (faible liquidité)
   - ADX > 40 (trend trop fort, mean reversion risquée)
   - ATR% > seuil (volatilité extrême)

2. REVERSE CONDITIONS (inverser le signal):
   - Signal UP mais Momentum(10) < -0.5% (tendance baissière forte)
   - Signal DOWN mais Momentum(10) > +0.5% (tendance haussière forte)

3. INDICATEURS SUPPLEMENTAIRES A TESTER:
   - Body ratio < 0.3 (doji/indécision) -> SKIP
   - RSI change extrême (>10 points) -> signal fort
   - Consecutive candles opposées au signal -> REVERSE
    """)


if __name__ == "__main__":
    main()
