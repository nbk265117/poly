#!/usr/bin/env python3
"""
SIMULATION DETAILLEE V7 - $100/trade
BTC + ETH + XRP - 2024-2025
"""

import ccxt
import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def calculate_rsi(prices, period=7):
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
    lowest_low = min(lows[-period:])
    highest_high = max(highs[-period:])
    if highest_high == lowest_low:
        return 50
    return ((closes[-1] - lowest_low) / (highest_high - lowest_low)) * 100


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


def backtest_v7(ohlcv, symbol, bet_amount=100):
    """Backtest V7 Final Strategy"""
    LOOKBACK = 20
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 68
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 75

    # Polymarket payout ~52% entry
    entry_price = 0.52
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    monthly_results = defaultdict(lambda: {
        'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0,
        'up_trades': 0, 'up_wins': 0,
        'down_trades': 0, 'down_wins': 0
    })

    for i in range(LOOKBACK + 1, len(ohlcv) - 1):
        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)
        month_key = timestamp.strftime("%Y-%m")

        closes = [c[4] for c in ohlcv[i-LOOKBACK:i+1]]
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i+1]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i+1]]

        rsi = calculate_rsi(closes, 7)
        stoch = calculate_stoch(highs, lows, closes, 5)

        # Signal V7 Final
        signal = None
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            signal = "DOWN"

        if not signal:
            continue

        # Resultat
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
            monthly_results[month_key]['losses'] += 1
            monthly_results[month_key]['pnl'] -= loss_amount

    return dict(monthly_results)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 100)
    print("SIMULATION DETAILLEE - STRATEGIE V7 FINALE")
    print("=" * 100)
    print()
    print("PARAMETRES:")
    print("  - Mise par trade: $100")
    print("  - Paires: BTC/USDT, ETH/USDT, XRP/USDT")
    print("  - Periode: Janvier 2024 - Decembre 2025")
    print("  - Timeframe: 15 minutes")
    print()
    print("REGLES V7:")
    print("  - Signal UP:   RSI(7) < 38 AND Stoch(5) < 30")
    print("  - Signal DOWN: RSI(7) > 68 AND Stoch(5) > 75")
    print("=" * 100)

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Charger donnees
    all_data = {}
    for symbol in symbols:
        print(f"\nTelechargement {symbol}...")
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"  {len(all_data[symbol])} candles")

    # Backtest par symbol
    results_by_symbol = {}
    for symbol in symbols:
        results_by_symbol[symbol] = backtest_v7(all_data[symbol], symbol)

    # Combiner resultats
    combined = defaultdict(lambda: {
        'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0,
        'up_trades': 0, 'up_wins': 0,
        'down_trades': 0, 'down_wins': 0,
        'btc_pnl': 0, 'eth_pnl': 0, 'xrp_pnl': 0
    })

    for symbol in symbols:
        short_name = symbol.replace('/USDT', '').lower()
        for month, stats in results_by_symbol[symbol].items():
            for key in ['trades', 'wins', 'losses', 'pnl', 'up_trades', 'up_wins', 'down_trades', 'down_wins']:
                combined[month][key] += stats[key]
            combined[month][f'{short_name}_pnl'] = stats['pnl']

    # ============================================
    # AFFICHAGE 2024
    # ============================================
    print("\n" + "=" * 100)
    print("DETAIL MENSUEL 2024")
    print("=" * 100)
    print()
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'WR':>6} | {'BTC PnL':>12} | {'ETH PnL':>12} | {'XRP PnL':>12} | {'TOTAL':>14}")
    print("-" * 100)

    year_2024_pnl = 0
    year_2024_trades = 0
    year_2024_wins = 0

    months_2024 = sorted([m for m in combined.keys() if m.startswith('2024')])

    for month in months_2024:
        s = combined[month]
        wr = (s['wins'] / s['trades'] * 100) if s['trades'] > 0 else 0

        btc_str = f"+${s['btc_pnl']:,.0f}" if s['btc_pnl'] >= 0 else f"-${abs(s['btc_pnl']):,.0f}"
        eth_str = f"+${s['eth_pnl']:,.0f}" if s['eth_pnl'] >= 0 else f"-${abs(s['eth_pnl']):,.0f}"
        xrp_str = f"+${s['xrp_pnl']:,.0f}" if s['xrp_pnl'] >= 0 else f"-${abs(s['xrp_pnl']):,.0f}"
        total_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"

        indicator = " ***" if s['pnl'] >= 15000 else (" *" if s['pnl'] >= 10000 else "")

        print(f"{month:<10} | {s['trades']:>7,} | {s['wins']:>6,} | {wr:>5.1f}% | {btc_str:>12} | {eth_str:>12} | {xrp_str:>12} | {total_str:>14}{indicator}")

        year_2024_pnl += s['pnl']
        year_2024_trades += s['trades']
        year_2024_wins += s['wins']

    print("-" * 100)
    wr_2024 = (year_2024_wins / year_2024_trades * 100) if year_2024_trades > 0 else 0
    total_str = f"+${year_2024_pnl:,.0f}" if year_2024_pnl >= 0 else f"-${abs(year_2024_pnl):,.0f}"
    print(f"{'TOTAL 2024':<10} | {year_2024_trades:>7,} | {year_2024_wins:>6,} | {wr_2024:>5.1f}% | {'':>12} | {'':>12} | {'':>12} | {total_str:>14}")

    # ============================================
    # AFFICHAGE 2025
    # ============================================
    print("\n" + "=" * 100)
    print("DETAIL MENSUEL 2025")
    print("=" * 100)
    print()
    print(f"{'Mois':<10} | {'Trades':>7} | {'Wins':>6} | {'WR':>6} | {'BTC PnL':>12} | {'ETH PnL':>12} | {'XRP PnL':>12} | {'TOTAL':>14}")
    print("-" * 100)

    year_2025_pnl = 0
    year_2025_trades = 0
    year_2025_wins = 0

    months_2025 = sorted([m for m in combined.keys() if m.startswith('2025')])

    for month in months_2025:
        s = combined[month]
        wr = (s['wins'] / s['trades'] * 100) if s['trades'] > 0 else 0

        btc_str = f"+${s['btc_pnl']:,.0f}" if s['btc_pnl'] >= 0 else f"-${abs(s['btc_pnl']):,.0f}"
        eth_str = f"+${s['eth_pnl']:,.0f}" if s['eth_pnl'] >= 0 else f"-${abs(s['eth_pnl']):,.0f}"
        xrp_str = f"+${s['xrp_pnl']:,.0f}" if s['xrp_pnl'] >= 0 else f"-${abs(s['xrp_pnl']):,.0f}"
        total_str = f"+${s['pnl']:,.0f}" if s['pnl'] >= 0 else f"-${abs(s['pnl']):,.0f}"

        indicator = " ***" if s['pnl'] >= 15000 else (" *" if s['pnl'] >= 10000 else "")

        print(f"{month:<10} | {s['trades']:>7,} | {s['wins']:>6,} | {wr:>5.1f}% | {btc_str:>12} | {eth_str:>12} | {xrp_str:>12} | {total_str:>14}{indicator}")

        year_2025_pnl += s['pnl']
        year_2025_trades += s['trades']
        year_2025_wins += s['wins']

    print("-" * 100)
    wr_2025 = (year_2025_wins / year_2025_trades * 100) if year_2025_trades > 0 else 0
    total_str = f"+${year_2025_pnl:,.0f}" if year_2025_pnl >= 0 else f"-${abs(year_2025_pnl):,.0f}"
    print(f"{'TOTAL 2025':<10} | {year_2025_trades:>7,} | {year_2025_wins:>6,} | {wr_2025:>5.1f}% | {'':>12} | {'':>12} | {'':>12} | {total_str:>14}")

    # ============================================
    # RESUME GLOBAL
    # ============================================
    total_trades = year_2024_trades + year_2025_trades
    total_wins = year_2024_wins + year_2025_wins
    total_pnl = year_2024_pnl + year_2025_pnl
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    months_above_15k = sum(1 for s in combined.values() if s['pnl'] >= 15000)
    months_above_10k = sum(1 for s in combined.values() if s['pnl'] >= 10000)
    min_month_pnl = min(s['pnl'] for s in combined.values())
    max_month_pnl = max(s['pnl'] for s in combined.values())
    avg_month_pnl = total_pnl / len(combined)

    print("\n" + "=" * 100)
    print("RESUME GLOBAL - STRATEGIE V7 FINALE")
    print("=" * 100)
    print()
    print(f"  PnL 2024:           +${year_2024_pnl:,.0f}")
    print(f"  PnL 2025:           +${year_2025_pnl:,.0f}")
    print(f"  --------------------------")
    print(f"  PnL TOTAL:          +${total_pnl:,.0f}")
    print()
    print(f"  Trades Total:       {total_trades:,}")
    print(f"  Trades Gagnants:    {total_wins:,}")
    print(f"  Win Rate:           {total_wr:.1f}%")
    print()
    print(f"  Trades/Jour:        ~{total_trades // (24*30)}")
    print(f"  PnL Moyen/Mois:     ${avg_month_pnl:,.0f}")
    print()
    print(f"  Meilleur Mois:      +${max_month_pnl:,.0f}")
    print(f"  Pire Mois:          +${min_month_pnl:,.0f}")
    print()
    print(f"  Mois > $15,000:     {months_above_15k}/24")
    print(f"  Mois > $10,000:     {months_above_10k}/24")
    print()
    print("=" * 100)
    print("LEGENDE: *** = PnL >= $15,000 | * = PnL >= $10,000")
    print("=" * 100)


if __name__ == "__main__":
    main()
