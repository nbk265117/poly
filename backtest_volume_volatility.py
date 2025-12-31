#!/usr/bin/env python3
"""
BACKTEST: Volume-Volatility Context Strategy
Based on Reddit discussion insights

SETUP: 2 candles consecutives
CONTEXT:
  - Volume Relatif > 1.2x moyenne
  - RSI ajuste crypto: < 30 ou > 70
  - ATR regime (volatilite)

RULES:
  - 2 DOWN + Volume eleve + RSI < 30 -> UP
  - 2 UP + Volume eleve + RSI > 70 -> DOWN
  - Volume faible -> SKIP
"""

import ccxt
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def calculate_rsi(prices, period=14):
    """Calcule le RSI"""
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_atr(high, low, close, period=14):
    """Calcule l'ATR"""
    tr_list = []
    for i in range(1, len(high)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return np.mean(tr_list) if tr_list else 0

    return np.mean(tr_list[-period:])


def get_direction(candle):
    """UP si close > open, sinon DOWN"""
    return "UP" if candle[4] > candle[1] else "DOWN"


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


def backtest_volume_volatility(symbol, ohlcv, bet_amount=100):
    """
    Backtest Volume-Volatility Context Strategy
    """
    # Parametres
    VOLUME_THRESHOLD = 1.2  # Volume > 1.2x moyenne
    RSI_OVERSOLD = 30       # RSI < 30 pour signal UP
    RSI_OVERBOUGHT = 70     # RSI > 70 pour signal DOWN
    LOOKBACK = 20           # Periode pour moyennes

    entry_price = 0.525
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    monthly_results = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})

    # Stats globales
    total_signals = 0
    filtered_by_volume = 0
    filtered_by_rsi = 0

    for i in range(LOOKBACK + 2, len(ohlcv) - 1):
        # Directions des 2 dernieres candles fermees
        d1 = get_direction(ohlcv[i-2])
        d2 = get_direction(ohlcv[i-1])

        # Verifier 2 candles consecutives
        if d1 != d2:
            continue

        total_signals += 1

        # Calculer le volume relatif
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i]]
        avg_volume = np.mean(volumes)
        current_volume = ohlcv[i-1][5]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 0

        # Calculer RSI
        closes = [c[4] for c in ohlcv[i-LOOKBACK-14:i]]
        rsi = calculate_rsi(closes)

        # Calculer ATR (pour info)
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i]]
        closes_atr = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        atr = calculate_atr(highs, lows, closes_atr)

        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month_key = timestamp.strftime("%Y-%m")

        signal = None

        # REGLE 1: 2 DOWN + Volume eleve + RSI oversold -> UP
        if d1 == "DOWN" and d2 == "DOWN":
            if relative_volume < VOLUME_THRESHOLD:
                filtered_by_volume += 1
                monthly_results[month_key]["skipped"] += 1
                continue
            if rsi > RSI_OVERSOLD:
                filtered_by_rsi += 1
                monthly_results[month_key]["skipped"] += 1
                continue
            signal = "UP"

        # REGLE 2: 2 UP + Volume eleve + RSI overbought -> DOWN
        elif d1 == "UP" and d2 == "UP":
            if relative_volume < VOLUME_THRESHOLD:
                filtered_by_volume += 1
                monthly_results[month_key]["skipped"] += 1
                continue
            if rsi < RSI_OVERBOUGHT:
                filtered_by_rsi += 1
                monthly_results[month_key]["skipped"] += 1
                continue
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            monthly_results[month_key]["trades"] += 1

            if signal == actual:
                monthly_results[month_key]["wins"] += 1
                monthly_results[month_key]["pnl"] += win_profit
            else:
                monthly_results[month_key]["losses"] += 1
                monthly_results[month_key]["pnl"] -= loss_amount

    return dict(monthly_results), {
        "total_signals": total_signals,
        "filtered_by_volume": filtered_by_volume,
        "filtered_by_rsi": filtered_by_rsi
    }


def backtest_v2_simple(symbol, ohlcv, bet_amount=100):
    """
    Backtest V2 Simple (pour comparaison)
    Regle: 3 candles consecutives -> inverse
    """
    entry_price = 0.525
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    monthly_results = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

    for i in range(3, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-3])
        d2 = get_direction(ohlcv[i-2])
        d3 = get_direction(ohlcv[i-1])

        signal = None
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN":
            signal = "UP"
        elif d1 == "UP" and d2 == "UP" and d3 == "UP":
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
            month_key = timestamp.strftime("%Y-%m")

            monthly_results[month_key]["trades"] += 1

            if signal == actual:
                monthly_results[month_key]["wins"] += 1
                monthly_results[month_key]["pnl"] += win_profit
            else:
                monthly_results[month_key]["losses"] += 1
                monthly_results[month_key]["pnl"] -= loss_amount

    return dict(monthly_results)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 80)
    print("BACKTEST: VOLUME-VOLATILITY CONTEXT STRATEGY")
    print("=" * 80)
    print()
    print("REGLES:")
    print("  - Setup: 2 candles consecutives")
    print("  - Filtre 1: Volume > 1.2x moyenne")
    print("  - Filtre 2: RSI < 30 (pour UP) ou RSI > 70 (pour DOWN)")
    print("  - Entry: 52.5c | Win: +$90.48 | Loss: -$100")
    print("=" * 80)

    # Periode: 2024-2025
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Resultats Volume-Volatility
    vv_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})
    vv_stats = {"total_signals": 0, "filtered_by_volume": 0, "filtered_by_rsi": 0}

    # Resultats V2 Simple (comparaison)
    v2_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")
        data = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(data)} candles")

        # Backtest Volume-Volatility
        results_vv, stats = backtest_volume_volatility(symbol, data)
        for month, s in results_vv.items():
            for k, v in s.items():
                vv_monthly[month][k] += v
        vv_stats["total_signals"] += stats["total_signals"]
        vv_stats["filtered_by_volume"] += stats["filtered_by_volume"]
        vv_stats["filtered_by_rsi"] += stats["filtered_by_rsi"]

        # Backtest V2 Simple
        results_v2 = backtest_v2_simple(symbol, data)
        for month, s in results_v2.items():
            for k, v in s.items():
                v2_monthly[month][k] += v

    # === RESULTATS VOLUME-VOLATILITY ===
    print("\n" + "=" * 80)
    print("RESULTATS: VOLUME-VOLATILITY STRATEGY")
    print("=" * 80)

    print(f"\n{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'Skip':>6} | {'WR':>6} | {'PnL':>12}")
    print("-" * 80)

    total_trades = 0
    total_wins = 0
    total_pnl = 0
    total_skipped = 0

    for month in sorted(vv_monthly.keys()):
        s = vv_monthly[month]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        print(f"{month:<10} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {s['skipped']:>6} | {wr:>5.1f}% | {pnl_str:>12}")
        total_trades += s["trades"]
        total_wins += s["wins"]
        total_pnl += s["pnl"]
        total_skipped += s["skipped"]

    print("-" * 80)
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
    pnl_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
    print(f"{'TOTAL':<10} | {total_trades:>7} | {total_wins:>6} | {total_trades-total_wins:>6} | {total_skipped:>6} | {total_wr:>5.1f}% | {pnl_str:>12}")

    # === RESULTATS V2 SIMPLE (Comparaison) ===
    print("\n" + "=" * 80)
    print("COMPARAISON: V2 SIMPLE (3 candles consecutives)")
    print("=" * 80)

    v2_total_trades = sum(s["trades"] for s in v2_monthly.values())
    v2_total_wins = sum(s["wins"] for s in v2_monthly.values())
    v2_total_pnl = sum(s["pnl"] for s in v2_monthly.values())
    v2_wr = (v2_total_wins / v2_total_trades * 100) if v2_total_trades > 0 else 0

    print(f"Total Trades: {v2_total_trades:,}")
    print(f"Win Rate: {v2_wr:.1f}%")
    print(f"PnL Total: ${v2_total_pnl:,.0f}")

    # === COMPARAISON ===
    print("\n" + "=" * 80)
    print("COMPARAISON FINALE")
    print("=" * 80)

    print(f"\n{'Strategie':<25} | {'Trades':>10} | {'WR':>8} | {'PnL':>15} | {'PnL/Trade':>10}")
    print("-" * 80)

    vv_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
    v2_pnl_per_trade = v2_total_pnl / v2_total_trades if v2_total_trades > 0 else 0

    vv_pnl_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
    v2_pnl_str = f"+${v2_total_pnl:,.0f}" if v2_total_pnl >= 0 else f"-${abs(v2_total_pnl):,.0f}"

    print(f"{'Volume-Volatility':<25} | {total_trades:>10,} | {total_wr:>7.1f}% | {vv_pnl_str:>15} | ${vv_pnl_per_trade:>9.2f}")
    print(f"{'V2 Simple (3 candles)':<25} | {v2_total_trades:>10,} | {v2_wr:>7.1f}% | {v2_pnl_str:>15} | ${v2_pnl_per_trade:>9.2f}")

    print("\n" + "=" * 80)
    print("STATISTIQUES DE FILTRAGE")
    print("=" * 80)
    print(f"Signaux initiaux (2 candles): {vv_stats['total_signals']:,}")
    print(f"Filtres par Volume: {vv_stats['filtered_by_volume']:,} ({vv_stats['filtered_by_volume']/vv_stats['total_signals']*100:.1f}%)")
    print(f"Filtres par RSI: {vv_stats['filtered_by_rsi']:,} ({vv_stats['filtered_by_rsi']/vv_stats['total_signals']*100:.1f}%)")
    print(f"Trades executes: {total_trades:,} ({total_trades/vv_stats['total_signals']*100:.1f}%)")

    # Verdict
    print("\n" + "=" * 80)
    if total_wr > v2_wr:
        print(f"VERDICT: Volume-Volatility MEILLEUR (+{total_wr - v2_wr:.1f}% WR)")
    else:
        print(f"VERDICT: V2 Simple MEILLEUR (+{v2_wr - total_wr:.1f}% WR)")
    print("=" * 80)


if __name__ == "__main__":
    main()
