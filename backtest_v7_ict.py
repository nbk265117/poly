#!/usr/bin/env python3
"""
BACKTEST V7 - ICT ENHANCED
==========================
Compare V6 baseline vs V7 avec filtres ICT

Cible: 18+ mois avec PnL > $15,000
"""

import ccxt
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def calculate_rsi(prices, period=7):
    """RSI"""
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
    """Stochastic"""
    lowest_low = min(lows[-period:])
    highest_high = max(highs[-period:])
    if highest_high == lowest_low:
        return 50
    return ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100


def calculate_range_position(highs, lows, closes, period=50):
    """ICT Range Position (Premium/Discount)"""
    if len(highs) < period:
        return 50
    range_high = max(highs[-period:])
    range_low = min(lows[-period:])
    if range_high == range_low:
        return 50
    return ((closes[-1] - range_low) / (range_high - range_low)) * 100


def calculate_ema(prices, period):
    """EMA"""
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]


def calculate_confidence_v7(rsi, stoch, range_pos, rel_volume, trend, signal, use_ict=True):
    """
    Confidence score V7 avec ICT
    """
    confidence = 50

    # 1. ICT Range Position (max +20, min -15)
    if use_ict:
        if signal == "UP":
            if range_pos < 15:
                confidence += 20
            elif range_pos < 30:
                confidence += 15
            elif range_pos < 40:
                confidence += 10
            elif range_pos > 70:
                confidence -= 15
        else:
            if range_pos > 85:
                confidence += 20
            elif range_pos > 70:
                confidence += 15
            elif range_pos > 60:
                confidence += 10
            elif range_pos < 30:
                confidence -= 15

    # 2. RSI Extremity (max +25)
    if signal == "UP":
        if rsi < 20:
            confidence += 25
        elif rsi < 25:
            confidence += 20
        elif rsi < 30:
            confidence += 15
        elif rsi < 35:
            confidence += 10
    else:
        if rsi > 80:
            confidence += 25
        elif rsi > 75:
            confidence += 20
        elif rsi > 72:
            confidence += 15
        elif rsi > 70:
            confidence += 10

    # 3. Stoch Extremity (max +15)
    if signal == "UP":
        if stoch < 10:
            confidence += 15
        elif stoch < 20:
            confidence += 10
    else:
        if stoch > 90:
            confidence += 15
        elif stoch > 80:
            confidence += 10

    # 4. Volume (max +10, min -15)
    if 0.7 <= rel_volume <= 1.5:
        confidence += 10
    elif rel_volume < 0.4:
        confidence -= 15
    elif rel_volume > 3.0:
        confidence -= 10

    # 5. Trend (max +10, min -5)
    if (signal == "UP" and trend == "UP") or (signal == "DOWN" and trend == "DOWN"):
        confidence += 10
    elif (signal == "UP" and trend == "DOWN") or (signal == "DOWN" and trend == "UP"):
        confidence -= 5

    return max(0, min(100, confidence))


def fetch_historical_data(exchange, symbol, start_date, end_date):
    """Recupere les donnees historiques"""
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


def backtest_v7(ohlcv, confidence_threshold=70, use_ict=True, bet_amount=100):
    """
    Backtest V7 avec ou sans ICT
    """
    LOOKBACK = 60  # Plus de lookback pour Range Position
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 68
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 75

    entry_price = 0.52
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    monthly_results = defaultdict(lambda: {
        'trades': 0, 'wins': 0, 'pnl': 0,
        'up_trades': 0, 'up_wins': 0,
        'down_trades': 0, 'down_wins': 0
    })

    for i in range(LOOKBACK + 1, len(ohlcv) - 1):
        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month_key = timestamp.strftime("%Y-%m")

        closes = [c[4] for c in ohlcv[i-LOOKBACK:i+1]]
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i+1]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i+1]]
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i+1]]

        rsi = calculate_rsi(closes, 7)
        stoch = calculate_stoch(highs, lows, closes, 5)
        range_pos = calculate_range_position(highs, lows, closes, 50)

        # Signal V6
        signal = None
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            signal = "DOWN"

        if not signal:
            continue

        # Indicateurs supplementaires
        avg_volume = np.mean(volumes[:-1])
        rel_volume = volumes[-1] / avg_volume if avg_volume > 0 else 1

        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)
        trend = "UP" if ema20 > ema50 else "DOWN"

        # Confidence V7
        confidence = calculate_confidence_v7(rsi, stoch, range_pos, rel_volume, trend, signal, use_ict)

        if confidence < confidence_threshold:
            continue

        # Trade
        actual = "UP" if ohlcv[i+1][4] > ohlcv[i+1][1] else "DOWN"
        is_win = (signal == actual)

        monthly_results[month_key]['trades'] += 1

        if signal == "UP":
            monthly_results[month_key]['up_trades'] += 1
            if is_win:
                monthly_results[month_key]['up_wins'] += 1
        else:
            monthly_results[month_key]['down_trades'] += 1
            if is_win:
                monthly_results[month_key]['down_wins'] += 1

        if is_win:
            monthly_results[month_key]['wins'] += 1
            monthly_results[month_key]['pnl'] += win_profit
        else:
            monthly_results[month_key]['pnl'] -= loss_amount

    return dict(monthly_results)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("BACKTEST V7 - ICT ENHANCED")
    print("=" * 90)
    print()
    print("STRATEGIE V7:")
    print("  Signal UP:   RSI(7) < 38 AND Stoch(5) < 30")
    print("  Signal DOWN: RSI(7) > 68 AND Stoch(5) > 75")
    print("  ICT Filter:  Range Position (Premium/Discount zones)")
    print("=" * 90)

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Charger les donnees
    all_data = {}
    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(all_data[symbol])} candles")

    # Configurations a tester
    configs = [
        ("V6 Baseline (no filter)", 0, False),
        ("V7 ICT Conf>=60", 60, True),
        ("V7 ICT Conf>=65", 65, True),
        ("V7 ICT Conf>=70", 70, True),
        ("V7 ICT Conf>=75", 75, True),
        ("V7 ICT Conf>=80", 80, True),
    ]

    results_by_config = {}

    for name, threshold, use_ict in configs:
        combined = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'pnl': 0,
            'up_trades': 0, 'up_wins': 0,
            'down_trades': 0, 'down_wins': 0
        })

        for symbol in symbols:
            results = backtest_v7(
                all_data[symbol],
                confidence_threshold=threshold,
                use_ict=use_ict
            )
            for month, stats in results.items():
                for key in stats:
                    combined[month][key] += stats[key]

        results_by_config[name] = dict(combined)

    # Comparaison
    print("\n" + "=" * 90)
    print("COMPARAISON DES CONFIGURATIONS")
    print("=" * 90)
    print()
    print(f"{'Config':<25} | {'Trades':>8} | {'WR':>7} | {'PnL Total':>12} | {'Mois>$15k':>10} | {'Min Mois':>10}")
    print("-" * 90)

    for name in configs:
        config_name = name[0]
        results = results_by_config[config_name]

        total_trades = sum(s['trades'] for s in results.values())
        total_wins = sum(s['wins'] for s in results.values())
        total_pnl = sum(s['pnl'] for s in results.values())

        months_above_15k = sum(1 for s in results.values() if s['pnl'] >= 15000)
        min_month = min(s['pnl'] for s in results.values()) if results else 0

        wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        pnl_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
        min_str = f"+${min_month:,.0f}" if min_month >= 0 else f"-${abs(min_month):,.0f}"

        print(f"{config_name:<25} | {total_trades:>8,} | {wr:>6.1f}% | {pnl_str:>12} | {months_above_15k:>6}/24   | {min_str:>10}")

    # Detail meilleure config
    best_config = max(
        configs,
        key=lambda c: sum(1 for s in results_by_config[c[0]].values() if s['pnl'] >= 15000)
    )
    best_name = best_config[0]

    print("\n" + "=" * 90)
    print(f"DETAIL: {best_name}")
    print("=" * 90)

    results = results_by_config[best_name]

    print(f"\n{'Mois':<10} | {'Trades':>7} | {'UP':>5} | {'DOWN':>5} | {'Wins':>5} | {'WR':>6} | {'PnL':>12}")
    print("-" * 75)

    for month in sorted(results.keys()):
        s = results[month]
        mwr = (s['wins'] / s['trades'] * 100) if s['trades'] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        indicator = " *" if s['pnl'] >= 15000 else ""
        print(f"{month:<10} | {s['trades']:>7,} | {s['up_trades']:>5} | {s['down_trades']:>5} | {s['wins']:>5} | {mwr:>5.1f}% | {pnl_str:>12}{indicator}")

    total_trades = sum(s['trades'] for s in results.values())
    total_wins = sum(s['wins'] for s in results.values())
    total_pnl = sum(s['pnl'] for s in results.values())
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print("-" * 75)
    pnl_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
    print(f"{'TOTAL':<10} | {total_trades:>7,} | {sum(s['up_trades'] for s in results.values()):>5} | {sum(s['down_trades'] for s in results.values()):>5} | {total_wins:>5} | {total_wr:>5.1f}% | {pnl_str:>12}")

    months_above_15k = sum(1 for s in results.values() if s['pnl'] >= 15000)
    months_above_10k = sum(1 for s in results.values() if s['pnl'] >= 10000)

    print(f"\n* Mois marques avec '*' ont PnL >= $15,000")
    print(f"\nRESUME:")
    print(f"  Mois > $15,000: {months_above_15k}/24")
    print(f"  Mois > $10,000: {months_above_10k}/24")
    print(f"  PnL Moyen/Mois: ${total_pnl/24:,.0f}")
    print(f"  Trades/Jour: ~{total_trades/(24*30):.0f}")


if __name__ == "__main__":
    main()
