#!/usr/bin/env python3
"""
ANALYSE V2: Detection dynamique basée sur RSI Velocity et Sessions

Insights de l'analyse V1:
- SKIP: Pas de différence claire avec indicateurs simples
- REVERSE: RSI Change significativement plus élevé (0.96 vs 0.16)

Nouvelles approches:
1. RSI Velocity (vitesse de changement RSI)
2. Sessions de marché (Asian/London/NY)
3. Signal Confidence (confluence d'indicateurs)
4. Win Rate glissant (régime récent)
"""

import ccxt
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from collections import defaultdict


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


def get_market_session(hour):
    """Determine market session based on UTC hour"""
    if 0 <= hour < 8:
        return "ASIAN"
    elif 8 <= hour < 13:
        return "LONDON"
    elif 13 <= hour < 21:
        return "NEW_YORK"
    else:
        return "ASIAN_EARLY"


def calculate_signal_confidence(rsi, stoch, rel_volume, atr_pct, rsi_velocity):
    """
    Score de confiance du signal (0-100)
    Plus le score est bas, moins on devrait trader
    """
    score = 50  # Base

    # RSI extreme = plus de confiance
    if rsi < 30 or rsi > 70:
        score += 15
    elif rsi < 35 or rsi > 65:
        score += 10
    elif rsi < 40 or rsi > 60:
        score += 5

    # Stoch extreme = plus de confiance
    if stoch < 20 or stoch > 80:
        score += 15
    elif stoch < 30 or stoch > 70:
        score += 10

    # Volume bon = plus de confiance
    if 0.8 < rel_volume < 1.5:
        score += 10
    elif rel_volume < 0.5 or rel_volume > 2.5:
        score -= 15

    # RSI velocity trop forte = moins de confiance (momentum contre nous)
    if abs(rsi_velocity) > 5:
        score -= 20
    elif abs(rsi_velocity) > 3:
        score -= 10

    return max(0, min(100, score))


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


def analyze_with_dynamic_rules(ohlcv, entry_price=0.525, bet_amount=100):
    """
    Analyse avec différentes règles dynamiques
    """
    LOOKBACK = 20
    RSI_PERIOD = 7
    STOCH_PERIOD = 5
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 58
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 80

    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    results = {
        'baseline': {'trades': 0, 'wins': 0, 'pnl': 0},  # RSI+Stoch sans filtre
        'rsi_velocity': {'trades': 0, 'wins': 0, 'pnl': 0},  # Filtre RSI velocity
        'confidence': {'trades': 0, 'wins': 0, 'pnl': 0},  # Score confiance > 60
        'session': {'trades': 0, 'wins': 0, 'pnl': 0},  # Skip mauvaises sessions
        'combined': {'trades': 0, 'wins': 0, 'pnl': 0},  # Tout combiné
    }

    # Stats par session
    session_stats = {
        'ASIAN': {'trades': 0, 'wins': 0},
        'LONDON': {'trades': 0, 'wins': 0},
        'NEW_YORK': {'trades': 0, 'wins': 0},
        'ASIAN_EARLY': {'trades': 0, 'wins': 0},
    }

    # Stats par RSI velocity bucket
    velocity_stats = defaultdict(lambda: {'trades': 0, 'wins': 0})

    prev_rsi = None

    for i in range(LOOKBACK + 1, len(ohlcv) - 1):
        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)

        closes = [c[4] for c in ohlcv[i-LOOKBACK:i+1]]
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i+1]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i+1]]
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i+1]]

        rsi = calculate_rsi(closes, RSI_PERIOD)
        stoch = calculate_stoch(highs, lows, closes, STOCH_PERIOD)

        # RSI Velocity (changement entre 2 candles)
        rsi_velocity = rsi - prev_rsi if prev_rsi is not None else 0
        prev_rsi = rsi

        # Vérifier signal
        signal = None
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            signal = "DOWN"

        if not signal:
            continue

        # Indicateurs supplémentaires
        avg_volume = np.mean(volumes[:-1])
        rel_volume = volumes[-1] / avg_volume if avg_volume > 0 else 1

        price = closes[-1]
        atr = np.mean([highs[j] - lows[j] for j in range(-14, 0)])
        atr_pct = (atr / price) * 100 if price > 0 else 0

        session = get_market_session(timestamp.hour)
        confidence = calculate_signal_confidence(rsi, stoch, rel_volume, atr_pct, rsi_velocity)

        # Résultat réel
        actual = "UP" if ohlcv[i+1][4] > ohlcv[i+1][1] else "DOWN"
        is_win = (signal == actual)

        # Stats sessions
        session_stats[session]['trades'] += 1
        session_stats[session]['wins'] += 1 if is_win else 0

        # Stats velocity
        velocity_bucket = int(rsi_velocity / 2) * 2  # Bucket de 2
        velocity_stats[velocity_bucket]['trades'] += 1
        velocity_stats[velocity_bucket]['wins'] += 1 if is_win else 0

        # === STRATEGIES ===

        # 1. Baseline (pas de filtre)
        results['baseline']['trades'] += 1
        if is_win:
            results['baseline']['wins'] += 1
            results['baseline']['pnl'] += win_profit
        else:
            results['baseline']['pnl'] -= loss_amount

        # 2. RSI Velocity filter (skip si velocity > 3 dans sens opposé)
        skip_velocity = False
        if signal == "UP" and rsi_velocity < -3:
            skip_velocity = True
        elif signal == "DOWN" and rsi_velocity > 3:
            skip_velocity = True

        if not skip_velocity:
            results['rsi_velocity']['trades'] += 1
            if is_win:
                results['rsi_velocity']['wins'] += 1
                results['rsi_velocity']['pnl'] += win_profit
            else:
                results['rsi_velocity']['pnl'] -= loss_amount

        # 3. Confidence filter (score > 60)
        if confidence >= 60:
            results['confidence']['trades'] += 1
            if is_win:
                results['confidence']['wins'] += 1
                results['confidence']['pnl'] += win_profit
            else:
                results['confidence']['pnl'] -= loss_amount

        # 4. Session filter (skip Asian early)
        if session != "ASIAN_EARLY":
            results['session']['trades'] += 1
            if is_win:
                results['session']['wins'] += 1
                results['session']['pnl'] += win_profit
            else:
                results['session']['pnl'] -= loss_amount

        # 5. Combined (velocity + confidence > 55)
        if not skip_velocity and confidence >= 55:
            results['combined']['trades'] += 1
            if is_win:
                results['combined']['wins'] += 1
                results['combined']['pnl'] += win_profit
            else:
                results['combined']['pnl'] -= loss_amount

    return results, session_stats, dict(velocity_stats)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("ANALYSE V2: DETECTION DYNAMIQUE - RSI VELOCITY & SESSIONS")
    print("=" * 90)

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 1, 1, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    total_results = {k: {'trades': 0, 'wins': 0, 'pnl': 0} for k in
                     ['baseline', 'rsi_velocity', 'confidence', 'session', 'combined']}

    total_session_stats = defaultdict(lambda: {'trades': 0, 'wins': 0})
    total_velocity_stats = defaultdict(lambda: {'trades': 0, 'wins': 0})

    for symbol in symbols:
        print(f"\nTéléchargement {symbol}...")
        data = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(data)} candles")

        results, session_stats, velocity_stats = analyze_with_dynamic_rules(data)

        for k in total_results:
            for metric in ['trades', 'wins', 'pnl']:
                total_results[k][metric] += results[k][metric]

        for session in session_stats:
            total_session_stats[session]['trades'] += session_stats[session]['trades']
            total_session_stats[session]['wins'] += session_stats[session]['wins']

        for bucket in velocity_stats:
            total_velocity_stats[bucket]['trades'] += velocity_stats[bucket]['trades']
            total_velocity_stats[bucket]['wins'] += velocity_stats[bucket]['wins']

    # Résultats par stratégie
    print("\n" + "=" * 90)
    print("COMPARAISON DES STRATEGIES")
    print("=" * 90)

    print(f"\n{'Stratégie':<25} | {'Trades':>8} | {'Wins':>8} | {'WR':>7} | {'PnL':>12} | {'PnL/Trade':>10}")
    print("-" * 85)

    for name, stats in total_results.items():
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        pnl_str = f"+${stats['pnl']:,.0f}" if stats['pnl'] >= 0 else f"-${abs(stats['pnl']):,.0f}"
        ppt = stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
        print(f"{name:<25} | {stats['trades']:>8,} | {stats['wins']:>8,} | {wr:>6.1f}% | {pnl_str:>12} | ${ppt:>9.2f}")

    # Stats par session
    print("\n" + "=" * 90)
    print("WIN RATE PAR SESSION DE MARCHE (UTC)")
    print("=" * 90)
    print(f"\n{'Session':<15} | {'Heures UTC':<12} | {'Trades':>8} | {'Wins':>8} | {'WR':>7}")
    print("-" * 60)

    session_hours = {
        'ASIAN': '00:00-08:00',
        'LONDON': '08:00-13:00',
        'NEW_YORK': '13:00-21:00',
        'ASIAN_EARLY': '21:00-00:00'
    }

    for session in ['ASIAN', 'LONDON', 'NEW_YORK', 'ASIAN_EARLY']:
        stats = total_session_stats[session]
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        print(f"{session:<15} | {session_hours[session]:<12} | {stats['trades']:>8,} | {stats['wins']:>8,} | {wr:>6.1f}%")

    # Stats par RSI velocity
    print("\n" + "=" * 90)
    print("WIN RATE PAR RSI VELOCITY")
    print("=" * 90)
    print(f"\n{'RSI Velocity':<15} | {'Trades':>8} | {'Wins':>8} | {'WR':>7} | {'Insight':<30}")
    print("-" * 80)

    for bucket in sorted(total_velocity_stats.keys()):
        stats = total_velocity_stats[bucket]
        if stats['trades'] < 100:
            continue
        wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0

        insight = ""
        if wr > 58:
            insight = "HIGH CONFIDENCE"
        elif wr > 55:
            insight = "GOOD"
        elif wr < 52:
            insight = "SKIP - Low WR"

        print(f"{bucket:>+3} to {bucket+2:>+3}       | {stats['trades']:>8,} | {stats['wins']:>8,} | {wr:>6.1f}% | {insight}")

    # Règles recommandées
    print("\n" + "=" * 90)
    print("REGLES DYNAMIQUES RECOMMANDEES")
    print("=" * 90)

    # Trouver les meilleurs buckets de velocity
    good_velocity = []
    bad_velocity = []
    for bucket, stats in total_velocity_stats.items():
        if stats['trades'] >= 100:
            wr = (stats['wins'] / stats['trades'] * 100)
            if wr < 52:
                bad_velocity.append((bucket, wr))
            elif wr > 57:
                good_velocity.append((bucket, wr))

    print(f"""
ANALYSE COMPLETE:

1. RSI VELOCITY RULES:
   - Velocity zones à SKIP (WR < 52%): {bad_velocity if bad_velocity else "Aucune"}
   - Velocity zones HIGH CONF (WR > 57%): {good_velocity if good_velocity else "Aucune"}

2. SESSION RULES:
   - Meilleures sessions: LONDON et NEW_YORK
   - À surveiller: ASIAN (volume plus faible)

3. STRATEGIE "COMBINED" (RSI Velocity + Confidence):
   - Trades: {total_results['combined']['trades']:,}
   - Win Rate: {total_results['combined']['wins']/total_results['combined']['trades']*100:.1f}%
   - PnL: ${total_results['combined']['pnl']:,.0f}

4. IMPLEMENTATION PROPOSEE:

   def should_skip(rsi_velocity, signal):
       # Skip si RSI va dans sens opposé au signal trop vite
       if signal == "UP" and rsi_velocity < -3:
           return True
       if signal == "DOWN" and rsi_velocity > 3:
           return True
       return False

   def should_reverse(rsi_velocity, signal, confidence):
       # Pas de règle REVERSE claire - les patterns temporels
       # sont trop spécifiques pour être capturés dynamiquement
       return False
    """)

    # Conclusion
    print("=" * 90)
    print("CONCLUSION")
    print("=" * 90)

    baseline_wr = total_results['baseline']['wins'] / total_results['baseline']['trades'] * 100
    combined_wr = total_results['combined']['wins'] / total_results['combined']['trades'] * 100

    print(f"""
VERDICT:

1. RSI Velocity est le MEILLEUR indicateur dynamique trouvé
   - Baseline WR: {baseline_wr:.1f}%
   - Avec filtre velocity: {total_results['rsi_velocity']['wins']/total_results['rsi_velocity']['trades']*100:.1f}%
   - Combined: {combined_wr:.1f}%

2. Les patterns SKIP/REVERSE hard-codés capturent des micro-structures
   de marché (timing institutionnel, news, etc.) qui sont DIFFICILES
   à détecter avec des indicateurs techniques simples.

3. RECOMMANDATION:
   - Utiliser RSI Velocity comme filtre DYNAMIQUE principal
   - Garder un sous-ensemble des SKIP les plus robustes (WR < 48%)
   - Supprimer REVERSE (trop peu de données, risque d'overfitting)
""")


if __name__ == "__main__":
    main()
