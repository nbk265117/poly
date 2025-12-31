#!/usr/bin/env python3
"""
BACKTEST: V3 - 3 Candles + Volume Context
Combine V2 Simple avec filtre Volume

REGLES:
  - 3 candles DOWN consecutives + Volume > seuil -> UP
  - 3 candles UP consecutives + Volume > seuil -> DOWN
  - Volume faible -> SKIP
"""

import ccxt
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import defaultdict


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


def backtest_v3_volume(symbol, ohlcv, bet_amount=100, volume_threshold=1.0):
    """
    Backtest V3: 3 candles + Volume
    """
    LOOKBACK = 20

    entry_price = 0.525
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    monthly_results = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})

    total_signals = 0
    filtered_by_volume = 0

    for i in range(LOOKBACK + 3, len(ohlcv) - 1):
        # Directions des 3 dernieres candles fermees
        d1 = get_direction(ohlcv[i-3])
        d2 = get_direction(ohlcv[i-2])
        d3 = get_direction(ohlcv[i-1])

        signal = None

        # 3 DOWN -> UP
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN":
            signal = "UP"
            total_signals += 1
        # 3 UP -> DOWN
        elif d1 == "UP" and d2 == "UP" and d3 == "UP":
            signal = "DOWN"
            total_signals += 1

        if not signal:
            continue

        # Calculer le volume relatif
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i]]
        avg_volume = np.mean(volumes)
        current_volume = ohlcv[i-1][5]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 0

        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month_key = timestamp.strftime("%Y-%m")

        # Filtre Volume
        if relative_volume < volume_threshold:
            filtered_by_volume += 1
            monthly_results[month_key]["skipped"] += 1
            continue

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
        "filtered_by_volume": filtered_by_volume
    }


def backtest_v2_simple(symbol, ohlcv, bet_amount=100):
    """V2 Simple pour comparaison"""
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

    print("=" * 90)
    print("BACKTEST: V3 - 3 CANDLES + VOLUME CONTEXT")
    print("=" * 90)

    # Periode
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Charger les donnees une seule fois
    all_data = {}
    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(all_data[symbol])} candles")

    # Tester differents seuils de volume
    volume_thresholds = [0.8, 1.0, 1.2, 1.5, 2.0]

    print("\n" + "=" * 90)
    print("TEST DIFFERENTS SEUILS DE VOLUME")
    print("=" * 90)

    results_by_threshold = {}

    for threshold in volume_thresholds:
        v3_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0})
        v3_stats = {"total_signals": 0, "filtered_by_volume": 0}

        for symbol in symbols:
            results, stats = backtest_v3_volume(symbol, all_data[symbol], volume_threshold=threshold)
            for month, s in results.items():
                for k, v in s.items():
                    v3_monthly[month][k] += v
            v3_stats["total_signals"] += stats["total_signals"]
            v3_stats["filtered_by_volume"] += stats["filtered_by_volume"]

        total_trades = sum(s["trades"] for s in v3_monthly.values())
        total_wins = sum(s["wins"] for s in v3_monthly.values())
        total_pnl = sum(s["pnl"] for s in v3_monthly.values())
        total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

        results_by_threshold[threshold] = {
            "trades": total_trades,
            "wins": total_wins,
            "wr": total_wr,
            "pnl": total_pnl,
            "monthly": dict(v3_monthly),
            "stats": v3_stats
        }

    # V2 Simple pour comparaison
    v2_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})
    for symbol in symbols:
        results = backtest_v2_simple(symbol, all_data[symbol])
        for month, s in results.items():
            for k, v in s.items():
                v2_monthly[month][k] += v

    v2_total_trades = sum(s["trades"] for s in v2_monthly.values())
    v2_total_wins = sum(s["wins"] for s in v2_monthly.values())
    v2_total_pnl = sum(s["pnl"] for s in v2_monthly.values())
    v2_wr = (v2_total_wins / v2_total_trades * 100) if v2_total_trades > 0 else 0

    # Afficher comparaison
    print(f"\n{'Strategie':<30} | {'Trades':>10} | {'WR':>8} | {'PnL':>15} | {'PnL/Trade':>10}")
    print("-" * 90)

    # V2 Simple (baseline)
    v2_ppt = v2_total_pnl / v2_total_trades if v2_total_trades > 0 else 0
    v2_pnl_str = f"+${v2_total_pnl:,.0f}" if v2_total_pnl >= 0 else f"-${abs(v2_total_pnl):,.0f}"
    print(f"{'V2 Simple (sans volume)':<30} | {v2_total_trades:>10,} | {v2_wr:>7.1f}% | {v2_pnl_str:>15} | ${v2_ppt:>9.2f}")

    print("-" * 90)

    # V3 avec differents seuils
    best_threshold = None
    best_wr = 0

    for threshold in volume_thresholds:
        r = results_by_threshold[threshold]
        ppt = r["pnl"] / r["trades"] if r["trades"] > 0 else 0
        pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"

        label = f"V3 (Volume > {threshold}x)"
        wr_diff = r["wr"] - v2_wr
        wr_indicator = f"(+{wr_diff:.1f}%)" if wr_diff > 0 else f"({wr_diff:.1f}%)"

        print(f"{label:<30} | {r['trades']:>10,} | {r['wr']:>7.1f}% | {pnl_str:>15} | ${ppt:>9.2f} {wr_indicator}")

        if r["wr"] > best_wr and r["trades"] > 1000:  # Au moins 1000 trades
            best_wr = r["wr"]
            best_threshold = threshold

    # Detail du meilleur seuil
    if best_threshold:
        print("\n" + "=" * 90)
        print(f"DETAIL: MEILLEUR SEUIL = Volume > {best_threshold}x")
        print("=" * 90)

        r = results_by_threshold[best_threshold]

        print(f"\n{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'Skip':>6} | {'WR':>6} | {'PnL':>12}")
        print("-" * 80)

        for month in sorted(r["monthly"].keys()):
            s = r["monthly"][month]
            wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
            pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
            print(f"{month:<10} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {s['skipped']:>6} | {wr:>5.1f}% | {pnl_str:>12}")

        print("-" * 80)
        pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"
        print(f"{'TOTAL':<10} | {r['trades']:>7} | {r['wins']:>6} | {r['trades']-r['wins']:>6} | {r['stats']['filtered_by_volume']:>6} | {r['wr']:>5.1f}% | {pnl_str:>12}")

        # Stats
        print(f"\nSignaux (3 candles): {r['stats']['total_signals']:,}")
        print(f"Filtres par volume: {r['stats']['filtered_by_volume']:,} ({r['stats']['filtered_by_volume']/r['stats']['total_signals']*100:.1f}%)")
        print(f"Trades executes: {r['trades']:,} ({r['trades']/r['stats']['total_signals']*100:.1f}%)")

        # Mois positifs/negatifs
        positive_months = len([m for m, s in r["monthly"].items() if s["pnl"] > 0])
        total_months = len(r["monthly"])
        print(f"Mois positifs: {positive_months}/{total_months} ({positive_months/total_months*100:.0f}%)")

        # Comparaison finale
        print("\n" + "=" * 90)
        print("VERDICT FINAL")
        print("=" * 90)

        improvement_wr = r["wr"] - v2_wr
        improvement_ppt = (r["pnl"] / r["trades"]) - (v2_total_pnl / v2_total_trades)
        trade_reduction = (1 - r["trades"] / v2_total_trades) * 100

        print(f"Win Rate: {r['wr']:.1f}% vs {v2_wr:.1f}% (V2) = +{improvement_wr:.1f}%")
        print(f"PnL/Trade: ${r['pnl']/r['trades']:.2f} vs ${v2_total_pnl/v2_total_trades:.2f} (V2) = +${improvement_ppt:.2f}")
        print(f"Trades: {r['trades']:,} vs {v2_total_trades:,} (V2) = -{trade_reduction:.0f}%")
        print(f"PnL Total: ${r['pnl']:,.0f} vs ${v2_total_pnl:,.0f} (V2)")

        if r["wr"] > v2_wr:
            print(f"\n✅ V3 (Volume > {best_threshold}x) est PLUS PRECIS que V2")
        if r["pnl"] / r["trades"] > v2_total_pnl / v2_total_trades:
            print(f"✅ V3 a un MEILLEUR profit par trade")
        if r["pnl"] < v2_total_pnl:
            print(f"⚠️  MAIS V2 genere plus de profit TOTAL (plus de trades)")


if __name__ == "__main__":
    main()
