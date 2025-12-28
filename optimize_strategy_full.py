#!/usr/bin/env python3
"""
Optimisation complète de la stratégie pour atteindre $15k/mois
Objectif: 43+ trades/jour avec 58%+ WR
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time
from itertools import product
import json

# Constantes
BET = 100
ENTRY = 0.52
TARGET_PNL = 15000
DAYS_MONTH = 30

shares = BET / ENTRY
WIN_PROFIT = shares - BET  # $92.31


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


def calculate_indicators(df: pd.DataFrame, rsi_period: int, stoch_period: int, atr_period: int = 14):
    """Calcule tous les indicateurs"""
    df = df.copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(span=rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic
    low_min = df['low'].rolling(stoch_period).min()
    high_max = df['high'].rolling(stoch_period).max()
    df['stoch'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Consecutive candles
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    # ATR (Average True Range) - pour filtre volatilité
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(atr_period).mean()
    df['atr_pct'] = df['atr'] / df['close'] * 100  # ATR en %

    # Volume moyen
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']

    # Hour
    df['hour'] = df['datetime'].dt.hour

    return df


def backtest_with_filters(df: pd.DataFrame, config: dict) -> dict:
    """Backtest avec filtres avancés"""
    if df is None or len(df) < 50:
        return None

    blocked = config.get('blocked_hours', [])

    # Signaux de base
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

    # Filtre consécutif
    if config.get('consec', 1) > 1:
        up_signal = up_signal & (df['consec_down'] >= config['consec'])
        down_signal = down_signal & (df['consec_up'] >= config['consec'])

    # Filtre ATR (volatilité minimum)
    if config.get('min_atr_pct', 0) > 0:
        up_signal = up_signal & (df['atr_pct'] >= config['min_atr_pct'])
        down_signal = down_signal & (df['atr_pct'] >= config['min_atr_pct'])

    # Filtre ATR max (éviter trop de volatilité)
    if config.get('max_atr_pct', 100) < 100:
        up_signal = up_signal & (df['atr_pct'] <= config['max_atr_pct'])
        down_signal = down_signal & (df['atr_pct'] <= config['max_atr_pct'])

    # Filtre Volume
    if config.get('min_vol_ratio', 0) > 0:
        up_signal = up_signal & (df['vol_ratio'] >= config['min_vol_ratio'])
        down_signal = down_signal & (df['vol_ratio'] >= config['min_vol_ratio'])

    # Simuler trades
    trades = []
    last_idx = -4

    for i in range(20, len(df) - 1):
        if i - last_idx < 4:
            continue

        if up_signal.iloc[i]:
            next_row = df.iloc[i + 1]
            win = next_row['close'] > next_row['open']
            trades.append({'signal': 'UP', 'win': win, 'hour': df.iloc[i]['hour']})
            last_idx = i
        elif down_signal.iloc[i]:
            next_row = df.iloc[i + 1]
            win = next_row['close'] < next_row['open']
            trades.append({'signal': 'DOWN', 'win': win, 'hour': df.iloc[i]['hour']})
            last_idx = i

    if len(trades) < 50:
        return None

    wins = sum(1 for t in trades if t['win'])
    total = len(trades)
    wr = wins / total
    days = (df['datetime'].max() - df['datetime'].min()).days or 1
    tpd = total / days

    # Calcul PnL
    pnl_per_trade = (wr * WIN_PROFIT) + ((1 - wr) * (-BET))
    pnl_per_day = pnl_per_trade * tpd
    pnl_per_month = pnl_per_day * DAYS_MONTH

    return {
        'trades': total,
        'wins': wins,
        'wr': wr,
        'tpd': tpd,
        'pnl_trade': pnl_per_trade,
        'pnl_month': pnl_per_month
    }


def find_optimal_blacklist(df: pd.DataFrame, base_config: dict) -> list:
    """Trouve la blacklist optimale qui maximise le PnL"""
    df_calc = calculate_indicators(df, base_config['rsi_period'], base_config['stoch_period'])

    # D'abord, calculer le WR par heure
    config = base_config.copy()
    config['blocked_hours'] = []

    # Backtest sans blacklist pour avoir les stats par heure
    up_signal = (df_calc['rsi'] < config['rsi_oversold']) & (df_calc['stoch'] < config['stoch_oversold'])
    down_signal = (df_calc['rsi'] > config['rsi_overbought']) & (df_calc['stoch'] > config['stoch_overbought'])

    if config.get('consec', 1) > 1:
        up_signal = up_signal & (df_calc['consec_down'] >= config['consec'])
        down_signal = down_signal & (df_calc['consec_up'] >= config['consec'])

    hour_stats = {}
    last_idx = -4

    for i in range(20, len(df_calc) - 1):
        if i - last_idx < 4:
            continue

        hour = df_calc.iloc[i]['hour']

        if up_signal.iloc[i]:
            win = df_calc.iloc[i + 1]['close'] > df_calc.iloc[i + 1]['open']
            if hour not in hour_stats:
                hour_stats[hour] = {'wins': 0, 'total': 0}
            hour_stats[hour]['total'] += 1
            if win:
                hour_stats[hour]['wins'] += 1
            last_idx = i
        elif down_signal.iloc[i]:
            win = df_calc.iloc[i + 1]['close'] < df_calc.iloc[i + 1]['open']
            if hour not in hour_stats:
                hour_stats[hour] = {'wins': 0, 'total': 0}
            hour_stats[hour]['total'] += 1
            if win:
                hour_stats[hour]['wins'] += 1
            last_idx = i

    # Calculer WR et PnL contribution par heure
    hour_pnl = {}
    for hour, stats in hour_stats.items():
        if stats['total'] >= 10:
            wr = stats['wins'] / stats['total']
            pnl_per_trade = (wr * WIN_PROFIT) + ((1 - wr) * (-BET))
            hour_pnl[hour] = {
                'wr': wr,
                'trades': stats['total'],
                'pnl_contrib': pnl_per_trade * stats['total']
            }

    # Bloquer les heures avec PnL négatif
    bad_hours = [h for h, data in hour_pnl.items() if data['pnl_contrib'] < 0]

    return sorted(bad_hours)


def optimize_pair(df: pd.DataFrame, symbol: str) -> dict:
    """Optimise la configuration pour une pair"""
    print(f"\n{'='*60}")
    print(f"🔧 OPTIMISATION {symbol}")
    print(f"{'='*60}")

    results = []

    # Paramètres à tester
    rsi_periods = [5, 7, 9]
    rsi_thresholds = [(30, 70), (35, 65), (25, 75)]
    stoch_thresholds = [(25, 75), (30, 70), (20, 80)]
    consec_options = [1, 2]
    atr_filters = [(0, 100), (0.1, 100), (0.2, 100)]  # (min, max) ATR%
    vol_filters = [0, 0.8, 1.0]  # min volume ratio

    total_combos = len(rsi_periods) * len(rsi_thresholds) * len(stoch_thresholds) * len(consec_options) * len(atr_filters) * len(vol_filters)
    print(f"   Testing {total_combos} combinations...")

    tested = 0
    for rsi_p in rsi_periods:
        for (rsi_low, rsi_high) in rsi_thresholds:
            for (stoch_low, stoch_high) in stoch_thresholds:
                for consec in consec_options:
                    for (min_atr, max_atr) in atr_filters:
                        for min_vol in vol_filters:

                            config = {
                                'rsi_period': rsi_p,
                                'rsi_oversold': rsi_low,
                                'rsi_overbought': rsi_high,
                                'stoch_period': 5,
                                'stoch_oversold': stoch_low,
                                'stoch_overbought': stoch_high,
                                'consec': consec,
                                'min_atr_pct': min_atr,
                                'max_atr_pct': max_atr,
                                'min_vol_ratio': min_vol,
                                'blocked_hours': []
                            }

                            df_calc = calculate_indicators(df, rsi_p, 5)
                            result = backtest_with_filters(df_calc, config)

                            if result and result['tpd'] >= 3:  # Minimum 3 trades/day
                                results.append({
                                    **config,
                                    **result
                                })

                            tested += 1

    if not results:
        print(f"   ❌ Aucune config valide trouvée")
        return None

    # Trier par PnL mensuel
    results = sorted(results, key=lambda x: x['pnl_month'], reverse=True)

    # Top 5
    print(f"\n   📊 TOP 5 CONFIGS (par PnL):")
    print(f"   {'RSI':<12} {'Stoch':<12} {'Consec':<8} {'ATR':<10} {'Vol':<6} {'T/j':<6} {'WR':<8} {'PnL/mois'}")
    print("   " + "-" * 80)

    for r in results[:5]:
        rsi_str = f"{r['rsi_oversold']}/{r['rsi_overbought']}"
        stoch_str = f"{r['stoch_oversold']}/{r['stoch_overbought']}"
        atr_str = f"{r['min_atr_pct']:.1f}"
        print(f"   {rsi_str:<12} {stoch_str:<12} {r['consec']:<8} {atr_str:<10} {r['min_vol_ratio']:<6.1f} {r['tpd']:<6.1f} {r['wr']*100:<6.1f}% ${r['pnl_month']:>8,.0f}")

    best = results[0]

    # Trouver la blacklist optimale pour la meilleure config
    print(f"\n   🚫 Recherche blacklist optimale...")
    df_calc = calculate_indicators(df, best['rsi_period'], 5)
    optimal_blacklist = find_optimal_blacklist(df, best)

    # Re-tester avec la blacklist
    best['blocked_hours'] = optimal_blacklist
    result_with_bl = backtest_with_filters(df_calc, best)

    if result_with_bl:
        print(f"   Blacklist: {optimal_blacklist}")
        print(f"   Avec blacklist: {result_with_bl['tpd']:.1f} T/j | {result_with_bl['wr']*100:.1f}% WR | ${result_with_bl['pnl_month']:,.0f}/mois")

        if result_with_bl['pnl_month'] > best['pnl_month']:
            best = {**best, **result_with_bl}

    return best


def main():
    print("=" * 70)
    print("🎯 OPTIMISATION COMPLÈTE - OBJECTIF: $15k/mois avec $100/trade")
    print("=" * 70)
    print(f"   Besoin: 43+ trades/jour avec 58%+ WR")
    print(f"   Ou: combinaison équivalente en PnL")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']

    # Télécharger les données
    print("\n📥 TÉLÉCHARGEMENT DES DONNÉES (2024-2025)...")
    all_data = {}
    for symbol in symbols:
        base = symbol.split('/')[0]
        df = download_data(exchange, symbol, [2024, 2025])
        all_data[base] = df

    # Optimiser chaque pair
    best_configs = {}
    for symbol in symbols:
        base = symbol.split('/')[0]
        df = all_data[base]
        best = optimize_pair(df, base)
        if best:
            best_configs[base] = best

    # Résumé final
    print("\n" + "=" * 70)
    print("🏆 MEILLEURES CONFIGURATIONS TROUVÉES")
    print("=" * 70)

    total_tpd = 0
    total_pnl = 0

    for base in ['BTC', 'ETH', 'XRP', 'SOL']:
        if base in best_configs:
            cfg = best_configs[base]
            print(f"\n{base}:")
            print(f"   RSI({cfg['rsi_period']}): {cfg['rsi_oversold']}/{cfg['rsi_overbought']}")
            print(f"   Stoch: {cfg['stoch_oversold']}/{cfg['stoch_overbought']}")
            print(f"   Consec: {cfg['consec']}")
            if cfg.get('min_atr_pct', 0) > 0:
                print(f"   ATR min: {cfg['min_atr_pct']}%")
            if cfg.get('min_vol_ratio', 0) > 0:
                print(f"   Vol min: {cfg['min_vol_ratio']}x")
            print(f"   Blacklist: {cfg.get('blocked_hours', [])}")
            print(f"   → {cfg['tpd']:.1f} trades/jour | {cfg['wr']*100:.1f}% WR | ${cfg['pnl_month']:,.0f}/mois")

            total_tpd += cfg['tpd']
            total_pnl += cfg['pnl_month']

    print("\n" + "=" * 70)
    print("📊 TOTAL 4 PAIRS")
    print("=" * 70)
    print(f"   Trades/jour: {total_tpd:.0f}")
    print(f"   PnL/mois: ${total_pnl:,.0f}")

    pct_target = total_pnl / TARGET_PNL * 100
    print(f"\n   🎯 vs Objectif $15k: {pct_target:.0f}%")

    if total_pnl >= TARGET_PNL:
        print(f"\n   ✅ OBJECTIF ATTEINT!")
    else:
        gap = TARGET_PNL - total_pnl
        print(f"\n   ❌ Manque ${gap:,.0f}")
        bet_needed = BET * (TARGET_PNL / total_pnl)
        print(f"   💡 Avec ${bet_needed:.0f}/trade → ${TARGET_PNL:,}/mois")

    # Sauvegarder les configs
    output = {
        'configs': {},
        'summary': {
            'total_tpd': total_tpd,
            'total_pnl_month': total_pnl,
            'target': TARGET_PNL,
            'bet': BET
        }
    }

    for base, cfg in best_configs.items():
        output['configs'][base] = {
            'rsi_period': cfg['rsi_period'],
            'rsi_oversold': cfg['rsi_oversold'],
            'rsi_overbought': cfg['rsi_overbought'],
            'stoch_period': 5,
            'stoch_oversold': cfg['stoch_oversold'],
            'stoch_overbought': cfg['stoch_overbought'],
            'consec': cfg['consec'],
            'min_atr_pct': cfg.get('min_atr_pct', 0),
            'min_vol_ratio': cfg.get('min_vol_ratio', 0),
            'blocked_hours': cfg.get('blocked_hours', []),
            'expected_tpd': round(cfg['tpd'], 1),
            'expected_wr': round(cfg['wr'] * 100, 1),
            'expected_pnl_month': round(cfg['pnl_month'], 0)
        }

    with open('optimal_config.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n   📁 Config sauvegardée: optimal_config.json")


if __name__ == "__main__":
    main()
