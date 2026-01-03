#!/usr/bin/env python3
"""
Simulation V10 - $100 par position
BTC, ETH, XRP - 2024 et 2025
"""

import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# V10 Strategy Parameters
RSI_PERIOD = 7
RSI_OVERSOLD = 42
RSI_OVERBOUGHT = 62
STOCH_PERIOD = 5
STOCH_OVERSOLD = 38
STOCH_OVERBOUGHT = 68
FTFC_THRESHOLD = 2.0

# Trading Parameters
BET_AMOUNT = 100
ENTRY_PRICE = 0.525
WIN_PAYOUT = 1.0

PAIRS = ["BTC/USDT", "ETH/USDT", "XRP/USDT"]

def calculate_rsi(prices, period=7):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_stochastic(df, period=5):
    low_min = df["low"].rolling(window=period).min()
    high_max = df["high"].rolling(window=period).max()
    stoch = 100 * (df["close"] - low_min) / (high_max - low_min)
    return stoch

def calculate_ftfc(df_1h, df_4h, timestamp):
    h1_data = df_1h[df_1h.index <= timestamp].tail(5)
    if len(h1_data) >= 3:
        h1_trend = (h1_data["close"].iloc[-1] - h1_data["close"].iloc[0]) / h1_data["close"].iloc[0] * 100
        h1_rsi = calculate_rsi(df_1h[df_1h.index <= timestamp]["close"], 14).iloc[-1]
    else:
        h1_trend, h1_rsi = 0, 50
    
    h4_data = df_4h[df_4h.index <= timestamp].tail(5)
    if len(h4_data) >= 3:
        h4_trend = (h4_data["close"].iloc[-1] - h4_data["close"].iloc[0]) / h4_data["close"].iloc[0] * 100
        h4_rsi = calculate_rsi(df_4h[df_4h.index <= timestamp]["close"], 14).iloc[-1]
    else:
        h4_trend, h4_rsi = 0, 50
    
    ftfc = 0
    if h1_trend > 0.1: ftfc += 1
    elif h1_trend < -0.1: ftfc -= 1
    if h4_trend > 0.2: ftfc += 1
    elif h4_trend < -0.2: ftfc -= 1
    if h1_rsi > 55: ftfc += 0.5
    elif h1_rsi < 45: ftfc -= 0.5
    if h4_rsi > 55: ftfc += 0.5
    elif h4_rsi < 45: ftfc -= 0.5
    
    return ftfc

def fetch_data(exchange, symbol, timeframe, start_date, end_date):
    all_data = []
    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    print(f"  Fetching {symbol} {timeframe}...", end=" ", flush=True)
    
    while since < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
        except Exception as e:
            print(f"Error: {e}")
            break
    
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="first")]
    print(f"{len(df)} candles")
    return df

def simulate_pair(exchange, symbol, start_date, end_date):
    base = symbol.split("/")[0]
    
    df_15m = fetch_data(exchange, symbol, "15m", start_date - timedelta(days=7), end_date)
    df_1h = fetch_data(exchange, symbol, "1h", start_date - timedelta(days=30), end_date)
    df_4h = fetch_data(exchange, symbol, "4h", start_date - timedelta(days=60), end_date)
    
    if df_15m.empty:
        return []
    
    df_15m["rsi"] = calculate_rsi(df_15m["close"], RSI_PERIOD)
    df_15m["stoch"] = calculate_stochastic(df_15m, STOCH_PERIOD)
    
    trades = []
    sim_data = df_15m[(df_15m.index >= start_date) & (df_15m.index < end_date)]
    
    print(f"  Simulating {len(sim_data)} candles...")
    
    for i, (timestamp, row) in enumerate(sim_data.iterrows()):
        if pd.isna(row["rsi"]) or pd.isna(row["stoch"]):
            continue
        
        rsi = row["rsi"]
        stoch = row["stoch"]
        ftfc = calculate_ftfc(df_1h, df_4h, timestamp)
        
        signal = None
        
        if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
            if ftfc > -FTFC_THRESHOLD:
                signal = "UP"
        elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
            if ftfc < FTFC_THRESHOLD:
                signal = "DOWN"
        
        if signal:
            next_idx = sim_data.index.get_loc(timestamp)
            if next_idx + 1 < len(sim_data):
                next_candle = sim_data.iloc[next_idx + 1]
                price_change = next_candle["close"] - next_candle["open"]
                
                if signal == "UP":
                    win = price_change > 0
                else:
                    win = price_change < 0
                
                shares = BET_AMOUNT / ENTRY_PRICE
                if win:
                    pnl = shares * (WIN_PAYOUT - ENTRY_PRICE)
                else:
                    pnl = -BET_AMOUNT
                
                trades.append({
                    "timestamp": timestamp,
                    "symbol": base,
                    "signal": signal,
                    "rsi": rsi,
                    "stoch": stoch,
                    "ftfc": ftfc,
                    "win": win,
                    "pnl": pnl
                })
    
    return trades

def main():
    print("=" * 70)
    print("SIMULATION V10 - $100/POSITION - BTC/ETH/XRP")
    print("=" * 70)
    print(f"RSI({RSI_PERIOD}): {RSI_OVERSOLD}/{RSI_OVERBOUGHT}")
    print(f"Stoch({STOCH_PERIOD}): {STOCH_OVERSOLD}/{STOCH_OVERBOUGHT}")
    print(f"FTFC Threshold: {FTFC_THRESHOLD}")
    print(f"Bet: ${BET_AMOUNT} | Entry: {ENTRY_PRICE*100}c")
    print("=" * 70)
    
    exchange = ccxt.binance({"enableRateLimit": True})
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 1, 1)
    
    all_trades = []
    
    for symbol in PAIRS:
        print(f"\n{symbol}")
        trades = simulate_pair(exchange, symbol, start_date, end_date)
        all_trades.extend(trades)
        print(f"  Total: {len(trades)} trades")
    
    if not all_trades:
        print("No trades found!")
        return
    
    df = pd.DataFrame(all_trades)
    df["month"] = df["timestamp"].dt.to_period("M")
    df["year"] = df["timestamp"].dt.year
    
    print("\n" + "=" * 70)
    print("RESULTATS MENSUELS DETAILLES")
    print("=" * 70)
    
    monthly = df.groupby("month").agg({
        "pnl": "sum",
        "win": ["sum", "count"]
    }).round(2)
    monthly.columns = ["pnl", "wins", "trades"]
    monthly["losses"] = monthly["trades"] - monthly["wins"]
    monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(1)
    
    header = f"{Mois:<10} {Trades:>8} {Wins:>6} {Losses:>8} {WinRate:>8} {PnL:>14}"
    print(f"\n{header}")
    print("-" * 60)
    
    for month, row in monthly.iterrows():
        pnl_val = row["pnl"]
        if pnl_val >= 0:
            pnl_str = f"${pnl_val:,.0f}"
        else:
            pnl_str = f"-${abs(pnl_val):,.0f}"
        wr_str = f"{row[win_rate]:.1f}%"
        print(f"{str(month):<10} {int(row[trades]):>8} {int(row[wins]):>6} {int(row[losses]):>8} {wr_str:>8} {pnl_str:>14}")
    
    print("\n" + "=" * 70)
    print("RESUME ANNUEL")
    print("=" * 70)
    
    for year in [2024, 2025]:
        year_data = df[df["year"] == year]
        if len(year_data) > 0:
            wins = year_data["win"].sum()
            total = len(year_data)
            wr = wins / total * 100
            pnl = year_data["pnl"].sum()
            if pnl >= 0:
                pnl_str = f"${pnl:,.0f}"
            else:
                pnl_str = f"-${abs(pnl):,.0f}"
            print(f"\n{year}:")
            print(f"   Trades: {total:,}")
            print(f"   Wins: {int(wins):,} | Losses: {total - int(wins):,}")
            print(f"   Win Rate: {wr:.1f}%")
            print(f"   PnL Total: {pnl_str}")
            print(f"   PnL/mois moyen: ${pnl/12:,.0f}")
    
    print("\n" + "=" * 70)
    print("PAR SYMBOLE (2024-2025)")
    print("=" * 70)
    
    for symbol in ["BTC", "ETH", "XRP"]:
        sym_data = df[df["symbol"] == symbol]
        if len(sym_data) > 0:
            wins = sym_data["win"].sum()
            total = len(sym_data)
            wr = wins / total * 100
            pnl = sym_data["pnl"].sum()
            if pnl >= 0:
                pnl_str = f"${pnl:,.0f}"
            else:
                pnl_str = f"-${abs(pnl):,.0f}"
            print(f"\n{symbol}: {total:,} trades | WR: {wr:.1f}% | PnL: {pnl_str}")
    
    print("\n" + "=" * 70)
    print("RESUME TOTAL (2024-2025)")
    print("=" * 70)
    
    total_trades = len(df)
    total_wins = df["win"].sum()
    total_pnl = df["pnl"].sum()
    avg_monthly = total_pnl / 24
    
    print(f"\nCapital par trade: ${BET_AMOUNT}")
    print(f"Total trades: {total_trades:,}")
    print(f"Wins: {int(total_wins):,}")
    print(f"Losses: {total_trades - int(total_wins):,}")
    print(f"Win Rate: {total_wins/total_trades*100:.1f}%")
    
    if total_pnl >= 0:
        print(f"\nPnL Total: ${total_pnl:,.0f}")
    else:
        print(f"\nPnL Total: -${abs(total_pnl):,.0f}")
    print(f"PnL Mensuel Moyen: ${avg_monthly:,.0f}")
    
    df.to_csv("simulation_v10_100usd_results.csv", index=False)
    monthly.to_csv("simulation_v10_100usd_monthly.csv")
    print("\nResultats sauvegardes dans simulation_v10_100usd_*.csv")

if __name__ == "__main__":
    main()
