#!/usr/bin/env python3
"""
Applique les patterns découverts dans l'analyse des trades perdants
pour améliorer le win rate et atteindre $15k/mois
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ccxt

# Configuration
PAIRS = ['BTC', 'ETH', 'XRP', 'SOL']
ENTRY_PRICE = 0.52
BET = 100
WIN_PROFIT = (BET / ENTRY_PRICE) - BET  # $92.31
LOSS = -BET
TARGET_PNL = 15000

def fetch_data(symbol, days=730):
    """Récupère les données historiques"""
    exchange = ccxt.binance()
    timeframe = '15m'
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=days)).isoformat())

    all_candles = []
    while True:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        since = candles[-1][0] + 1
        if len(candles) < 1000:
            break

    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_indicators(df):
    """Calcule tous les indicateurs"""
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic
    low_min = df['low'].rolling(window=5).min()
    high_max = df['high'].rolling(window=5).max()
    df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min)
    df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()

    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # Volume ratio
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']

    # Consecutive candles
    df['candle_dir'] = np.where(df['close'] > df['open'], 1, -1)
    df['consec_up'] = 0
    df['consec_down'] = 0

    consec_up = 0
    consec_down = 0
    for i in range(len(df)):
        if df['candle_dir'].iloc[i] == 1:
            consec_up += 1
            consec_down = 0
        else:
            consec_down += 1
            consec_up = 0
        df.loc[df.index[i], 'consec_up'] = consec_up
        df.loc[df.index[i], 'consec_down'] = consec_down

    # Hour and day
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek

    return df

def simulate_trade(row, direction):
    """Simule un trade et retourne le résultat"""
    next_close = row['next_close']
    current_close = row['close']

    if direction == 'UP':
        return next_close > current_close
    else:
        return next_close < current_close

def backtest_with_filters(df, config, pair_name):
    """
    Backtest avec les nouveaux filtres basés sur l'analyse des pertes
    """
    results = []

    for i in range(30, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # Filtre heure bloquée
        if row['hour'] in config.get('blocked_hours', []):
            continue

        # Filtre jour de la semaine (0=Lundi)
        if row['day_of_week'] in config.get('blocked_days', []):
            continue

        signal = None

        # Signal UP: RSI oversold + Stoch oversold + consec down
        if (row['rsi'] < config['rsi_oversold'] and
            row['stoch_k'] < config['stoch_oversold'] and
            row['consec_down'] >= config['consec_threshold']):

            # Filtre MACD histogram (pour UP, on préfère MACD hist négatif = oversold)
            if config.get('use_macd_filter', False):
                if row['macd_hist'] > config.get('macd_hist_max_up', 0.5):
                    continue

            # Filtre volume
            if config.get('use_volume_filter', False):
                if row['volume_ratio'] < config.get('min_volume_ratio', 0.7):
                    continue

            signal = 'UP'

        # Signal DOWN: RSI overbought + Stoch overbought + consec up
        elif (row['rsi'] > config['rsi_overbought'] and
              row['stoch_k'] > config['stoch_overbought'] and
              row['consec_up'] >= config['consec_threshold']):

            # Filtre MACD histogram (pour DOWN, on préfère MACD hist positif = overbought)
            if config.get('use_macd_filter', False):
                if row['macd_hist'] < config.get('macd_hist_min_down', -0.5):
                    continue

            # Filtre volume
            if config.get('use_volume_filter', False):
                if row['volume_ratio'] < config.get('min_volume_ratio', 0.7):
                    continue

            signal = 'DOWN'

        if signal:
            # Simuler le trade
            win = simulate_trade({
                'close': row['close'],
                'next_close': next_row['close']
            }, signal)

            results.append({
                'pair': pair_name,
                'timestamp': row['timestamp'],
                'signal': signal,
                'win': win,
                'rsi': row['rsi'],
                'stoch_k': row['stoch_k'],
                'macd_hist': row['macd_hist'],
                'volume_ratio': row['volume_ratio'],
                'hour': row['hour'],
                'day_of_week': row['day_of_week']
            })

    return pd.DataFrame(results)

def test_filter_combination(all_data, filter_config):
    """Teste une combinaison de filtres sur toutes les paires"""
    all_results = []

    for pair, df in all_data.items():
        config = filter_config.copy()
        # Appliquer les heures bloquées spécifiques à la paire si définies
        if pair in filter_config.get('pair_blocked_hours', {}):
            config['blocked_hours'] = filter_config['pair_blocked_hours'][pair]

        results = backtest_with_filters(df, config, pair)
        all_results.append(results)

    if not all_results:
        return None

    combined = pd.concat(all_results, ignore_index=True)
    if len(combined) == 0:
        return None

    wins = combined['win'].sum()
    total = len(combined)
    wr = wins / total if total > 0 else 0

    days = (combined['timestamp'].max() - combined['timestamp'].min()).days
    trades_per_day = total / days if days > 0 else 0

    pnl_per_trade = (wr * WIN_PROFIT) + ((1 - wr) * LOSS)
    daily_pnl = pnl_per_trade * trades_per_day
    monthly_pnl = daily_pnl * 30

    return {
        'total_trades': total,
        'wins': wins,
        'wr': wr,
        'trades_per_day': trades_per_day,
        'pnl_per_trade': pnl_per_trade,
        'daily_pnl': daily_pnl,
        'monthly_pnl': monthly_pnl,
        'days': days
    }

def main():
    print("=" * 70)
    print("APPLICATION DES PATTERNS DES TRADES PERDANTS")
    print("Objectif: $15,000/mois avec $100/trade")
    print("=" * 70)

    # Charger les données
    print("\n📊 Chargement des données historiques (2 ans)...")
    all_data = {}
    for pair in PAIRS:
        symbol = f"{pair}/USDT"
        print(f"  Chargement {pair}...", end=" ")
        df = fetch_data(symbol)
        df = calculate_indicators(df)
        all_data[pair] = df
        print(f"✓ ({len(df)} candles)")

    # Configuration de base (avant optimisation)
    base_config = {
        'rsi_oversold': 35,
        'rsi_overbought': 65,
        'stoch_oversold': 30,
        'stoch_overbought': 70,
        'consec_threshold': 1,
        'blocked_hours': [],
        'blocked_days': [],
        'use_macd_filter': False,
        'use_volume_filter': False,
    }

    print("\n" + "=" * 70)
    print("TEST 1: Configuration de base (référence)")
    print("=" * 70)
    result_base = test_filter_combination(all_data, base_config)
    if result_base:
        print(f"  Trades: {result_base['total_trades']:,} | WR: {result_base['wr']:.1%}")
        print(f"  Trades/jour: {result_base['trades_per_day']:.1f}")
        print(f"  PnL mensuel: ${result_base['monthly_pnl']:,.0f}")

    # Test avec les patterns découverts
    test_configs = [
        {
            'name': "RSI strict (25/75)",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
            }
        },
        {
            'name': "RSI très strict (20/80)",
            'config': {
                **base_config,
                'rsi_oversold': 20,
                'rsi_overbought': 80,
            }
        },
        {
            'name': "Bloquer lundi (jour 0)",
            'config': {
                **base_config,
                'blocked_days': [0],  # Monday
            }
        },
        {
            'name': "Bloquer heures faibles (4, 6, 14, 15, 17)",
            'config': {
                **base_config,
                'blocked_hours': [4, 6, 14, 15, 17],
            }
        },
        {
            'name': "MACD filter activé",
            'config': {
                **base_config,
                'use_macd_filter': True,
                'macd_hist_max_up': 0.0,  # Pour UP, MACD hist doit être < 0
                'macd_hist_min_down': 0.0,  # Pour DOWN, MACD hist doit être > 0
            }
        },
        {
            'name': "Volume filter (ratio > 0.8)",
            'config': {
                **base_config,
                'use_volume_filter': True,
                'min_volume_ratio': 0.8,
            }
        },
        {
            'name': "COMBO: RSI strict + Lundi bloqué",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_days': [0],
            }
        },
        {
            'name': "COMBO: RSI strict + Heures faibles",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_hours': [4, 6, 14, 15, 17],
            }
        },
        {
            'name': "COMBO: RSI strict + MACD",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'use_macd_filter': True,
                'macd_hist_max_up': 0.0,
                'macd_hist_min_down': 0.0,
            }
        },
        {
            'name': "COMBO FULL: RSI + Lundi + Heures",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_days': [0],
                'blocked_hours': [4, 6, 14, 15, 17],
            }
        },
        {
            'name': "COMBO FULL + MACD",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_days': [0],
                'blocked_hours': [4, 6, 14, 15, 17],
                'use_macd_filter': True,
                'macd_hist_max_up': 0.0,
                'macd_hist_min_down': 0.0,
            }
        },
        {
            'name': "COMBO FULL + Volume",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_days': [0],
                'blocked_hours': [4, 6, 14, 15, 17],
                'use_volume_filter': True,
                'min_volume_ratio': 0.8,
            }
        },
        {
            'name': "COMBO ULTIMATE (tous les filtres)",
            'config': {
                **base_config,
                'rsi_oversold': 25,
                'rsi_overbought': 75,
                'blocked_days': [0],
                'blocked_hours': [4, 6, 14, 15, 17],
                'use_macd_filter': True,
                'macd_hist_max_up': 0.0,
                'macd_hist_min_down': 0.0,
                'use_volume_filter': True,
                'min_volume_ratio': 0.8,
            }
        },
    ]

    print("\n" + "=" * 70)
    print("TESTS DES FILTRES BASÉS SUR L'ANALYSE DES PERTES")
    print("=" * 70)

    results_summary = []

    for test in test_configs:
        result = test_filter_combination(all_data, test['config'])
        if result:
            print(f"\n📊 {test['name']}")
            print(f"   Trades: {result['total_trades']:,} | WR: {result['wr']:.1%} | Trades/jour: {result['trades_per_day']:.1f}")
            print(f"   PnL mensuel: ${result['monthly_pnl']:,.0f} ({result['monthly_pnl']/TARGET_PNL*100:.0f}% de l'objectif)")

            results_summary.append({
                'name': test['name'],
                **result
            })

    # Trouver la meilleure config
    print("\n" + "=" * 70)
    print("CLASSEMENT PAR PNL MENSUEL")
    print("=" * 70)

    results_summary.sort(key=lambda x: x['monthly_pnl'], reverse=True)

    for i, r in enumerate(results_summary[:5], 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        target_pct = r['monthly_pnl'] / TARGET_PNL * 100
        print(f"{emoji} #{i}: {r['name']}")
        print(f"      WR: {r['wr']:.1%} | Trades/jour: {r['trades_per_day']:.1f} | PnL: ${r['monthly_pnl']:,.0f} ({target_pct:.0f}%)")

    # Analyse: pourquoi on n'atteint pas $15k
    print("\n" + "=" * 70)
    print("ANALYSE: POURQUOI $15k EST DIFFICILE À ATTEINDRE")
    print("=" * 70)

    best = results_summary[0]

    # Calcul inverse: combien de trades/jour faut-il pour $15k avec ce WR?
    pnl_per_trade = (best['wr'] * WIN_PROFIT) + ((1 - best['wr']) * LOSS)
    trades_needed_per_day = TARGET_PNL / 30 / pnl_per_trade

    print(f"\nMeilleure config: {best['name']}")
    print(f"  - Win Rate actuel: {best['wr']:.1%}")
    print(f"  - PnL par trade: ${pnl_per_trade:.2f}")
    print(f"  - Trades/jour actuels: {best['trades_per_day']:.1f}")
    print(f"  - Trades/jour nécessaires pour $15k: {trades_needed_per_day:.1f}")

    # Calcul inverse: quel WR faut-il pour $15k avec ce nombre de trades?
    # monthly_pnl = ((wr * WIN_PROFIT) + ((1-wr) * LOSS)) * trades_per_day * 30
    # 15000 = ((wr * 92.31) + ((1-wr) * -100)) * trades_per_day * 30
    # 15000 = (wr * 92.31 - 100 + wr * 100) * trades_per_day * 30
    # 15000 = (wr * 192.31 - 100) * trades_per_day * 30
    # 15000 / (trades_per_day * 30) = wr * 192.31 - 100
    # (15000 / (trades_per_day * 30) + 100) / 192.31 = wr

    wr_needed = (TARGET_PNL / (best['trades_per_day'] * 30) + BET) / (WIN_PROFIT + BET)

    print(f"\nPour atteindre $15k avec {best['trades_per_day']:.1f} trades/jour:")
    print(f"  - Win Rate nécessaire: {wr_needed:.1%}")
    print(f"  - Gap avec WR actuel: {(wr_needed - best['wr'])*100:.1f} points")

    # Test avec plus de trades (RSI moins strict)
    print("\n" + "=" * 70)
    print("TEST ALTERNATIF: Plus de trades avec RSI modéré")
    print("=" * 70)

    more_trades_configs = [
        {
            'name': "RSI 30/70 + Lundi + Heures",
            'config': {
                **base_config,
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'blocked_days': [0],
                'blocked_hours': [4, 6, 17],  # Moins d'heures bloquées
            }
        },
        {
            'name': "RSI 32/68 + Lundi + Heures min",
            'config': {
                **base_config,
                'rsi_oversold': 32,
                'rsi_overbought': 68,
                'blocked_days': [0],
                'blocked_hours': [4],  # Une seule heure bloquée
            }
        },
        {
            'name': "RSI 35/65 + Lundi only",
            'config': {
                **base_config,
                'rsi_oversold': 35,
                'rsi_overbought': 65,
                'blocked_days': [0],
            }
        },
    ]

    for test in more_trades_configs:
        result = test_filter_combination(all_data, test['config'])
        if result:
            target_pct = result['monthly_pnl'] / TARGET_PNL * 100
            print(f"\n📊 {test['name']}")
            print(f"   WR: {result['wr']:.1%} | Trades/jour: {result['trades_per_day']:.1f}")
            print(f"   PnL mensuel: ${result['monthly_pnl']:,.0f} ({target_pct:.0f}% de l'objectif)")

if __name__ == "__main__":
    main()
