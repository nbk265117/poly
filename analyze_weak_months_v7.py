#!/usr/bin/env python3
"""
Analyse des mois faibles V6 Baseline
Objectif: Trouver des patterns pour ameliorer les 4 mois < $15k
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


def calculate_range_position(highs, lows, closes, period=50):
    if len(highs) < period:
        return 50
    range_high = max(highs[-period:])
    range_low = min(lows[-period:])
    if range_high == range_low:
        return 50
    return ((closes[-1] - range_low) / (range_high - range_low)) * 100


def calculate_ema(prices, period):
    return pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]


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


def analyze_trades(ohlcv, bet_amount=100):
    """Analyse detaillee des trades"""
    LOOKBACK = 60
    RSI_OVERSOLD = 38
    RSI_OVERBOUGHT = 68
    STOCH_OVERSOLD = 30
    STOCH_OVERBOUGHT = 75

    entry_price = 0.52
    shares_per_trade = bet_amount / entry_price
    win_profit = shares_per_trade * (1 - entry_price)
    loss_amount = bet_amount

    trades = []

    for i in range(LOOKBACK + 1, len(ohlcv) - 1):
        timestamp = datetime.fromtimestamp(ohlcv[i][0] / 1000, tz=timezone.utc)

        closes = [c[4] for c in ohlcv[i-LOOKBACK:i+1]]
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i+1]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i+1]]
        volumes = [c[5] for c in ohlcv[i-LOOKBACK:i+1]]

        rsi = calculate_rsi(closes, 7)
        stoch = calculate_stoch(highs, lows, closes, 5)
        range_pos = calculate_range_position(highs, lows, closes, 50)

        signal = None
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            signal = "DOWN"

        if not signal:
            continue

        avg_volume = np.mean(volumes[:-1])
        rel_volume = volumes[-1] / avg_volume if avg_volume > 0 else 1

        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)
        trend = "UP" if ema20 > ema50 else "DOWN"

        actual = "UP" if ohlcv[i+1][4] > ohlcv[i+1][1] else "DOWN"
        is_win = (signal == actual)

        trades.append({
            'timestamp': timestamp,
            'month': timestamp.strftime("%Y-%m"),
            'signal': signal,
            'rsi': rsi,
            'stoch': stoch,
            'range_pos': range_pos,
            'rel_volume': rel_volume,
            'trend': trend,
            'is_win': is_win,
            'pnl': win_profit if is_win else -loss_amount
        })

    return pd.DataFrame(trades)


def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("ANALYSE DES MOIS FAIBLES - V6 BASELINE")
    print("=" * 90)
    print()
    print("Mois faibles identifies: 2024-02, 2025-06, 2025-08, 2025-10")
    print()

    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    all_data = {}
    for symbol in symbols:
        print(f"Telechargement {symbol}...")
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)

    # Analyser tous les trades
    all_trades = []
    for symbol in symbols:
        df = analyze_trades(all_data[symbol])
        df['symbol'] = symbol.replace('/USDT', '')
        all_trades.append(df)

    trades_df = pd.concat(all_trades, ignore_index=True)

    weak_months = ['2024-02', '2025-06', '2025-08', '2025-10']
    strong_months = [m for m in trades_df['month'].unique() if m not in weak_months]

    # Statistiques globales
    print("\n" + "=" * 90)
    print("COMPARAISON: MOIS FORTS vs MOIS FAIBLES")
    print("=" * 90)

    weak_df = trades_df[trades_df['month'].isin(weak_months)]
    strong_df = trades_df[trades_df['month'].isin(strong_months)]

    print(f"\n{'Metrique':<30} | {'Mois Forts':>15} | {'Mois Faibles':>15}")
    print("-" * 70)

    # WR global
    strong_wr = strong_df['is_win'].mean() * 100
    weak_wr = weak_df['is_win'].mean() * 100
    print(f"{'Win Rate global':<30} | {strong_wr:>14.1f}% | {weak_wr:>14.1f}%")

    # WR par signal
    for sig in ['UP', 'DOWN']:
        s_wr = strong_df[strong_df['signal'] == sig]['is_win'].mean() * 100
        w_wr = weak_df[weak_df['signal'] == sig]['is_win'].mean() * 100
        print(f"{'WR Signal ' + sig:<30} | {s_wr:>14.1f}% | {w_wr:>14.1f}%")

    # WR par trend alignment
    for sig in ['UP', 'DOWN']:
        # Avec tendance
        s_with = strong_df[(strong_df['signal'] == sig) & (strong_df['trend'] == sig)]['is_win'].mean() * 100
        w_with = weak_df[(weak_df['signal'] == sig) & (weak_df['trend'] == sig)]['is_win'].mean() * 100
        print(f"{'WR ' + sig + ' avec tendance':<30} | {s_with:>14.1f}% | {w_with:>14.1f}%")

        # Contre tendance
        opp = 'DOWN' if sig == 'UP' else 'UP'
        s_against = strong_df[(strong_df['signal'] == sig) & (strong_df['trend'] == opp)]['is_win'].mean() * 100
        w_against = weak_df[(weak_df['signal'] == sig) & (weak_df['trend'] == opp)]['is_win'].mean() * 100
        print(f"{'WR ' + sig + ' contre tendance':<30} | {s_against:>14.1f}% | {w_against:>14.1f}%")

    # Analyse par Range Position
    print("\n" + "=" * 90)
    print("ANALYSE PAR RANGE POSITION (ICT)")
    print("=" * 90)

    ranges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]

    for signal in ['UP', 'DOWN']:
        print(f"\n--- Signal {signal} ---")
        print(f"{'Range Position':<20} | {'WR Forts':>10} | {'WR Faibles':>12} | {'Diff':>8} | {'Trades Faibles':>14}")
        print("-" * 75)

        for low, high in ranges:
            mask = (trades_df['range_pos'] >= low) & (trades_df['range_pos'] < high) & (trades_df['signal'] == signal)

            s_sub = strong_df[(strong_df['range_pos'] >= low) & (strong_df['range_pos'] < high) & (strong_df['signal'] == signal)]
            w_sub = weak_df[(weak_df['range_pos'] >= low) & (weak_df['range_pos'] < high) & (weak_df['signal'] == signal)]

            s_wr = s_sub['is_win'].mean() * 100 if len(s_sub) > 0 else 0
            w_wr = w_sub['is_win'].mean() * 100 if len(w_sub) > 0 else 0
            diff = w_wr - s_wr

            print(f"{low:>3}% - {high:<3}%          | {s_wr:>9.1f}% | {w_wr:>11.1f}% | {diff:>+7.1f}% | {len(w_sub):>14}")

    # Analyse par RSI level
    print("\n" + "=" * 90)
    print("ANALYSE PAR RSI LEVEL")
    print("=" * 90)

    print("\n--- Signal UP (RSI < 38) ---")
    rsi_ranges = [(0, 20), (20, 25), (25, 30), (30, 35), (35, 38)]
    print(f"{'RSI Level':<20} | {'WR Forts':>10} | {'WR Faibles':>12} | {'Diff':>8} | {'Trades Faibles':>14}")
    print("-" * 75)

    for low, high in rsi_ranges:
        s_sub = strong_df[(strong_df['rsi'] >= low) & (strong_df['rsi'] < high) & (strong_df['signal'] == 'UP')]
        w_sub = weak_df[(weak_df['rsi'] >= low) & (weak_df['rsi'] < high) & (weak_df['signal'] == 'UP')]

        s_wr = s_sub['is_win'].mean() * 100 if len(s_sub) > 0 else 0
        w_wr = w_sub['is_win'].mean() * 100 if len(w_sub) > 0 else 0
        diff = w_wr - s_wr

        print(f"{low:>3} - {high:<3}            | {s_wr:>9.1f}% | {w_wr:>11.1f}% | {diff:>+7.1f}% | {len(w_sub):>14}")

    print("\n--- Signal DOWN (RSI > 68) ---")
    rsi_ranges = [(68, 72), (72, 75), (75, 80), (80, 85), (85, 100)]
    print(f"{'RSI Level':<20} | {'WR Forts':>10} | {'WR Faibles':>12} | {'Diff':>8} | {'Trades Faibles':>14}")
    print("-" * 75)

    for low, high in rsi_ranges:
        s_sub = strong_df[(strong_df['rsi'] >= low) & (strong_df['rsi'] < high) & (strong_df['signal'] == 'DOWN')]
        w_sub = weak_df[(weak_df['rsi'] >= low) & (weak_df['rsi'] < high) & (weak_df['signal'] == 'DOWN')]

        s_wr = s_sub['is_win'].mean() * 100 if len(s_sub) > 0 else 0
        w_wr = w_sub['is_win'].mean() * 100 if len(w_sub) > 0 else 0
        diff = w_wr - s_wr

        print(f"{low:>3} - {high:<3}            | {s_wr:>9.1f}% | {w_wr:>11.1f}% | {diff:>+7.1f}% | {len(w_sub):>14}")

    # Analyse par symbol
    print("\n" + "=" * 90)
    print("ANALYSE PAR SYMBOL")
    print("=" * 90)

    print(f"\n{'Symbol':<10} | {'WR Forts':>10} | {'WR Faibles':>12} | {'Diff':>8} | {'PnL Faibles':>12}")
    print("-" * 65)

    for symbol in ['BTC', 'ETH', 'XRP']:
        s_sub = strong_df[strong_df['symbol'] == symbol]
        w_sub = weak_df[weak_df['symbol'] == symbol]

        s_wr = s_sub['is_win'].mean() * 100 if len(s_sub) > 0 else 0
        w_wr = w_sub['is_win'].mean() * 100 if len(w_sub) > 0 else 0
        diff = w_wr - s_wr
        w_pnl = w_sub['pnl'].sum()

        pnl_str = f"+${w_pnl:,.0f}" if w_pnl >= 0 else f"-${abs(w_pnl):,.0f}"
        print(f"{symbol:<10} | {s_wr:>9.1f}% | {w_wr:>11.1f}% | {diff:>+7.1f}% | {pnl_str:>12}")

    # Proposition d'amelioration
    print("\n" + "=" * 90)
    print("PROPOSITIONS D'AMELIORATION")
    print("=" * 90)

    # Tester: Filtrer les trades problematiques
    print("\n--- Test: Filtrer trades problematiques dans mois faibles ---\n")

    # Filtre 1: Exclure DOWN avec RSI 68-72 en mois faibles
    print("Filtre 1: Exclure DOWN avec RSI 68-72")
    excluded = weak_df[(weak_df['signal'] == 'DOWN') & (weak_df['rsi'] >= 68) & (weak_df['rsi'] < 72)]
    print(f"  Trades exclus: {len(excluded)}")
    print(f"  WR de ces trades: {excluded['is_win'].mean()*100:.1f}%")
    print(f"  PnL evite: ${excluded['pnl'].sum():,.0f}")

    # Filtre 2: Exclure UP contre tendance avec Range > 60
    print("\nFiltre 2: Exclure UP contre tendance avec Range > 60%")
    excluded2 = weak_df[(weak_df['signal'] == 'UP') & (weak_df['trend'] == 'DOWN') & (weak_df['range_pos'] > 60)]
    print(f"  Trades exclus: {len(excluded2)}")
    print(f"  WR de ces trades: {excluded2['is_win'].mean()*100:.1f}%")
    print(f"  PnL evite: ${excluded2['pnl'].sum():,.0f}")

    # Filtre 3: Exclure XRP contre tendance
    print("\nFiltre 3: Exclure XRP contre tendance")
    excluded3 = weak_df[(weak_df['symbol'] == 'XRP') & (weak_df['signal'] != weak_df['trend'])]
    print(f"  Trades exclus: {len(excluded3)}")
    print(f"  WR de ces trades: {excluded3['is_win'].mean()*100:.1f}%")
    print(f"  PnL evite: ${excluded3['pnl'].sum():,.0f}")


if __name__ == "__main__":
    main()
