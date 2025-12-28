#!/usr/bin/env python3
"""
Backtest Rapide - Mean Reversion Strategy (vectorise)
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from src.data_manager import DataManager
from src.config import get_config

# Config
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
SHARES = 5
CAPITAL = 10000
RSI_PERIOD = 14
RSI_OB = 70
RSI_OS = 30
CONSEC = 3
MAX_PRICE = 0.50

def add_indicators(df):
    """Ajoute RSI et bougies consecutives"""
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Direction de la bougie
    df['is_up'] = (df['close'] > df['open']).astype(int)
    df['is_down'] = (df['close'] < df['open']).astype(int)

    # Bougies consecutives (simplifie)
    df['consec_up'] = df['is_up'].groupby((df['is_up'] != df['is_up'].shift()).cumsum()).cumsum()
    df['consec_down'] = df['is_down'].groupby((df['is_down'] != df['is_down'].shift()).cumsum()).cumsum()

    # Momentum 3 periodes
    df['momentum'] = df['close'].pct_change(3) * 100

    # Resultat suivant (WIN si prediction correcte)
    df['next_up'] = (df['close'].shift(-1) > df['close']).astype(int)
    df['next_down'] = (df['close'].shift(-1) < df['close']).astype(int)

    return df

def generate_signals(df):
    """Genere les signaux"""
    # UP: 3+ DOWN consec OU RSI < 30, momentum negatif
    signal_up = ((df['consec_down'] >= CONSEC) | (df['rsi'] < RSI_OS)) & (df['momentum'] < 0)

    # DOWN: 3+ UP consec OU RSI > 70, momentum positif
    signal_down = ((df['consec_up'] >= CONSEC) | (df['rsi'] > RSI_OB)) & (df['momentum'] > 0)

    df['signal'] = 'NONE'
    df.loc[signal_up, 'signal'] = 'UP'
    df.loc[signal_down, 'signal'] = 'DOWN'

    return df

print('=' * 60)
print('BACKTEST MEAN REVERSION 2024-2025 (Vectorise)')
print('=' * 60)
print(f'Capital: ${CAPITAL:,} | Shares: {SHARES} | Prix max: {MAX_PRICE*100:.0f}c')
print('=' * 60)

# Charger les donnees
config = get_config()
dm = DataManager(config)

all_results = []

for symbol in SYMBOLS:
    print(f'\n{symbol}:')

    # Charger
    df = dm.prepare_multi_timeframe_data(symbol, ['15m'])['15m']
    df = df[(df['timestamp'] >= '2024-01-01') & (df['timestamp'] <= '2025-12-28')].copy()
    print(f'  Bougies: {len(df)}')

    # Indicateurs
    df = add_indicators(df)
    df = generate_signals(df)

    # Filtrer les signaux
    trades = df[df['signal'] != 'NONE'].copy()
    print(f'  Signaux: {len(trades)}')

    # Simuler prix d'entree (48-52 cents)
    np.random.seed(42)
    trades['entry_price'] = 0.48 + np.random.random(len(trades)) * 0.04

    # Filtrer par prix max
    trades = trades[trades['entry_price'] <= MAX_PRICE]
    print(f'  Trades valides: {len(trades)}')

    # Calculer resultats
    trades['is_win'] = ((trades['signal'] == 'UP') & (trades['next_up'] == 1)) | \
                       ((trades['signal'] == 'DOWN') & (trades['next_down'] == 1))

    # PnL par trade
    trades['bet_cost'] = SHARES * trades['entry_price']
    trades['pnl'] = np.where(trades['is_win'], SHARES - trades['bet_cost'], -trades['bet_cost'])

    # Stats
    wins = trades['is_win'].sum()
    losses = len(trades) - wins
    wr = wins / len(trades) * 100 if len(trades) > 0 else 0
    pnl = trades['pnl'].sum()

    status = 'FORT' if wr >= 55 else 'OK' if wr >= 50 else 'FAIBLE'
    print(f'  WR: {wr:.1f}% | Wins: {wins} | Losses: {losses} | PnL: ${pnl:.2f} | {status}')

    all_results.append({
        'symbol': symbol,
        'trades': len(trades),
        'wins': wins,
        'losses': losses,
        'wr': wr,
        'pnl': pnl
    })

# Resume
print('\n' + '=' * 60)
print('RESUME GLOBAL')
print('=' * 60)

total_trades = sum(r['trades'] for r in all_results)
total_wins = sum(r['wins'] for r in all_results)
total_pnl = sum(r['pnl'] for r in all_results)
global_wr = total_wins / total_trades * 100 if total_trades > 0 else 0

print(f'Total trades: {total_trades}')
print(f'Win Rate global: {global_wr:.1f}%')
print(f'PnL total: ${total_pnl:,.2f}')
print(f'Capital final: ${CAPITAL + total_pnl:,.2f}')
print(f'Retour: {total_pnl/CAPITAL*100:+.2f}%')
print(f'Trades/jour: {total_trades / 730:.1f}')
print('=' * 60)
