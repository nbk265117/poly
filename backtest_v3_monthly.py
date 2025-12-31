#!/usr/bin/env python3
"""
BACKTEST V3 - DETAIL MENSUEL 2024-2025
Strategie: 3 candles consecutives + Volume > 1.2x
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


def backtest_v3(ohlcv, bet_amount=100, volume_threshold=1.2):
    """
    Backtest V3: 3 candles + Volume > 1.2x
    """
    LOOKBACK = 20

    entry_price = 0.525
    shares_per_trade = bet_amount / entry_price  # ~190.48 shares
    win_profit = shares_per_trade * (1 - entry_price)  # ~$90.48
    loss_amount = bet_amount  # -$100

    monthly_results = defaultdict(lambda: {
        "wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0
    })

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

        # Volume filter
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i]]
        avg_volume = np.mean(volumes)
        current_volume = ohlcv[i-1][5]
        relative_volume = current_volume / avg_volume if avg_volume > 0 else 0

        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month_key = timestamp.strftime("%Y-%m")

        if relative_volume < volume_threshold:
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

    return dict(monthly_results)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 80)
    print("BACKTEST V3 - STRATEGIE 3 CANDLES + VOLUME > 1.2x")
    print("=" * 80)
    print()
    print("REGLES:")
    print("  - 3 candles DOWN consecutives + Volume > 1.2x -> BET UP")
    print("  - 3 candles UP consecutives + Volume > 1.2x -> BET DOWN")
    print("  - Volume < 1.2x -> SKIP (pas de trade)")
    print()
    print("MISE: $100 par trade @ 52.5c")
    print("  - Win: +$90.48")
    print("  - Loss: -$100.00")
    print("=" * 80)

    # Periode
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Resultats combines
    all_monthly = defaultdict(lambda: {
        "wins": 0, "losses": 0, "trades": 0, "pnl": 0, "skipped": 0
    })

    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")
        data = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(data)} candles")

        results = backtest_v3(data, bet_amount=100, volume_threshold=1.2)

        for month, stats in results.items():
            for k, v in stats.items():
                all_monthly[month][k] += v

    # ===== RESULTATS 2024 =====
    print("\n" + "=" * 80)
    print("RESULTATS 2024 - V3 (3 CANDLES + VOLUME > 1.2x)")
    print("=" * 80)
    print(f"\n{'Mois':<12} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'Skip':>6} | {'WR':>7} | {'PnL':>12}")
    print("-" * 80)

    year_2024_pnl = 0
    year_2024_trades = 0
    year_2024_wins = 0
    year_2024_skipped = 0

    for month in sorted([m for m in all_monthly.keys() if m.startswith("2024")]):
        s = all_monthly[month]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        print(f"{month:<12} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {s['skipped']:>6} | {wr:>6.1f}% | {pnl_str:>12}")
        year_2024_pnl += s["pnl"]
        year_2024_trades += s["trades"]
        year_2024_wins += s["wins"]
        year_2024_skipped += s["skipped"]

    print("-" * 80)
    wr_2024 = (year_2024_wins / year_2024_trades * 100) if year_2024_trades > 0 else 0
    pnl_2024_str = f"+${year_2024_pnl:,.0f}" if year_2024_pnl >= 0 else f"-${abs(year_2024_pnl):,.0f}"
    print(f"{'TOTAL 2024':<12} | {year_2024_trades:>7} | {year_2024_wins:>6} | {year_2024_trades-year_2024_wins:>6} | {year_2024_skipped:>6} | {wr_2024:>6.1f}% | {pnl_2024_str:>12}")

    # ===== RESULTATS 2025 =====
    print("\n" + "=" * 80)
    print("RESULTATS 2025 - V3 (3 CANDLES + VOLUME > 1.2x)")
    print("=" * 80)
    print(f"\n{'Mois':<12} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'Skip':>6} | {'WR':>7} | {'PnL':>12}")
    print("-" * 80)

    year_2025_pnl = 0
    year_2025_trades = 0
    year_2025_wins = 0
    year_2025_skipped = 0

    for month in sorted([m for m in all_monthly.keys() if m.startswith("2025")]):
        s = all_monthly[month]
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        pnl_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"
        print(f"{month:<12} | {s['trades']:>7} | {s['wins']:>6} | {s['losses']:>6} | {s['skipped']:>6} | {wr:>6.1f}% | {pnl_str:>12}")
        year_2025_pnl += s["pnl"]
        year_2025_trades += s["trades"]
        year_2025_wins += s["wins"]
        year_2025_skipped += s["skipped"]

    print("-" * 80)
    wr_2025 = (year_2025_wins / year_2025_trades * 100) if year_2025_trades > 0 else 0
    pnl_2025_str = f"+${year_2025_pnl:,.0f}" if year_2025_pnl >= 0 else f"-${abs(year_2025_pnl):,.0f}"
    print(f"{'TOTAL 2025':<12} | {year_2025_trades:>7} | {year_2025_wins:>6} | {year_2025_trades-year_2025_wins:>6} | {year_2025_skipped:>6} | {wr_2025:>6.1f}% | {pnl_2025_str:>12}")

    # ===== RESUME GLOBAL =====
    print("\n" + "=" * 80)
    print("RESUME GLOBAL V3")
    print("=" * 80)

    total_pnl = year_2024_pnl + year_2025_pnl
    total_trades = year_2024_trades + year_2025_trades
    total_wins = year_2024_wins + year_2025_wins
    total_skipped = year_2024_skipped + year_2025_skipped
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    months_count = len([m for m in all_monthly.keys() if all_monthly[m]["trades"] > 0])
    avg_monthly_pnl = total_pnl / months_count if months_count > 0 else 0
    avg_monthly_trades = total_trades / months_count if months_count > 0 else 0

    print(f"\nPeriode: 2024-2025 ({months_count} mois)")
    print(f"Total Trades: {total_trades:,}")
    print(f"Total Wins: {total_wins:,}")
    print(f"Total Skipped: {total_skipped:,}")
    print(f"Win Rate Global: {total_wr:.1f}%")
    print(f"PnL Total: ${total_pnl:,.0f}")
    print(f"PnL Moyen/Mois: ${avg_monthly_pnl:,.0f}")
    print(f"Trades Moyen/Mois: {avg_monthly_trades:,.0f}")
    print(f"Trades/Jour (moyenne): {avg_monthly_trades/30:.1f}")

    # Meilleur et pire mois
    sorted_months = sorted(
        [(m, s) for m, s in all_monthly.items() if s["trades"] > 0],
        key=lambda x: x[1]["pnl"]
    )
    worst = sorted_months[0]
    best = sorted_months[-1]

    print(f"\nMeilleur mois: {best[0]} (+${best[1]['pnl']:,.0f}) - WR {best[1]['wins']/best[1]['trades']*100:.1f}%")
    print(f"Pire mois: {worst[0]} (${worst[1]['pnl']:,.0f}) - WR {worst[1]['wins']/worst[1]['trades']*100:.1f}%")

    # Mois positifs vs negatifs
    positive_months = len([m for m, s in all_monthly.items() if s["pnl"] > 0 and s["trades"] > 0])
    negative_months = len([m for m, s in all_monthly.items() if s["pnl"] <= 0 and s["trades"] > 0])
    print(f"Mois positifs: {positive_months}/{months_count} ({positive_months/months_count*100:.0f}%)")

    # PnL par trade
    pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
    print(f"PnL/Trade: ${pnl_per_trade:.2f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
