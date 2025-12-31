#!/usr/bin/env python3
"""
BACKTEST COMPLET - TOUTES LES STRATEGIES
Compare toutes les strategies pour trouver la meilleure
"""

import ccxt
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from collections import defaultdict


def get_direction(candle):
    """UP si close > open, sinon DOWN"""
    return "UP" if candle[4] > candle[1] else "DOWN"


def calculate_rsi(closes, period=14):
    """Calcule le RSI"""
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


def calculate_macd(closes, fast=12, slow=26, signal=9):
    """Calcule MACD, Signal et Histogram"""
    if len(closes) < slow + signal:
        return 0, 0, 0

    # EMA fast
    ema_fast = np.mean(closes[-fast:])
    # EMA slow
    ema_slow = np.mean(closes[-slow:])
    # MACD line
    macd_line = ema_fast - ema_slow
    # Signal line (simplified)
    signal_line = np.mean(closes[-(signal):]) - np.mean(closes[-(slow):])
    # Histogram
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_bollinger(closes, period=20, std_dev=2):
    """Calcule les Bollinger Bands"""
    if len(closes) < period:
        return 0, 0, 0

    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)

    return upper, sma, lower


def calculate_ema(closes, period):
    """Calcule l'EMA"""
    if len(closes) < period:
        return np.mean(closes)

    multiplier = 2 / (period + 1)
    ema = closes[-period]
    for price in closes[-period+1:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    return ema


def calculate_atr(highs, lows, closes, period=14):
    """Calcule l'ATR"""
    if len(highs) < period + 1:
        return 0

    tr_list = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        tr_list.append(tr)

    return np.mean(tr_list[-period:])


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


# ============================================================
# STRATEGIES
# ============================================================

def strategy_v2_simple(ohlcv, bet_amount=100):
    """V2: 3 candles consecutives -> inverse"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount

    wins, losses = 0, 0

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
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_v3_volume(ohlcv, bet_amount=100, volume_threshold=1.2):
    """V3: 3 candles + Volume > 1.2x"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    wins, losses, skipped = 0, 0, 0

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

        if rel_vol < volume_threshold:
            skipped += 1
            continue

        actual = get_direction(ohlcv[i])
        if signal == actual:
            wins += 1
        else:
            losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl, "skipped": skipped}


def strategy_rsi(ohlcv, bet_amount=100, oversold=30, overbought=70):
    """RSI: < 30 -> UP, > 70 -> DOWN"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    wins, losses = 0, 0

    for i in range(LOOKBACK, len(ohlcv) - 1):
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        rsi = calculate_rsi(closes)

        signal = None
        if rsi < oversold:
            signal = "UP"
        elif rsi > overbought:
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_rsi_adjusted(ohlcv, bet_amount=100, oversold=25, overbought=75):
    """RSI Adjusted Crypto: < 25 -> UP, > 75 -> DOWN"""
    return strategy_rsi(ohlcv, bet_amount, oversold, overbought)


def strategy_macd(ohlcv, bet_amount=100):
    """MACD Crossover: histogram change"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 35

    wins, losses = 0, 0
    prev_histogram = None

    for i in range(LOOKBACK, len(ohlcv) - 1):
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        _, _, histogram = calculate_macd(closes)

        signal = None
        if prev_histogram is not None:
            # Crossover: histogram changes sign
            if prev_histogram < 0 and histogram > 0:
                signal = "UP"
            elif prev_histogram > 0 and histogram < 0:
                signal = "DOWN"

        prev_histogram = histogram

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_bollinger(ohlcv, bet_amount=100):
    """Bollinger Bands: price touches lower -> UP, touches upper -> DOWN"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 25

    wins, losses = 0, 0

    for i in range(LOOKBACK, len(ohlcv) - 1):
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        upper, middle, lower = calculate_bollinger(closes)

        current_close = ohlcv[i-1][4]
        current_low = ohlcv[i-1][3]
        current_high = ohlcv[i-1][2]

        signal = None
        # Price touches lower band -> bounce UP
        if current_low <= lower:
            signal = "UP"
        # Price touches upper band -> bounce DOWN
        elif current_high >= upper:
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_ema_cross(ohlcv, bet_amount=100, fast=9, slow=21):
    """EMA Cross: fast crosses above slow -> UP, below -> DOWN"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = slow + 5

    wins, losses = 0, 0
    prev_fast, prev_slow = None, None

    for i in range(LOOKBACK, len(ohlcv) - 1):
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]
        ema_fast = calculate_ema(closes, fast)
        ema_slow = calculate_ema(closes, slow)

        signal = None
        if prev_fast is not None and prev_slow is not None:
            # Golden cross: fast crosses above slow
            if prev_fast < prev_slow and ema_fast > ema_slow:
                signal = "UP"
            # Death cross: fast crosses below slow
            elif prev_fast > prev_slow and ema_fast < ema_slow:
                signal = "DOWN"

        prev_fast, prev_slow = ema_fast, ema_slow

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_atr_breakout(ohlcv, bet_amount=100):
    """ATR Breakout: high volatility + direction"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    wins, losses = 0, 0

    for i in range(LOOKBACK, len(ohlcv) - 1):
        highs = [c[2] for c in ohlcv[i-LOOKBACK:i]]
        lows = [c[3] for c in ohlcv[i-LOOKBACK:i]]
        closes = [c[4] for c in ohlcv[i-LOOKBACK:i]]

        atr = calculate_atr(highs, lows, closes)
        avg_atr = np.mean([calculate_atr(
            [c[2] for c in ohlcv[j-14:j]],
            [c[3] for c in ohlcv[j-14:j]],
            [c[4] for c in ohlcv[j-14:j]]
        ) for j in range(i-10, i)])

        # High volatility regime
        if atr < avg_atr * 1.2:
            continue

        # Direction based on last candle
        last_dir = get_direction(ohlcv[i-1])
        signal = "DOWN" if last_dir == "UP" else "UP"  # Mean reversion

        actual = get_direction(ohlcv[i])
        if signal == actual:
            wins += 1
        else:
            losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_combined_rsi_volume(ohlcv, bet_amount=100):
    """Combined: 2 candles + RSI extreme + Volume"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount
    LOOKBACK = 20

    wins, losses, skipped = 0, 0, 0

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

        signal = None

        # 2 DOWN + RSI < 35 + Volume > 1.0x -> UP
        if d1 == "DOWN" and rsi < 35 and rel_vol > 1.0:
            signal = "UP"
        # 2 UP + RSI > 65 + Volume > 1.0x -> DOWN
        elif d1 == "UP" and rsi > 65 and rel_vol > 1.0:
            signal = "DOWN"

        if not signal:
            skipped += 1
            continue

        actual = get_direction(ohlcv[i])
        if signal == actual:
            wins += 1
        else:
            losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl, "skipped": skipped}


def strategy_2_candles_simple(ohlcv, bet_amount=100):
    """2 candles consecutives -> inverse (plus de trades)"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount

    wins, losses = 0, 0

    for i in range(2, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-2])
        d2 = get_direction(ohlcv[i-1])

        signal = None
        if d1 == "DOWN" and d2 == "DOWN":
            signal = "UP"
        elif d1 == "UP" and d2 == "UP":
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


def strategy_4_candles(ohlcv, bet_amount=100):
    """4 candles consecutives -> inverse (plus selectif)"""
    entry_price = 0.525
    win_profit = (bet_amount / entry_price) * (1 - entry_price)
    loss_amount = bet_amount

    wins, losses = 0, 0

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
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    pnl = (wins * win_profit) - (losses * loss_amount)
    return {"wins": wins, "losses": losses, "total": total, "pnl": pnl}


# ============================================================
# MAIN
# ============================================================

def main():
    exchange = ccxt.binance({'enableRateLimit': True})

    print("=" * 90)
    print("BACKTEST COMPLET - TOUTES LES STRATEGIES")
    print("=" * 90)
    print("Periode: 2024-2025 | Paires: BTC, ETH, XRP | Timeframe: 15min")
    print("Mise: $100/trade @ 52.5c | Win: +$90.48 | Loss: -$100")
    print("=" * 90)

    # Periode
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

    symbols = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

    # Charger les donnees
    all_data = {}
    for symbol in symbols:
        print(f"\nTelechargement {symbol}...", end=" ", flush=True)
        all_data[symbol] = fetch_historical_data(exchange, symbol, start_date, end_date)
        print(f"{len(all_data[symbol])} candles")

    # Liste des strategies a tester
    strategies = [
        ("1. V2 Simple (3 candles)", strategy_v2_simple),
        ("2. V3 Volume 1.2x", lambda x: strategy_v3_volume(x, volume_threshold=1.2)),
        ("3. 2 Candles Simple", strategy_2_candles_simple),
        ("4. 4 Candles", strategy_4_candles),
        ("5. RSI (30/70)", lambda x: strategy_rsi(x, oversold=30, overbought=70)),
        ("6. RSI Crypto (25/75)", lambda x: strategy_rsi(x, oversold=25, overbought=75)),
        ("7. MACD Crossover", strategy_macd),
        ("8. Bollinger Bands", strategy_bollinger),
        ("9. EMA Cross (9/21)", lambda x: strategy_ema_cross(x, fast=9, slow=21)),
        ("10. EMA Cross (12/26)", lambda x: strategy_ema_cross(x, fast=12, slow=26)),
        ("11. ATR Breakout", strategy_atr_breakout),
        ("12. Combined RSI+Vol", strategy_combined_rsi_volume),
    ]

    results = []

    print("\n" + "=" * 90)
    print("RESULTATS PAR STRATEGIE")
    print("=" * 90)

    for name, strategy_fn in strategies:
        print(f"\nTest: {name}...", end=" ", flush=True)

        total_wins = 0
        total_losses = 0
        total_pnl = 0

        for symbol in symbols:
            r = strategy_fn(all_data[symbol])
            total_wins += r["wins"]
            total_losses += r["losses"]
            total_pnl += r["pnl"]

        total_trades = total_wins + total_losses
        wr = (total_wins / total_trades * 100) if total_trades > 0 else 0
        pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
        trades_per_day = total_trades / (365 * 2)  # 2 ans

        results.append({
            "name": name,
            "trades": total_trades,
            "wins": total_wins,
            "wr": wr,
            "pnl": total_pnl,
            "pnl_per_trade": pnl_per_trade,
            "trades_per_day": trades_per_day
        })

        print(f"OK - {total_trades:,} trades | {wr:.1f}% WR | ${total_pnl:,.0f}")

    # Trier par Win Rate
    results_by_wr = sorted(results, key=lambda x: x["wr"], reverse=True)

    # Trier par PnL Total
    results_by_pnl = sorted(results, key=lambda x: x["pnl"], reverse=True)

    # Trier par PnL/Trade
    results_by_ppt = sorted(results, key=lambda x: x["pnl_per_trade"], reverse=True)

    # ===== CLASSEMENT PAR WIN RATE =====
    print("\n" + "=" * 90)
    print("CLASSEMENT PAR WIN RATE")
    print("=" * 90)
    print(f"\n{'Rank':<5} | {'Strategie':<30} | {'Trades':>10} | {'WR':>8} | {'PnL':>12} | {'PnL/Trade':>10}")
    print("-" * 90)

    for i, r in enumerate(results_by_wr, 1):
        pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"
        print(f"{i:<5} | {r['name']:<30} | {r['trades']:>10,} | {r['wr']:>7.1f}% | {pnl_str:>12} | ${r['pnl_per_trade']:>9.2f}")

    # ===== CLASSEMENT PAR PNL TOTAL =====
    print("\n" + "=" * 90)
    print("CLASSEMENT PAR PNL TOTAL")
    print("=" * 90)
    print(f"\n{'Rank':<5} | {'Strategie':<30} | {'Trades':>10} | {'WR':>8} | {'PnL':>12} | {'PnL/Trade':>10}")
    print("-" * 90)

    for i, r in enumerate(results_by_pnl, 1):
        pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"
        print(f"{i:<5} | {r['name']:<30} | {r['trades']:>10,} | {r['wr']:>7.1f}% | {pnl_str:>12} | ${r['pnl_per_trade']:>9.2f}")

    # ===== CLASSEMENT PAR PNL/TRADE =====
    print("\n" + "=" * 90)
    print("CLASSEMENT PAR PNL/TRADE (Efficacite)")
    print("=" * 90)
    print(f"\n{'Rank':<5} | {'Strategie':<30} | {'Trades':>10} | {'WR':>8} | {'PnL':>12} | {'PnL/Trade':>10}")
    print("-" * 90)

    for i, r in enumerate(results_by_ppt, 1):
        pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"
        print(f"{i:<5} | {r['name']:<30} | {r['trades']:>10,} | {r['wr']:>7.1f}% | {pnl_str:>12} | ${r['pnl_per_trade']:>9.2f}")

    # ===== CONCLUSION =====
    print("\n" + "=" * 90)
    print("CONCLUSION FINALE")
    print("=" * 90)

    best_wr = results_by_wr[0]
    best_pnl = results_by_pnl[0]
    best_ppt = results_by_ppt[0]

    print(f"\n MEILLEUR WIN RATE:")
    print(f"   {best_wr['name']}")
    print(f"   WR: {best_wr['wr']:.1f}% | Trades: {best_wr['trades']:,} | PnL: ${best_wr['pnl']:,.0f}")

    print(f"\n MEILLEUR PNL TOTAL:")
    print(f"   {best_pnl['name']}")
    print(f"   PnL: ${best_pnl['pnl']:,.0f} | WR: {best_pnl['wr']:.1f}% | Trades: {best_pnl['trades']:,}")

    print(f"\n MEILLEUR PNL/TRADE:")
    print(f"   {best_ppt['name']}")
    print(f"   PnL/Trade: ${best_ppt['pnl_per_trade']:.2f} | WR: {best_ppt['wr']:.1f}% | PnL: ${best_ppt['pnl']:,.0f}")

    # Recommandation
    print("\n" + "-" * 90)
    print("RECOMMANDATION:")
    print("-" * 90)

    # Trouver le meilleur compromis (WR > 55% ET PnL > 0 ET Trades > 10000)
    viable = [r for r in results if r["wr"] > 55 and r["pnl"] > 0 and r["trades"] > 5000]
    if viable:
        # Trier par score composite: WR * PnL_per_trade
        viable_sorted = sorted(viable, key=lambda x: x["wr"] * x["pnl_per_trade"], reverse=True)
        best = viable_sorted[0]
        print(f"\n MEILLEUR COMPROMIS (WR > 55% + Volume suffisant):")
        print(f"   >>> {best['name']} <<<")
        print(f"   WR: {best['wr']:.1f}%")
        print(f"   PnL Total: ${best['pnl']:,.0f}")
        print(f"   PnL/Trade: ${best['pnl_per_trade']:.2f}")
        print(f"   Trades: {best['trades']:,} ({best['trades_per_day']:.1f}/jour)")

    # Strategies non viables
    print("\n STRATEGIES NON VIABLES (WR < 52.5% breakeven):")
    non_viable = [r for r in results if r["wr"] < 52.5]
    for r in non_viable:
        print(f"   - {r['name']} ({r['wr']:.1f}% WR)")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    main()
