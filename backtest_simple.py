#!/usr/bin/env python3
"""
Backtest Simple - Mean Reversion Strategy
Pour BTC, ETH, XRP sur 2024-2025
"""

import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from src.data_manager import DataManager
from src.config import get_config

# Parametres
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
SHARES_PER_TRADE = 5  # 5 shares
INITIAL_CAPITAL = 10000
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
CONSEC_THRESHOLD = 3
MAX_PRICE = 0.50  # 50 cents max

def calculate_rsi(closes):
    if len(closes) < RSI_PERIOD + 1:
        return 50
    delta = pd.Series(closes).diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def count_consecutive(opens, closes, idx):
    consec_up = 0
    consec_down = 0
    for i in range(idx, max(idx-10, -1), -1):
        is_up = closes[i] > opens[i]
        is_down = closes[i] < opens[i]

        if i == idx:
            if is_up: consec_up = 1
            elif is_down: consec_down = 1
        else:
            if is_down and consec_down > 0: consec_down += 1
            elif is_up and consec_up > 0: consec_up += 1
            else: break
    return consec_up, consec_down

print('=' * 60)
print('BACKTEST MEAN REVERSION 2024-2025')
print('=' * 60)
print(f'Capital: ${INITIAL_CAPITAL:,} | Shares/trade: {SHARES_PER_TRADE}')
print(f'Symboles: {", ".join([s.split("/")[0] for s in SYMBOLS])}')
print('=' * 60)

# Charger les donnees
config = get_config()
dm = DataManager(config)

all_data = {}
for symbol in SYMBOLS:
    print(f'Chargement {symbol}...', end=' ')
    df = dm.prepare_multi_timeframe_data(symbol, ['15m'])['15m']
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] <= '2025-12-28')]
    all_data[symbol] = df.reset_index(drop=True)
    print(f'{len(df)} bougies')

# Simulation
capital = INITIAL_CAPITAL
results = {s: {'wins': 0, 'losses': 0, 'pnl': 0} for s in SYMBOLS}
total_trades = 0

for symbol, df in all_data.items():
    opens = df['open'].values
    closes = df['close'].values

    for i in range(RSI_PERIOD + 5, len(df) - 1):
        # RSI
        rsi = calculate_rsi(closes[:i+1].tolist())

        # Consecutives
        consec_up, consec_down = count_consecutive(opens, closes, i)

        # Momentum
        momentum = (closes[i] - closes[i-3]) / closes[i-3] * 100

        # Signaux
        signal = None
        if (consec_down >= CONSEC_THRESHOLD or rsi < RSI_OVERSOLD) and momentum < 0:
            signal = 'UP'
        elif (consec_up >= CONSEC_THRESHOLD or rsi > RSI_OVERBOUGHT) and momentum > 0:
            signal = 'DOWN'

        if signal:
            # Prix simule (48-52 cents)
            entry_price = 0.48 + np.random.random() * 0.04

            # Filtre prix max
            if entry_price > MAX_PRICE:
                continue

            bet_cost = SHARES_PER_TRADE * entry_price

            if capital < bet_cost:
                continue

            # Resultat
            if signal == 'UP':
                is_win = closes[i + 1] > closes[i]
            else:
                is_win = closes[i + 1] < closes[i]

            # PnL Polymarket
            if is_win:
                # Win: receive $1 per share
                pnl = SHARES_PER_TRADE - bet_cost
                capital += pnl
                results[symbol]['wins'] += 1
            else:
                # Loss: lose the bet
                pnl = -bet_cost
                capital += pnl
                results[symbol]['losses'] += 1

            results[symbol]['pnl'] += pnl
            total_trades += 1

# Resultats
print()
print('=' * 60)
print('RESULTATS')
print('=' * 60)

total_pnl = capital - INITIAL_CAPITAL
total_wins = sum(r['wins'] for r in results.values())
total_losses = sum(r['losses'] for r in results.values())
win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0

print(f'Capital final: ${capital:,.2f}')
print(f'PnL total: ${total_pnl:,.2f} ({total_pnl/INITIAL_CAPITAL*100:+.2f}%)')
print(f'Trades: {total_trades}')
print(f'Wins: {total_wins} | Losses: {total_losses}')
print(f'Win Rate: {win_rate:.2f}%')
print(f'Trades/jour: {total_trades / 730:.1f}')

print()
print('Par symbole:')
for symbol in SYMBOLS:
    r = results[symbol]
    trades = r['wins'] + r['losses']
    if trades > 0:
        wr = r['wins'] / trades * 100
        status = 'FORT' if wr >= 55 else 'OK' if wr >= 50 else 'FAIBLE'
        print(f"  {symbol.split('/')[0]}: WR={wr:.1f}% | Trades={trades} | PnL=${r['pnl']:.2f} | {status}")

print('=' * 60)
