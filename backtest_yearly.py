#!/usr/bin/env python3
"""
Backtest par année - 2022, 2023, 2024, 2025
Strategy optimisée: RSI 25/75, Consec 5, Mom 0.2%, Heures bloquées
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List
import time

# Config optimisée
RSI_PERIOD = 14
RSI_OVERSOLD = 25
RSI_OVERBOUGHT = 75
CONSEC_THRESHOLD = 5
MIN_MOMENTUM = 0.2
BLOCKED_HOURS = [3, 7, 15, 18, 19, 20]

def download_year_data(exchange, symbol: str, year: int) -> pd.DataFrame:
    """Télécharge les données 15m pour une année complète"""
    print(f"  📥 Téléchargement {symbol} {year}...")

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    if year == 2025:
        end = datetime.now(timezone.utc)
    else:
        end = datetime(year, 12, 31, 23, 59, tzinfo=timezone.utc)

    all_data = []
    since = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)

    while since < end_ts:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '15m', since=since, limit=1000)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            time.sleep(0.1)
        except Exception as e:
            print(f"    ⚠️ Erreur: {e}")
            time.sleep(1)
            continue

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset=['timestamp'])
    print(f"    ✅ {len(df)} bougies téléchargées")
    return df

def calculate_rsi(closes: pd.Series) -> pd.Series:
    """RSI vectorisé"""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(span=RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def count_consecutive_vectorized(df: pd.DataFrame) -> tuple:
    """Compte bougies consécutives de manière vectorisée"""
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)

    # Groupes de bougies consécutives
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()

    consec_up = is_up.groupby(up_groups).cumsum()
    consec_down = is_down.groupby(down_groups).cumsum()

    return consec_up, consec_down

def backtest_year(df: pd.DataFrame, symbol: str, year: int) -> Dict:
    """Backtest pour une année"""
    if df is None or len(df) < 50:
        return None

    # Calculer indicateurs
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])
    df['consec_up'], df['consec_down'] = count_consecutive_vectorized(df)
    df['momentum'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100
    df['hour'] = df['datetime'].dt.hour

    # Filtrer heures bloquées
    df['blocked'] = df['hour'].isin(BLOCKED_HOURS)

    # Générer signaux
    df['signal_up'] = (
        ((df['consec_down'] >= CONSEC_THRESHOLD) | (df['rsi'] < RSI_OVERSOLD)) &
        (df['momentum'] < -MIN_MOMENTUM) &
        (~df['blocked'])
    )
    df['signal_down'] = (
        ((df['consec_up'] >= CONSEC_THRESHOLD) | (df['rsi'] > RSI_OVERBOUGHT)) &
        (df['momentum'] > MIN_MOMENTUM) &
        (~df['blocked'])
    )

    # Simuler trades
    trades = []
    last_trade_idx = -16  # Cooldown 4 bougies (1 heure)

    for i in range(20, len(df)):
        if i - last_trade_idx < 4:  # Cooldown
            continue

        row = df.iloc[i]

        if row['signal_up']:
            # Vérifier résultat (bougie suivante)
            if i + 1 < len(df):
                next_row = df.iloc[i + 1]
                win = next_row['close'] > next_row['open']
                trades.append({
                    'datetime': row['datetime'],
                    'signal': 'UP',
                    'win': win,
                    'entry_price': row['close'],
                    'rsi': row['rsi'],
                    'consec': row['consec_down']
                })
                last_trade_idx = i

        elif row['signal_down']:
            if i + 1 < len(df):
                next_row = df.iloc[i + 1]
                win = next_row['close'] < next_row['open']
                trades.append({
                    'datetime': row['datetime'],
                    'signal': 'DOWN',
                    'win': win,
                    'entry_price': row['close'],
                    'rsi': row['rsi'],
                    'consec': row['consec_up']
                })
                last_trade_idx = i

    if not trades:
        return None

    trades_df = pd.DataFrame(trades)
    wins = trades_df['win'].sum()
    total = len(trades_df)
    win_rate = wins / total * 100 if total > 0 else 0

    # PnL (mise $2.50, gain $2.50 si win, perte $2.50 si loss)
    bet = 2.50
    pnl = sum([bet if t['win'] else -bet for t in trades])

    # Trades par jour
    days = (df['datetime'].max() - df['datetime'].min()).days or 1
    trades_per_day = total / days

    return {
        'symbol': symbol,
        'year': year,
        'total_trades': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': win_rate,
        'pnl': pnl,
        'trades_per_day': trades_per_day,
        'days': days
    }

def main():
    print("=" * 70)
    print("📊 BACKTEST PAR ANNÉE - STRATÉGIE OPTIMISÉE")
    print("=" * 70)
    print(f"Config: RSI {RSI_OVERSOLD}/{RSI_OVERBOUGHT} | Consec {CONSEC_THRESHOLD} | Mom {MIN_MOMENTUM}%")
    print(f"Heures bloquées: {BLOCKED_HOURS}")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    years = [2022, 2023, 2024, 2025]

    all_results = []

    for year in years:
        print(f"\n{'='*70}")
        print(f"📅 ANNÉE {year}")
        print("=" * 70)

        year_results = []

        for symbol in symbols:
            df = download_year_data(exchange, symbol, year)
            result = backtest_year(df, symbol, year)

            if result:
                year_results.append(result)
                all_results.append(result)
                print(f"\n  {symbol.split('/')[0]}:")
                print(f"    Trades: {result['total_trades']} ({result['trades_per_day']:.1f}/jour)")
                print(f"    Win Rate: {result['win_rate']:.1f}%")
                print(f"    PnL: ${result['pnl']:+.2f}")

        # Résumé année
        if year_results:
            total_trades = sum(r['total_trades'] for r in year_results)
            total_wins = sum(r['wins'] for r in year_results)
            total_pnl = sum(r['pnl'] for r in year_results)
            avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0

            print(f"\n  📊 TOTAL {year}:")
            print(f"    Trades: {total_trades}")
            print(f"    Win Rate Global: {avg_wr:.1f}%")
            print(f"    PnL Total: ${total_pnl:+.2f}")

    # Résumé global
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ GLOBAL (2022-2025)")
    print("=" * 70)

    # Par symbole
    for symbol in symbols:
        sym_results = [r for r in all_results if r['symbol'] == symbol]
        if sym_results:
            total = sum(r['total_trades'] for r in sym_results)
            wins = sum(r['wins'] for r in sym_results)
            pnl = sum(r['pnl'] for r in sym_results)
            wr = wins / total * 100 if total > 0 else 0
            print(f"\n{symbol.split('/')[0]}:")
            print(f"  Trades: {total} | WR: {wr:.1f}% | PnL: ${pnl:+.2f}")

    # Total
    total_trades = sum(r['total_trades'] for r in all_results)
    total_wins = sum(r['wins'] for r in all_results)
    total_pnl = sum(r['pnl'] for r in all_results)
    global_wr = total_wins / total_trades * 100 if total_trades > 0 else 0

    print(f"\n{'='*70}")
    print(f"🎯 GLOBAL: {total_trades} trades | WR: {global_wr:.1f}% | PnL: ${total_pnl:+.2f}")
    print("=" * 70)

    # Tableau récapitulatif
    print("\n📋 TABLEAU RÉCAPITULATIF:")
    print("-" * 70)
    print(f"{'Année':<8} {'BTC WR':<12} {'ETH WR':<12} {'XRP WR':<12} {'Global WR':<12}")
    print("-" * 70)

    for year in years:
        year_results = [r for r in all_results if r['year'] == year]
        btc = next((r for r in year_results if 'BTC' in r['symbol']), None)
        eth = next((r for r in year_results if 'ETH' in r['symbol']), None)
        xrp = next((r for r in year_results if 'XRP' in r['symbol']), None)

        total = sum(r['total_trades'] for r in year_results)
        wins = sum(r['wins'] for r in year_results)
        global_wr = wins / total * 100 if total > 0 else 0

        btc_wr = f"{btc['win_rate']:.1f}%" if btc else "N/A"
        eth_wr = f"{eth['win_rate']:.1f}%" if eth else "N/A"
        xrp_wr = f"{xrp['win_rate']:.1f}%" if xrp else "N/A"

        print(f"{year:<8} {btc_wr:<12} {eth_wr:<12} {xrp_wr:<12} {global_wr:.1f}%")

    print("-" * 70)

if __name__ == "__main__":
    main()
