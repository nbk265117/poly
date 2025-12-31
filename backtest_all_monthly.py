#!/usr/bin/env python3
"""
BACKTEST MENSUEL DETAILLE - TOUTES LES STRATEGIES VIABLES
$100 par trade @ 52.5c | Win: +$90.48 | Loss: -$100
"""

import ccxt
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def get_direction(candle):
    return "UP" if candle[4] > candle[1] else "DOWN"


def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def fetch_historical_data(exchange, symbol, start_date, end_date):
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


# ============================================================
# STRATEGIES
# ============================================================

def strategy_v2_simple(ohlcv, bet_amount=100):
    """V2: 3 candles consecutives"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount

    monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

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
            ts = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
            month = ts.strftime("%Y-%m")
            monthly[month]["trades"] += 1
            if signal == actual:
                monthly[month]["wins"] += 1
                monthly[month]["pnl"] += win_profit
            else:
                monthly[month]["losses"] += 1
                monthly[month]["pnl"] -= loss_amount

    return dict(monthly)


def strategy_4_candles(ohlcv, bet_amount=100):
    """4 candles consecutives"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount

    monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

    for i in range(4, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-4])
        d2 = get_direction(ohlcv[i-3])
        d3 = get_direction(ohlcv[i-2])
        d4 = get_direction(ohlcv[i-1])

        signal = None
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN" and d4 == "DOWN":
            signal = "UP"
        elif d1 == "UP" and d2 == "UP" and d3 == "UP" and d4 == "UP":
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            ts = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
            month = ts.strftime("%Y-%m")
            monthly[month]["trades"] += 1
            if signal == actual:
                monthly[month]["wins"] += 1
                monthly[month]["pnl"] += win_profit
            else:
                monthly[month]["losses"] += 1
                monthly[month]["pnl"] -= loss_amount

    return dict(monthly)


def strategy_v3_volume(ohlcv, bet_amount=100, volume_threshold=1.2):
    """V3: 3 candles + Volume > 1.2x"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})

    for i in range(LOOKBACK + 3, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-3])
        d2 = get_direction(ohlcv[i-2])
        d3 = get_direction(ohlcv[i-1])

        signal = None
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN":
            signal = "UP"
        elif d1 == "UP" and d2 == "UP" and d3 == "UP":
            signal = "DOWN"

        if not signal:
            continue

        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i]]
        avg_vol = np.mean(volumes)
        curr_vol = ohlcv[i-1][5]
        rel_vol = curr_vol / avg_vol if avg_vol > 0 else 0

        ts = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month = ts.strftime("%Y-%m")

        if rel_vol < volume_threshold:
            monthly[month]["skipped"] += 1
            continue

        actual = get_direction(ohlcv[i])
        monthly[month]["trades"] += 1
        if signal == actual:
            monthly[month]["wins"] += 1
            monthly[month]["pnl"] += win_profit
        else:
            monthly[month]["losses"] += 1
            monthly[month]["pnl"] -= loss_amount

    return dict(monthly)


def strategy_combined_rsi_vol(ohlcv, bet_amount=100):
    """Combined: 2 candles + RSI extreme + Volume"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})

    for i in range(LOOKBACK, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-2])
        d2 = get_direction(ohlcv[i-1])

        if d1 != d2:
            continue

        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        rsi = calculate_rsi(closes)

        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i]]
        avg_vol = np.mean(volumes)
        curr_vol = ohlcv[i-1][5]
        rel_vol = curr_vol / avg_vol if avg_vol > 0 else 0

        ts = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month = ts.strftime("%Y-%m")

        signal = None
        if d1 == "DOWN" and rsi < 35 and rel_vol > 1.0:
            signal = "UP"
        elif d1 == "UP" and rsi > 65 and rel_vol > 1.0:
            signal = "DOWN"

        if not signal:
            monthly[month]["skipped"] += 1
            continue

        actual = get_direction(ohlcv[i])
        monthly[month]["trades"] += 1
        if signal == actual:
            monthly[month]["wins"] += 1
            monthly[month]["pnl"] += win_profit
        else:
            monthly[month]["losses"] += 1
            monthly[month]["pnl"] -= loss_amount

    return dict(monthly)


def print_monthly_results(name, monthly_data):
    """Affiche les resultats mensuels"""
    print(f"\n{'='*90}")
    print(f"STRATEGIE: {name}")
    print(f"{'='*90}")

    # 2024
    print(f"\n--- 2024 ---")
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'WR':>7} | {'PnL':>12}")
    print("-" * 70)

    year_2024 = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0}
    for month in sorted([m for m in monthly_data.keys() if m.startswith("2024")]):
        s = monthly_data[month]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        print(f"{month:<10} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {wr:>6.1f}% | {pnl_str:>12}")
        year_2024["trades"] += s["trades"]
        year_2024["wins"] += s["wins"]
        year_2024["losses"] += s["losses"]
        year_2024["pnl"] += s["pnl"]

    wr_2024 = (year_2024["wins"] / year_2024["trades"] * 100) if year_2024["trades"] > 0 else 0
    pnl_2024_str = f"+${year_2024['pnl']:,.0f}" if year_2024['pnl'] >= 0 else f"-${abs(year_2024['pnl']):,.0f}"
    print("-" * 70)
    print(f"{'TOTAL 2024':<10} | {year_2024['trades']:>7} | {year_2024['wins']:>6} | {year_2024['losses']:>6} | {wr_2024:>6.1f}% | {pnl_2024_str:>12}")

    # 2025
    print(f"\n--- 2025 ---")
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'WR':>7} | {'PnL':>12}")
    print("-" * 70)

    year_2025 = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0}
    for month in sorted([m for m in monthly_data.keys() if m.startswith("2025")]):
        s = monthly_data[month]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        print(f"{month:<10} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {wr:>6.1f}% | {pnl_str:>12}")
        year_2025["trades"] += s["trades"]
        year_2025["wins"] += s["wins"]
        year_2025["losses"] += s["losses"]
        year_2025["pnl"] += s["pnl"]

    wr_2025 = (year_2025["wins"] / year_2025["trades"] * 100) if year_2025["trades"] > 0 else 0
    pnl_2025_str = f"+${year_2025['pnl']:,.0f}" if year_2025['pnl'] >= 0 else f"-${abs(year_2025['pnl']):,.0f}"
    print("-" * 70)
    print(f"{'TOTAL 2025':<10} | {year_2025['trades']:>7} | {year_2025['wins']:>6} | {year_2025['losses']:>6} | {wr_2025:>6.1f}% | {pnl_2025_str:>12}")

    # Resume
    total_trades = year_2024["trades"] + year_2025["trades"]
    total_wins = year_2024["wins"] + year_2025["wins"]
    total_pnl = year_2024["pnl"] + year_2025["pnl"]
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    months_count = len([m for m in monthly_data.keys() if monthly_data[m]["trades"] > 0])
    avg_monthly_pnl = total_pnl / months_count if months_count > 0 else 0

    positive_months = len([m for m, s in monthly_data.items() if s["pnl"] > 0 and s["trades"] > 0])

    print(f"\n--- RESUME {name} ---")
    print(f"Win Rate Global: {total_wr:.1f}%")
    print(f"PnL Total (2 ans): ${total_pnl:,.0f}")
    print(f"PnL Moyen/Mois: ${avg_monthly_pnl:,.0f}")
    print(f"Trades/Jour: {total_trades / 730:.1f}")
    print(f"Mois Positifs: {positive_months}/{months_count} ({positive_months/months_count*100:.0f}%)")

    return {
        "name": name,
        "total_trades": total_trades,
        "total_wins": total_wins,
        "total_wr": total_wr,
        "total_pnl": total_pnl,
        "avg_monthly_pnl": avg_monthly_pnl,
        "positive_months": positive_months,
        "months_count": months_count
    }


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("BACKTEST MENSUEL DETAILLE - TOUTES LES STRATEGIES VIABLES")
    print("=" * 90)
    print("Periode: 2024-2025 | Paires: BTC, ETH, XRP | Mise: $100/trade @ 52.5c")
    print("Win: +$90.48 | Loss: -$100")
    print("=" * 90)

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Charger les donnees
    all_data = {}
    for symbol in symbols:
        print(f"\nTelechargement {symbol}...", end=" ", flush=True)
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"{len(all_data[symbol])} candles")

    # Strategies a tester
    strategies = [
        ("V2 SIMPLE (3 Candles)", strategy_v2_simple),
        ("4 CANDLES", strategy_4_candles),
        ("V3 VOLUME 1.2x", strategy_v3_volume),
        ("COMBINED RSI+VOL", strategy_combined_rsi_vol),
    ]

    all_results = []

    for name, strategy_fn in strategies:
        # Aggreger les resultats des 3 paires
        combined_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

        for symbol in symbols:
            results = strategy_fn(all_data[symbol])
            for month, stats in results.items():
                combined_monthly[month]["wins"] += stats["wins"]
                combined_monthly[month]["losses"] += stats["losses"]
                combined_monthly[month]["trades"] += stats["trades"]
                combined_monthly[month]["pnl"] += stats["pnl"]

        summary = print_monthly_results(name, dict(combined_monthly))
        all_results.append(summary)

    # Tableau comparatif final
    print("\n" + "=" * 90)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 90)
    print(f"\n{'Strategie':<25} | {'WR':>7} | {'PnL Total':>12} | {'PnL/Mois':>10} | {'Trades/J':>9} | {'Mois+':>6}")
    print("-" * 90)

    for r in sorted(all_results, key=lambda x: x["total_wr"], reverse=True):
        pnl_str = f"+${r['total_pnl']:,.0f}" if r['total_pnl'] >= 0 else f"-${abs(r['total_pnl']):,.0f}"
        pnl_month = f"${r['avg_monthly_pnl']:,.0f}"
        trades_day = r['total_trades'] / 730
        months_pct = f"{r['positive_months']}/{r['months_count']}"
        print(f"{r['name']:<25} | {r['total_wr']:>6.1f}% | {pnl_str:>12} | {pnl_month:>10} | {trades_day:>9.1f} | {months_pct:>6}")

    print("\n" + "=" * 90)
    print("RECOMMANDATION FINALE")
    print("=" * 90)

    best_wr = max(all_results, key=lambda x: x["total_wr"])
    best_pnl = max(all_results, key=lambda x: x["total_pnl"])

    print(f"\n🏆 MEILLEUR WIN RATE: {best_wr['name']} ({best_wr['total_wr']:.1f}%)")
    print(f"💰 MEILLEUR PNL: {best_pnl['name']} (${best_pnl['total_pnl']:,.0f})")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()
