#!/usr/bin/env python3
"""
BACKTEST STRATEGIE V2 - SIMULATION MENSUELLE 2024-2025
Mise: $100 par trade @ 52.5c
Regle: 3 candles consecutives -> parier inverse
"""

import ccxt
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

def get_direction(candle):
    """UP si close > open, sinon DOWN"""
    return "UP" if candle[4] > candle[1] else "DOWN"

def fetch_historical_data(exchange, symbol, start_date, end_date):
    """Récupère les données historiques par chunks"""
    all_data = []
    current = start_date

    while current < end_date:
        since = int(current.timestamp() * 1000)
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            # Avancer au dernier timestamp + 1
            current = datetime.fromtimestamp(ohlcv[-1][0] / 1000, tz=timezone.utc) + timedelta(minutes=15)
            time.sleep(0.2)  # Rate limit
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            break

    return all_data

def backtest_v2_monthly(symbol, ohlcv, bet_amount=100):
    """Backtest V2 avec résultats mensuels"""

    # Entry @ 52.5c
    entry_price = 0.525
    shares_per_trade = bet_amount / entry_price  # ~190.48 shares
    win_profit = shares_per_trade * (1 - entry_price)  # ~$90.48
    loss_amount = bet_amount  # -$100

    monthly_results = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

    for i in range(3, len(ohlcv) - 1):
        # Directions des 3 dernières candles
        d1 = get_direction(ohlcv[i-3])
        d2 = get_direction(ohlcv[i-2])
        d3 = get_direction(ohlcv[i-1])

        signal = None

        # 3 DOWN -> UP
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN":
            signal = "UP"
        # 3 UP -> DOWN
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
    print("BACKTEST STRATEGIE V2 - SIMULATION $100/TRADE")
    print("Regle: 3 candles consecutives -> parier inverse")
    print("Entry: 52.5c | Win: +$90.48 | Loss: -$100")
    print("=" * 80)

    # Périodes
    start_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_2024 = datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc)
    start_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_2025 = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    all_monthly = defaultdict(lambda: {"wins": 0, "losses": 0, "trades": 0, "pnl": 0})

    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")

        # 2024
        print(f"  2024...", end=" ", flush=True)
        data_2024 = fetch_historical_data(exchange, symbol, start_2024, end_2024)
        print(f"{len(data_2024)} candles")

        # 2025
        print(f"  2025...", end=" ", flush=True)
        data_2025 = fetch_historical_data(exchange, symbol, start_2025, end_2025)
        print(f"{len(data_2025)} candles")

        # Combine
        all_data = data_2024 + data_2025

        # Backtest
        results = backtest_v2_monthly(symbol, all_data, bet_amount=100)

        # Aggregate
        for month, stats in results.items():
            all_monthly[month]["wins"] += stats["wins"]
            all_monthly[month]["losses"] += stats["losses"]
            all_monthly[month]["trades"] += stats["trades"]
            all_monthly[month]["pnl"] += stats["pnl"]

    # Affichage résultats
    print("\n" + "=" * 80)
    print("RESULTATS MENSUELS - 3 PAIRES COMBINEES (BTC + ETH + XRP)")
    print("=" * 80)

    # 2024
    print("\n" + "-" * 80)
    print("2024")
    print("-" * 80)
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'WR':>6} | {'PnL':>12}")
    print("-" * 80)

    year_2024_pnl = 0
    year_2024_trades = 0
    year_2024_wins = 0

    for month in sorted([m for m in all_monthly.keys() if m.startswith("2024")]):
        stats = all_monthly[month]
        wr = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0
        pnl_str = f"+${stats['pnl']:,.0f}" if stats['pnl'] >= 0 else f"-${abs(stats['pnl']):,.0f}"
        print(f"{month:<10} | {stats['trades']:>7} | {stats['wins']:>6} | {stats['losses']:>6} | {wr:>5.1f}% | {pnl_str:>12}")
        year_2024_pnl += stats["pnl"]
        year_2024_trades += stats["trades"]
        year_2024_wins += stats["wins"]

    print("-" * 80)
    wr_2024 = (year_2024_wins / year_2024_trades * 100) if year_2024_trades > 0 else 0
    pnl_2024_str = f"+${year_2024_pnl:,.0f}" if year_2024_pnl >= 0 else f"-${abs(year_2024_pnl):,.0f}"
    print(f"{'TOTAL 2024':<10} | {year_2024_trades:>7} | {year_2024_wins:>6} | {year_2024_trades - year_2024_wins:>6} | {wr_2024:>5.1f}% | {pnl_2024_str:>12}")

    # 2025
    print("\n" + "-" * 80)
    print("2025")
    print("-" * 80)
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'Losses':>6} | {'WR':>6} | {'PnL':>12}")
    print("-" * 80)

    year_2025_pnl = 0
    year_2025_trades = 0
    year_2025_wins = 0

    for month in sorted([m for m in all_monthly.keys() if m.startswith("2025")]):
        stats = all_monthly[month]
        wr = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0
        pnl_str = f"+${stats['pnl']:,.0f}" if stats['pnl'] >= 0 else f"-${abs(stats['pnl']):,.0f}"
        print(f"{month:<10} | {stats['trades']:>7} | {stats['wins']:>6} | {stats['losses']:>6} | {wr:>5.1f}% | {pnl_str:>12}")
        year_2025_pnl += stats["pnl"]
        year_2025_trades += stats["trades"]
        year_2025_wins += stats["wins"]

    print("-" * 80)
    wr_2025 = (year_2025_wins / year_2025_trades * 100) if year_2025_trades > 0 else 0
    pnl_2025_str = f"+${year_2025_pnl:,.0f}" if year_2025_pnl >= 0 else f"-${abs(year_2025_pnl):,.0f}"
    print(f"{'TOTAL 2025':<10} | {year_2025_trades:>7} | {year_2025_wins:>6} | {year_2025_trades - year_2025_wins:>6} | {wr_2025:>5.1f}% | {pnl_2025_str:>12}")

    # Résumé global
    print("\n" + "=" * 80)
    print("RESUME GLOBAL")
    print("=" * 80)

    total_pnl = year_2024_pnl + year_2025_pnl
    total_trades = year_2024_trades + year_2025_trades
    total_wins = year_2024_wins + year_2025_wins
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    months_count = len([m for m in all_monthly.keys() if all_monthly[m]["trades"] > 0])
    avg_monthly_pnl = total_pnl / months_count if months_count > 0 else 0
    avg_monthly_trades = total_trades / months_count if months_count > 0 else 0

    print(f"Periode: 2024-2025 ({months_count} mois)")
    print(f"Total Trades: {total_trades:,}")
    print(f"Total Wins: {total_wins:,}")
    print(f"Win Rate Global: {total_wr:.1f}%")
    print(f"PnL Total: ${total_pnl:,.0f}")
    print(f"PnL Moyen/Mois: ${avg_monthly_pnl:,.0f}")
    print(f"Trades Moyen/Mois: {avg_monthly_trades:,.0f}")
    print(f"Trades/Jour (moyenne): {avg_monthly_trades/30:.1f}")

    # Meilleur et pire mois
    sorted_months = sorted(all_monthly.items(), key=lambda x: x[1]["pnl"])
    worst = sorted_months[0]
    best = sorted_months[-1]

    print(f"\nMeilleur mois: {best[0]} (+${best[1]['pnl']:,.0f})")
    print(f"Pire mois: {worst[0]} (${worst[1]['pnl']:,.0f})")

    # Mois positifs vs négatifs
    positive_months = len([m for m in all_monthly.values() if m["pnl"] > 0])
    negative_months = len([m for m in all_monthly.values() if m["pnl"] <= 0])
    print(f"Mois positifs: {positive_months}/{months_count} ({positive_months/months_count*100:.0f}%)")

    print("=" * 80)

if __name__ == "__main__":
    main()
