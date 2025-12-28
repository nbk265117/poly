#!/usr/bin/env python3
"""
Optimisation pour atteindre $15k/mois avec 4 pairs + $100/trade
Objectif: Trouver la config avec 58%+ WR
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
from itertools import product

# CONFIG ACTUELLE
CURRENT_CONFIG = {
    'BTC': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec': 1, 'blocked': [4, 14, 15]},
    'ETH': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec': 1, 'blocked': [0, 6, 7, 14, 23]},
    'XRP': {'rsi_period': 5, 'rsi_oversold': 25, 'rsi_overbought': 75, 'stoch_period': 5, 'stoch_oversold': 20, 'stoch_overbought': 80, 'consec': 2, 'blocked': [1, 4, 7, 13, 16, 18, 19, 21]},
    'SOL': {'rsi_period': 7, 'rsi_oversold': 35, 'rsi_overbought': 65, 'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 70, 'consec': 1, 'blocked': [0, 1, 4, 5, 6, 7, 8, 14, 15, 17, 19, 22, 23]},
}


def download_data(exchange, symbol: str, years: list) -> pd.DataFrame:
    """Télécharge les données historiques"""
    all_data = []
    for year in years:
        print(f"  📥 {symbol} {year}...", end=" ", flush=True)
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) if year == 2025 else datetime(year, 12, 31, 23, 59, tzinfo=timezone.utc)

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
            except:
                time.sleep(1)
                continue
        print("✅")

    if not all_data:
        return None

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset=['timestamp'])
    return df


def calculate_rsi(closes: pd.Series, period: int) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_stochastic(df: pd.DataFrame, period: int) -> pd.Series:
    low_min = df['low'].rolling(period).min()
    high_max = df['high'].rolling(period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)


def count_consecutive(df: pd.DataFrame) -> tuple:
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    consec_up = is_up.groupby(up_groups).cumsum()
    consec_down = is_down.groupby(down_groups).cumsum()
    return consec_up, consec_down


def backtest_config(df: pd.DataFrame, config: dict) -> list:
    """Backtest une configuration et retourne les trades détaillés"""
    if df is None or len(df) < 50:
        return []

    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], config['rsi_period'])
    df['stoch'] = calculate_stochastic(df, config['stoch_period'])
    df['consec_up'], df['consec_down'] = count_consecutive(df)
    df['hour'] = df['datetime'].dt.hour

    blocked = config.get('blocked', [])

    up_signal = (
        (df['rsi'] < config['rsi_oversold']) &
        (df['stoch'] < config['stoch_oversold']) &
        (~df['hour'].isin(blocked))
    )
    down_signal = (
        (df['rsi'] > config['rsi_overbought']) &
        (df['stoch'] > config['stoch_overbought']) &
        (~df['hour'].isin(blocked))
    )

    if config.get('consec', 1) > 1:
        up_signal = up_signal & (df['consec_down'] >= config['consec'])
        down_signal = down_signal & (df['consec_up'] >= config['consec'])

    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:
            continue

        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if up_signal.iloc[i]:
            win = next_row['close'] > next_row['open']
            trades.append({
                'datetime': row['datetime'],
                'hour': row['hour'],
                'signal': 'UP',
                'rsi': row['rsi'],
                'stoch': row['stoch'],
                'win': win
            })
            last_idx = i
        elif down_signal.iloc[i]:
            win = next_row['close'] < next_row['open']
            trades.append({
                'datetime': row['datetime'],
                'hour': row['hour'],
                'signal': 'DOWN',
                'rsi': row['rsi'],
                'stoch': row['stoch'],
                'win': win
            })
            last_idx = i

    return trades


def analyze_losing_trades(all_trades: list, symbol: str):
    """Analyse détaillée des trades perdants"""
    if not all_trades:
        return

    df = pd.DataFrame(all_trades)
    wins = df[df['win'] == True]
    losses = df[df['win'] == False]

    print(f"\n{'='*60}")
    print(f"📊 ANALYSE {symbol}: {len(wins)} wins / {len(losses)} losses ({len(wins)/len(df)*100:.1f}% WR)")
    print(f"{'='*60}")

    # Analyse par heure
    print(f"\n⏰ WIN RATE PAR HEURE:")
    print("-" * 50)
    hour_stats = df.groupby('hour').agg({'win': ['sum', 'count']})
    hour_stats.columns = ['wins', 'total']
    hour_stats['wr'] = (hour_stats['wins'] / hour_stats['total'] * 100).round(1)
    hour_stats = hour_stats.sort_values('wr')

    bad_hours = []
    for hour in range(24):
        if hour in hour_stats.index:
            row = hour_stats.loc[hour]
            wr = row['wr']
            if wr < 55:
                bad_hours.append(hour)
                status = "🔴 BLOQUER" if wr < 50 else "🟡 FAIBLE"
            else:
                status = "🟢"
            if row['total'] >= 5:  # Au moins 5 trades pour être significatif
                print(f"   {hour:02d}h: {int(row['total']):>3} trades | WR {wr:>5.1f}% {status}")

    print(f"\n   Heures à bloquer (WR < 55%): {sorted(bad_hours)}")

    # Analyse par RSI
    print(f"\n📈 ANALYSE RSI (trades perdants):")
    print("-" * 50)

    up_losses = losses[losses['signal'] == 'UP']
    down_losses = losses[losses['signal'] == 'DOWN']

    if len(up_losses) > 0:
        print(f"   UP perdants: RSI moyen = {up_losses['rsi'].mean():.1f} (min: {up_losses['rsi'].min():.1f}, max: {up_losses['rsi'].max():.1f})")
    if len(down_losses) > 0:
        print(f"   DOWN perdants: RSI moyen = {down_losses['rsi'].mean():.1f} (min: {down_losses['rsi'].min():.1f}, max: {down_losses['rsi'].max():.1f})")

    # Analyse par Stoch
    print(f"\n📉 ANALYSE STOCHASTIC (trades perdants):")
    print("-" * 50)
    if len(up_losses) > 0:
        print(f"   UP perdants: Stoch moyen = {up_losses['stoch'].mean():.1f}")
    if len(down_losses) > 0:
        print(f"   DOWN perdants: Stoch moyen = {down_losses['stoch'].mean():.1f}")

    return bad_hours


def test_stricter_config(df: pd.DataFrame, base_config: dict, symbol: str):
    """Teste des configurations plus strictes"""
    print(f"\n{'='*60}")
    print(f"🔧 TEST CONFIGS STRICTES - {symbol}")
    print(f"{'='*60}")

    results = []

    # Paramètres à tester
    rsi_thresholds = [(30, 70), (25, 75), (20, 80)]
    stoch_thresholds = [(25, 75), (20, 80), (15, 85)]
    consec_options = [1, 2]

    for (rsi_low, rsi_high), (stoch_low, stoch_high), consec in product(rsi_thresholds, stoch_thresholds, consec_options):
        config = base_config.copy()
        config['rsi_oversold'] = rsi_low
        config['rsi_overbought'] = rsi_high
        config['stoch_oversold'] = stoch_low
        config['stoch_overbought'] = stoch_high
        config['consec'] = consec

        trades = backtest_config(df, config)
        if len(trades) < 100:  # Minimum trades pour être significatif
            continue

        wins = sum(1 for t in trades if t['win'])
        wr = wins / len(trades) * 100
        tpd = len(trades) / 730  # 2 ans

        results.append({
            'rsi': f"{rsi_low}/{rsi_high}",
            'stoch': f"{stoch_low}/{stoch_high}",
            'consec': consec,
            'trades': len(trades),
            'tpd': tpd,
            'wr': wr
        })

    # Trier par WR
    results = sorted(results, key=lambda x: x['wr'], reverse=True)

    print(f"\n{'RSI':<10} {'Stoch':<10} {'Consec':<8} {'Trades':<8} {'T/jour':<8} {'WR':<8}")
    print("-" * 60)

    for r in results[:10]:  # Top 10
        status = "✅" if r['wr'] >= 58 else ""
        print(f"{r['rsi']:<10} {r['stoch']:<10} {r['consec']:<8} {r['trades']:<8} {r['tpd']:<8.1f} {r['wr']:<6.1f}% {status}")

    return results


def test_aggressive_blacklist(df: pd.DataFrame, base_config: dict, symbol: str, bad_hours: list):
    """Teste des blacklists plus agressives"""
    print(f"\n{'='*60}")
    print(f"🚫 TEST BLACKLIST AGRESSIVE - {symbol}")
    print(f"{'='*60}")

    current_blocked = base_config.get('blocked', [])

    # Tester différents niveaux de blacklist
    scenarios = [
        ("Actuel", current_blocked),
        ("+ heures <55%", list(set(current_blocked + bad_hours))),
    ]

    # Ajouter les heures proches de 50%
    very_bad = [h for h in bad_hours if h not in current_blocked]
    if very_bad:
        scenarios.append(("+ très faibles", list(set(current_blocked + very_bad[:3]))))

    print(f"\n{'Scénario':<25} {'Blocked':<8} {'Trades':<8} {'WR':<8}")
    print("-" * 55)

    best = None
    for name, blocked in scenarios:
        config = base_config.copy()
        config['blocked'] = blocked

        trades = backtest_config(df, config)
        if not trades:
            continue

        wins = sum(1 for t in trades if t['win'])
        wr = wins / len(trades) * 100
        tpd = len(trades) / 730

        status = "✅" if wr >= 58 else ""
        print(f"{name:<25} {len(blocked):<8} {len(trades):<8} {wr:<6.1f}% {status}")

        if best is None or wr > best['wr']:
            best = {'name': name, 'blocked': blocked, 'wr': wr, 'tpd': tpd}

    return best


def main():
    print("=" * 70)
    print("🎯 OPTIMISATION POUR $15k/MOIS (58% WR)")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']

    all_data = {}
    all_bad_hours = {}
    best_configs = {}

    # 1. Télécharger les données
    print("\n📥 TÉLÉCHARGEMENT DES DONNÉES...")
    for symbol in symbols:
        base = symbol.split('/')[0]
        df = download_data(exchange, symbol, [2024, 2025])
        all_data[base] = df

    # 2. Analyser les trades perdants pour chaque pair
    print("\n" + "=" * 70)
    print("📊 ANALYSE DES TRADES PERDANTS")
    print("=" * 70)

    for symbol in symbols:
        base = symbol.split('/')[0]
        df = all_data[base]
        config = CURRENT_CONFIG[base]

        trades = backtest_config(df, config)
        bad_hours = analyze_losing_trades(trades, base)
        all_bad_hours[base] = bad_hours

    # 3. Tester des configs plus strictes
    print("\n" + "=" * 70)
    print("🔧 TEST CONFIGURATIONS STRICTES")
    print("=" * 70)

    for symbol in symbols:
        base = symbol.split('/')[0]
        df = all_data[base]
        config = CURRENT_CONFIG[base]

        results = test_stricter_config(df, config, base)
        if results:
            best_configs[base] = results[0]

    # 4. Tester blacklists agressives
    print("\n" + "=" * 70)
    print("🚫 TEST BLACKLISTS AGRESSIVES")
    print("=" * 70)

    best_blacklists = {}
    for symbol in symbols:
        base = symbol.split('/')[0]
        df = all_data[base]
        config = CURRENT_CONFIG[base]
        bad_hours = all_bad_hours.get(base, [])

        best = test_aggressive_blacklist(df, config, base, bad_hours)
        if best:
            best_blacklists[base] = best

    # 5. Résumé et recommandations
    print("\n" + "=" * 70)
    print("🎯 RECOMMANDATIONS FINALES")
    print("=" * 70)

    print("\n📊 MEILLEURE CONFIG PAR PAIR:")
    print("-" * 60)

    total_tpd = 0
    weighted_wr = 0

    for base in ['BTC', 'ETH', 'XRP', 'SOL']:
        if base in best_configs:
            cfg = best_configs[base]
            print(f"\n{base}:")
            print(f"   RSI: {cfg['rsi']} | Stoch: {cfg['stoch']} | Consec: {cfg['consec']}")
            print(f"   Trades/jour: {cfg['tpd']:.1f} | WR: {cfg['wr']:.1f}%")
            total_tpd += cfg['tpd']
            weighted_wr += cfg['wr'] * cfg['tpd']

    if total_tpd > 0:
        avg_wr = weighted_wr / total_tpd
        print(f"\n{'='*60}")
        print(f"📈 TOTAL: {total_tpd:.0f} trades/jour | WR moyen: {avg_wr:.1f}%")

        # Calcul PnL
        BET = 100
        ENTRY = 0.52
        shares = BET / ENTRY
        win_profit = shares - BET
        pnl_trade = (avg_wr/100 * win_profit) + ((1 - avg_wr/100) * (-BET))
        pnl_month = pnl_trade * total_tpd * 30

        print(f"💰 PnL estimé: ${pnl_month:,.0f}/mois")

        if pnl_month >= 15000:
            print(f"\n✅ OBJECTIF $15k ATTEINT!")
        else:
            print(f"\n❌ Manque ${15000 - pnl_month:,.0f}")


if __name__ == "__main__":
    main()
