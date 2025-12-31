#!/usr/bin/env python3
"""
BACKTEST STRATEGIE V2 - SIMPLE MEAN REVERSION
Regle: 3 candles consecutives dans une direction -> parier inverse
"""

import ccxt
import time
from datetime import datetime, timezone

def get_direction(candle):
    """Retourne UP si close > open, sinon DOWN"""
    return "UP" if candle[4] > candle[1] else "DOWN"

def backtest_v2_simple(symbol, exchange, days=30):
    """Backtest la strategie V2 sur N jours"""
    limit = min(96 * days, 1000)
    ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=limit)

    wins = 0
    losses = 0

    for i in range(3, len(ohlcv) - 1):
        d1 = get_direction(ohlcv[i-3])
        d2 = get_direction(ohlcv[i-2])
        d3 = get_direction(ohlcv[i-1])

        signal = None

        # 3 DOWN consecutifs -> UP
        if d1 == "DOWN" and d2 == "DOWN" and d3 == "DOWN":
            signal = "UP"
        # 3 UP consecutifs -> DOWN
        elif d1 == "UP" and d2 == "UP" and d3 == "UP":
            signal = "DOWN"

        if signal:
            actual = get_direction(ohlcv[i])
            if signal == actual:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0

    return {
        "symbol": symbol,
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": wr,
        "trades_per_day": total / days if days > 0 else 0
    }

def main():
    exchange = ccxt.binance({'enableRateLimit': True})
    days = 10

    print("=" * 70)
    print("BACKTEST STRATEGIE V2 - SIMPLE MEAN REVERSION")
    print("Regle: 3 candles consecutives -> parier inverse")
    print("=" * 70)
    print(f"\nPeriode: {days} derniers jours")
    print("-" * 70)

    results = []
    for symbol in ["BTC/USDT", "ETH/USDT", "XRP/USDT"]:
        result = backtest_v2_simple(symbol, exchange, days)
        results.append(result)
        print(f"{result['symbol']:12} | Trades: {result['total']:4} | Wins: {result['wins']:3} | WR: {result['win_rate']:5.1f}% | {result['trades_per_day']:.1f}/jour")
        time.sleep(0.5)

    # Total
    total_trades = sum(r["total"] for r in results)
    total_wins = sum(r["wins"] for r in results)
    total_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0

    print("-" * 70)
    print(f"{'TOTAL':12} | Trades: {total_trades:4} | Wins: {total_wins:3} | WR: {total_wr:5.1f}% | {total_trades/days:.1f}/jour")

    # PnL
    print("\n" + "=" * 70)
    print("ANALYSE PnL (mise $5.25 par trade @ 52.5c)")
    print("=" * 70)

    bet = 5.25
    win_profit = 4.75
    loss_amount = 5.25

    total_pnl = (total_wins * win_profit) - ((total_trades - total_wins) * loss_amount)
    pnl_per_day = total_pnl / days
    pnl_per_month = pnl_per_day * 30

    print(f"Wins: {total_wins} x ${win_profit} = +${total_wins * win_profit:.2f}")
    print(f"Losses: {total_trades - total_wins} x ${loss_amount} = -${(total_trades - total_wins) * loss_amount:.2f}")
    print(f"PnL Total ({days}j): ${total_pnl:.2f}")
    print(f"PnL/jour: ${pnl_per_day:.2f}")
    print(f"PnL/mois (projection): ${pnl_per_month:.2f}")

    print("\n" + "=" * 70)
    if total_wr >= 55:
        print("✅ STRATEGIE VIABLE (WR >= 55%)")
    elif total_wr >= 52.5:
        print("⚠️ STRATEGIE MARGINALE (WR ~52.5% breakeven)")
    else:
        print("❌ STRATEGIE NON VIABLE (WR < 52.5%)")
    print("=" * 70)

    # Test avec différents nombres de candles consécutives
    print("\n" + "=" * 70)
    print("TEST VARIATIONS (BTC seulement)")
    print("=" * 70)

    for consecutive in [2, 3, 4, 5]:
        wins = 0
        losses = 0
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", '15m', limit=1000)

        for i in range(consecutive, len(ohlcv) - 1):
            directions = [get_direction(ohlcv[i-j-1]) for j in range(consecutive)]

            signal = None
            if all(d == "DOWN" for d in directions):
                signal = "UP"
            elif all(d == "UP" for d in directions):
                signal = "DOWN"

            if signal:
                actual = get_direction(ohlcv[i])
                if signal == actual:
                    wins += 1
                else:
                    losses += 1

        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        print(f"{consecutive} candles consecutives: {wins}/{total} = {wr:.1f}% WR | {total/10:.1f} trades/jour")

if __name__ == "__main__":
    main()
