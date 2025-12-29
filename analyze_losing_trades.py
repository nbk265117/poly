#!/usr/bin/env python3
"""
ANALYSE APPROFONDIE DES TRADES PERDANTS 2024-2025
==================================================
Objectif: Trouver TOUS les points communs des pertes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ccxt

# Configuration strategy actuelle
RSI_PERIOD = 7
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 58
STOCH_PERIOD = 5
STOCH_OVERSOLD = 30
STOCH_OVERBOUGHT = 80

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']


def fetch_historical_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical 15m data from Binance"""
    exchange = ccxt.binance()

    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

    all_candles = []
    current_ts = start_ts

    print(f"  Fetching {symbol}...", end=" ", flush=True)

    while current_ts < end_ts:
        candles = exchange.fetch_ohlcv(symbol, '15m', current_ts, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        current_ts = candles[-1][0] + 1

    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[(df['timestamp'] >= start_date) & (df['timestamp'] < end_date)]

    print(f"{len(df)} candles")
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators"""
    df = df.copy()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Stochastic
    low_min = df['low'].rolling(STOCH_PERIOD).min()
    high_max = df['high'].rolling(STOCH_PERIOD).max()
    df['stoch'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # Volatility (ATR)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_pct'] = df['atr'] / df['close'] * 100

    # Volume analysis
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']

    # Trend (SMA)
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    df['trend'] = np.where(df['sma_20'] > df['sma_50'], 'UP', 'DOWN')

    # Price change
    df['pct_change'] = df['close'].pct_change() * 100
    df['pct_change_5'] = df['close'].pct_change(5) * 100

    # Candle patterns
    df['body'] = abs(df['close'] - df['open'])
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['candle_range'] = df['high'] - df['low']
    df['body_ratio'] = df['body'] / df['candle_range'].replace(0, np.nan)

    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    # Momentum
    df['momentum'] = df['close'] - df['close'].shift(10)
    df['momentum_pct'] = df['momentum'] / df['close'].shift(10) * 100

    # RSI divergence (price up but RSI down, or vice versa)
    df['price_dir'] = np.sign(df['close'] - df['close'].shift(5))
    df['rsi_dir'] = np.sign(df['rsi'] - df['rsi'].shift(5))
    df['divergence'] = df['price_dir'] != df['rsi_dir']

    return df


def generate_signals_and_results(df: pd.DataFrame) -> pd.DataFrame:
    """Generate signals and determine win/loss"""
    df = df.copy()

    # Generate signals
    df['signal'] = None

    # UP signal: RSI < 38 AND Stoch < 30
    up_condition = (df['rsi'] < RSI_OVERSOLD) & (df['stoch'] < STOCH_OVERSOLD)
    df.loc[up_condition, 'signal'] = 'UP'

    # DOWN signal: RSI > 58 AND Stoch > 80
    down_condition = (df['rsi'] > RSI_OVERBOUGHT) & (df['stoch'] > STOCH_OVERBOUGHT)
    df.loc[down_condition, 'signal'] = 'DOWN'

    # Calculate result (next candle direction)
    df['next_close'] = df['close'].shift(-1)
    df['next_direction'] = np.where(df['next_close'] > df['close'], 'UP', 'DOWN')

    # Win if signal matches next direction
    df['win'] = df['signal'] == df['next_direction']

    return df


def run_analysis():
    """Main analysis function"""
    print("=" * 70)
    print("ANALYSE DES TRADES PERDANTS 2024-2025")
    print("=" * 70)

    all_trades = []

    # Fetch and process data for each symbol
    for symbol in SYMBOLS:
        print(f"\n{'='*50}")
        print(f"Processing {symbol}")
        print("=" * 50)

        # 2024 data
        print("\n2024:")
        df_2024 = fetch_historical_data(symbol, '2024-01-01', '2025-01-01')
        df_2024 = calculate_indicators(df_2024)
        df_2024 = generate_signals_and_results(df_2024)
        df_2024['symbol'] = symbol
        df_2024['year'] = 2024

        # 2025 data
        print("2025:")
        df_2025 = fetch_historical_data(symbol, '2025-01-01', '2025-12-29')
        df_2025 = calculate_indicators(df_2025)
        df_2025 = generate_signals_and_results(df_2025)
        df_2025['symbol'] = symbol
        df_2025['year'] = 2025

        all_trades.append(df_2024[df_2024['signal'].notna()])
        all_trades.append(df_2025[df_2025['signal'].notna()])

    # Combine all trades
    trades = pd.concat(all_trades, ignore_index=True)
    trades['hour'] = trades['timestamp'].dt.hour
    trades['day'] = trades['timestamp'].dt.dayofweek
    trades['month'] = trades['timestamp'].dt.month

    # Separate winners and losers
    winners = trades[trades['win'] == True]
    losers = trades[trades['win'] == False]

    print("\n" + "=" * 70)
    print("STATISTIQUES GLOBALES")
    print("=" * 70)
    print(f"Total trades: {len(trades):,}")
    print(f"Winners: {len(winners):,} ({len(winners)/len(trades)*100:.1f}%)")
    print(f"Losers: {len(losers):,} ({len(losers)/len(trades)*100:.1f}%)")

    # ===== ANALYSE DES PERDANTS =====

    print("\n" + "=" * 70)
    print("ANALYSE DETAILLEE DES TRADES PERDANTS")
    print("=" * 70)

    # 1. Par heure
    print("\n📊 1. DISTRIBUTION PAR HEURE (UTC)")
    print("-" * 50)
    hour_stats = []
    for hour in range(24):
        hour_trades = trades[trades['hour'] == hour]
        hour_losers = losers[losers['hour'] == hour]
        if len(hour_trades) > 0:
            loss_rate = len(hour_losers) / len(hour_trades) * 100
            hour_stats.append({
                'hour': hour,
                'total': len(hour_trades),
                'losses': len(hour_losers),
                'loss_rate': loss_rate
            })

    hour_df = pd.DataFrame(hour_stats).sort_values('loss_rate', ascending=False)
    print("\nHeures avec le PLUS de pertes:")
    for _, row in hour_df.head(10).iterrows():
        bar = "█" * int(row['loss_rate'] / 2)
        print(f"  {int(row['hour']):02d}:00 UTC → {row['loss_rate']:.1f}% loss rate ({row['losses']}/{row['total']}) {bar}")

    print("\nHeures avec le MOINS de pertes:")
    for _, row in hour_df.tail(5).iterrows():
        bar = "█" * int(row['loss_rate'] / 2)
        print(f"  {int(row['hour']):02d}:00 UTC → {row['loss_rate']:.1f}% loss rate ({row['losses']}/{row['total']}) {bar}")

    # 2. Par jour
    print("\n📊 2. DISTRIBUTION PAR JOUR")
    print("-" * 50)
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    day_stats = []
    for day in range(7):
        day_trades = trades[trades['day'] == day]
        day_losers = losers[losers['day'] == day]
        if len(day_trades) > 0:
            loss_rate = len(day_losers) / len(day_trades) * 100
            day_stats.append({
                'day': day,
                'name': days[day],
                'total': len(day_trades),
                'losses': len(day_losers),
                'loss_rate': loss_rate
            })

    day_df = pd.DataFrame(day_stats).sort_values('loss_rate', ascending=False)
    for _, row in day_df.iterrows():
        bar = "█" * int(row['loss_rate'] / 2)
        status = "⚠️" if row['loss_rate'] > 45 else "✅"
        print(f"  {status} {row['name']:10} → {row['loss_rate']:.1f}% loss rate ({row['losses']}/{row['total']}) {bar}")

    # 3. Par type de signal
    print("\n📊 3. PAR TYPE DE SIGNAL")
    print("-" * 50)
    for signal_type in ['UP', 'DOWN']:
        signal_trades = trades[trades['signal'] == signal_type]
        signal_losers = losers[losers['signal'] == signal_type]
        loss_rate = len(signal_losers) / len(signal_trades) * 100
        print(f"  Signal {signal_type}: {loss_rate:.1f}% loss rate ({len(signal_losers)}/{len(signal_trades)})")

    # 4. Par niveau RSI
    print("\n📊 4. PAR NIVEAU RSI A L'ENTREE")
    print("-" * 50)

    # Pour les signaux UP (RSI < 38)
    print("\nSignaux UP (RSI < 38):")
    up_trades = trades[trades['signal'] == 'UP']
    up_losers = losers[losers['signal'] == 'UP']

    rsi_ranges = [(0, 15), (15, 25), (25, 30), (30, 35), (35, 38)]
    for low, high in rsi_ranges:
        range_trades = up_trades[(up_trades['rsi'] >= low) & (up_trades['rsi'] < high)]
        range_losers = up_losers[(up_losers['rsi'] >= low) & (up_losers['rsi'] < high)]
        if len(range_trades) > 0:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} RSI {low}-{high}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # Pour les signaux DOWN (RSI > 58)
    print("\nSignaux DOWN (RSI > 58):")
    down_trades = trades[trades['signal'] == 'DOWN']
    down_losers = losers[losers['signal'] == 'DOWN']

    rsi_ranges = [(58, 65), (65, 70), (70, 75), (75, 85), (85, 100)]
    for low, high in rsi_ranges:
        range_trades = down_trades[(down_trades['rsi'] >= low) & (down_trades['rsi'] < high)]
        range_losers = down_losers[(down_losers['rsi'] >= low) & (down_losers['rsi'] < high)]
        if len(range_trades) > 0:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} RSI {low}-{high}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # 5. Par niveau Stochastic
    print("\n📊 5. PAR NIVEAU STOCHASTIC A L'ENTREE")
    print("-" * 50)

    print("\nSignaux UP (Stoch < 30):")
    stoch_ranges = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30)]
    for low, high in stoch_ranges:
        range_trades = up_trades[(up_trades['stoch'] >= low) & (up_trades['stoch'] < high)]
        range_losers = up_losers[(up_losers['stoch'] >= low) & (up_losers['stoch'] < high)]
        if len(range_trades) > 0:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} Stoch {low}-{high}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    print("\nSignaux DOWN (Stoch > 80):")
    stoch_ranges = [(80, 85), (85, 90), (90, 95), (95, 100)]
    for low, high in stoch_ranges:
        range_trades = down_trades[(down_trades['stoch'] >= low) & (down_trades['stoch'] < high)]
        range_losers = down_losers[(down_losers['stoch'] >= low) & (down_losers['stoch'] < high)]
        if len(range_trades) > 0:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} Stoch {low}-{high}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # 6. Par volatilité (ATR)
    print("\n📊 6. PAR VOLATILITE (ATR %)")
    print("-" * 50)

    # Quartiles de volatilité
    trades['vol_quartile'] = pd.qcut(trades['atr_pct'], 4, labels=['Très faible', 'Faible', 'Moyenne', 'Haute'])

    for quartile in ['Très faible', 'Faible', 'Moyenne', 'Haute']:
        q_trades = trades[trades['vol_quartile'] == quartile]
        q_losers = losers[losers.index.isin(q_trades.index)]
        if len(q_trades) > 0:
            loss_rate = len(q_losers) / len(q_trades) * 100
            avg_atr = q_trades['atr_pct'].mean()
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} {quartile:12} (ATR ~{avg_atr:.2f}%): {loss_rate:.1f}% loss ({len(q_losers)}/{len(q_trades)}) {bar}")

    # 7. Par volume
    print("\n📊 7. PAR VOLUME (ratio vs moyenne)")
    print("-" * 50)

    vol_ranges = [(0, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 100)]
    vol_labels = ['Très bas (<0.5x)', 'Bas (0.5-0.75x)', 'Normal bas (0.75-1x)',
                  'Normal haut (1-1.5x)', 'Haut (1.5-2x)', 'Très haut (>2x)']

    for (low, high), label in zip(vol_ranges, vol_labels):
        range_trades = trades[(trades['vol_ratio'] >= low) & (trades['vol_ratio'] < high)]
        range_losers = losers[losers.index.isin(range_trades.index)]
        if len(range_trades) > 0:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} {label:22}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # 8. Par tendance
    print("\n📊 8. PAR TENDANCE (SMA20 vs SMA50)")
    print("-" * 50)

    for trend in ['UP', 'DOWN']:
        trend_trades = trades[trades['trend'] == trend]
        trend_losers = losers[losers.index.isin(trend_trades.index)]
        if len(trend_trades) > 0:
            loss_rate = len(trend_losers) / len(trend_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} Tendance {trend}: {loss_rate:.1f}% loss ({len(trend_losers)}/{len(trend_trades)}) {bar}")

    # Signal contre tendance vs avec tendance
    print("\n  Signal AVEC la tendance vs CONTRE:")
    with_trend = trades[trades['signal'] == trades['trend']]
    against_trend = trades[trades['signal'] != trades['trend']]

    with_losers = losers[losers.index.isin(with_trend.index)]
    against_losers = losers[losers.index.isin(against_trend.index)]

    with_loss_rate = len(with_losers) / len(with_trend) * 100 if len(with_trend) > 0 else 0
    against_loss_rate = len(against_losers) / len(against_trend) * 100 if len(against_trend) > 0 else 0

    print(f"    ✅ AVEC tendance:   {with_loss_rate:.1f}% loss ({len(with_losers)}/{len(with_trend)})")
    print(f"    ⚠️ CONTRE tendance: {against_loss_rate:.1f}% loss ({len(against_losers)}/{len(against_trend)})")

    # 9. Par position Bollinger
    print("\n📊 9. PAR POSITION BOLLINGER BANDS")
    print("-" * 50)

    bb_ranges = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
    bb_labels = ['Sous BB inf', 'Près BB inf', 'Bas', 'Milieu bas', 'Milieu haut', 'Haut', 'Près BB sup', 'Au-dessus BB']

    for (low, high), label in zip(bb_ranges, bb_labels):
        range_trades = trades[(trades['bb_position'] >= low) & (trades['bb_position'] < high)]
        range_losers = losers[losers.index.isin(range_trades.index)]
        if len(range_trades) > 100:  # Minimum sample
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} {label:15}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # 10. Par momentum
    print("\n📊 10. PAR MOMENTUM (% sur 10 bougies)")
    print("-" * 50)

    mom_ranges = [(-100, -2), (-2, -1), (-1, -0.5), (-0.5, 0), (0, 0.5), (0.5, 1), (1, 2), (2, 100)]
    mom_labels = ['Fort baissier (<-2%)', 'Baissier (-2 à -1%)', 'Légèrement baissier',
                  'Neutre négatif', 'Neutre positif', 'Légèrement haussier',
                  'Haussier (1 à 2%)', 'Fort haussier (>2%)']

    for (low, high), label in zip(mom_ranges, mom_labels):
        range_trades = trades[(trades['momentum_pct'] >= low) & (trades['momentum_pct'] < high)]
        range_losers = losers[losers.index.isin(range_trades.index)]
        if len(range_trades) > 100:
            loss_rate = len(range_losers) / len(range_trades) * 100
            bar = "█" * int(loss_rate / 2)
            status = "⚠️" if loss_rate > 45 else "✅"
            print(f"  {status} {label:25}: {loss_rate:.1f}% loss ({len(range_losers)}/{len(range_trades)}) {bar}")

    # 11. Par divergence RSI
    print("\n📊 11. PAR DIVERGENCE RSI/PRIX")
    print("-" * 50)

    div_trades = trades[trades['divergence'] == True]
    no_div_trades = trades[trades['divergence'] == False]

    div_losers = losers[losers.index.isin(div_trades.index)]
    no_div_losers = losers[losers.index.isin(no_div_trades.index)]

    div_loss = len(div_losers) / len(div_trades) * 100 if len(div_trades) > 0 else 0
    no_div_loss = len(no_div_losers) / len(no_div_trades) * 100 if len(no_div_trades) > 0 else 0

    print(f"  Avec divergence:  {div_loss:.1f}% loss ({len(div_losers)}/{len(div_trades)})")
    print(f"  Sans divergence:  {no_div_loss:.1f}% loss ({len(no_div_losers)}/{len(no_div_trades)})")

    # 12. Par symbol
    print("\n📊 12. PAR PAIRE")
    print("-" * 50)

    for symbol in SYMBOLS:
        sym_trades = trades[trades['symbol'] == symbol]
        sym_losers = losers[losers['symbol'] == symbol]
        loss_rate = len(sym_losers) / len(sym_trades) * 100
        bar = "█" * int(loss_rate / 2)
        status = "⚠️" if loss_rate > 45 else "✅"
        print(f"  {status} {symbol:10}: {loss_rate:.1f}% loss ({len(sym_losers)}/{len(sym_trades)}) {bar}")

    # 13. Par mois
    print("\n📊 13. PAR MOIS")
    print("-" * 50)

    months = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    month_stats = []
    for month in range(1, 13):
        m_trades = trades[trades['month'] == month]
        m_losers = losers[losers['month'] == month]
        if len(m_trades) > 0:
            loss_rate = len(m_losers) / len(m_trades) * 100
            month_stats.append({'month': month, 'name': months[month-1],
                              'loss_rate': loss_rate, 'losses': len(m_losers), 'total': len(m_trades)})

    month_df = pd.DataFrame(month_stats).sort_values('loss_rate', ascending=False)
    for _, row in month_df.iterrows():
        bar = "█" * int(row['loss_rate'] / 2)
        status = "⚠️" if row['loss_rate'] > 45 else "✅"
        print(f"  {status} {row['name']:4}: {row['loss_rate']:.1f}% loss ({row['losses']}/{row['total']}) {bar}")

    # 14. Combos jour+heure toxiques
    print("\n📊 14. COMBOS JOUR+HEURE LES PLUS TOXIQUES")
    print("-" * 50)

    combo_stats = []
    for day in range(7):
        for hour in range(24):
            combo_trades = trades[(trades['day'] == day) & (trades['hour'] == hour)]
            combo_losers = losers[(losers['day'] == day) & (losers['hour'] == hour)]
            if len(combo_trades) >= 50:  # Minimum sample
                loss_rate = len(combo_losers) / len(combo_trades) * 100
                combo_stats.append({
                    'day': day,
                    'hour': hour,
                    'day_name': days[day],
                    'loss_rate': loss_rate,
                    'losses': len(combo_losers),
                    'total': len(combo_trades)
                })

    combo_df = pd.DataFrame(combo_stats).sort_values('loss_rate', ascending=False)

    print("\n🔴 TOP 20 COMBOS LES PLUS PERDANTS (>50% loss rate):")
    top_toxic = combo_df[combo_df['loss_rate'] > 50].head(20)
    for _, row in top_toxic.iterrows():
        print(f"  ⛔ {row['day_name']:10} {int(row['hour']):02d}:00 UTC → {row['loss_rate']:.1f}% loss ({row['losses']}/{row['total']})")

    print(f"\n  → {len(combo_df[combo_df['loss_rate'] > 50])} combos avec >50% loss rate")
    print(f"  → {len(combo_df[combo_df['loss_rate'] > 48])} combos avec >48% loss rate")

    # 15. Analyse des séquences de pertes
    print("\n📊 15. SEQUENCES DE PERTES CONSECUTIVES")
    print("-" * 50)

    # Calculer les séquences
    trades_sorted = trades.sort_values('timestamp')
    trades_sorted['loss'] = ~trades_sorted['win']

    sequences = []
    current_seq = 0
    for _, row in trades_sorted.iterrows():
        if row['loss']:
            current_seq += 1
        else:
            if current_seq > 0:
                sequences.append(current_seq)
            current_seq = 0

    if sequences:
        print(f"  Séquence max de pertes: {max(sequences)} trades consécutifs")
        print(f"  Séquence moyenne: {np.mean(sequences):.1f} trades")
        print(f"  Séquences de 5+ pertes: {len([s for s in sequences if s >= 5])}")
        print(f"  Séquences de 10+ pertes: {len([s for s in sequences if s >= 10])}")

    # 16. Corrélation entre indicateurs
    print("\n📊 16. CORRELATION INDICATEURS/PERTES")
    print("-" * 50)

    # RSI extrême
    extreme_rsi_up = up_trades[up_trades['rsi'] < 20]
    extreme_rsi_up_losers = up_losers[up_losers['rsi'] < 20]
    if len(extreme_rsi_up) > 0:
        loss_rate = len(extreme_rsi_up_losers) / len(extreme_rsi_up) * 100
        print(f"  RSI très bas (<20) pour UP: {loss_rate:.1f}% loss ({len(extreme_rsi_up_losers)}/{len(extreme_rsi_up)})")

    extreme_rsi_down = down_trades[down_trades['rsi'] > 80]
    extreme_rsi_down_losers = down_losers[down_losers['rsi'] > 80]
    if len(extreme_rsi_down) > 0:
        loss_rate = len(extreme_rsi_down_losers) / len(extreme_rsi_down) * 100
        print(f"  RSI très haut (>80) pour DOWN: {loss_rate:.1f}% loss ({len(extreme_rsi_down_losers)}/{len(extreme_rsi_down)})")

    # Double confirmation forte
    strong_up = up_trades[(up_trades['rsi'] < 25) & (up_trades['stoch'] < 15)]
    strong_up_losers = up_losers[(up_losers['rsi'] < 25) & (up_losers['stoch'] < 15)]
    if len(strong_up) > 0:
        loss_rate = len(strong_up_losers) / len(strong_up) * 100
        print(f"  Signal UP fort (RSI<25 & Stoch<15): {loss_rate:.1f}% loss ({len(strong_up_losers)}/{len(strong_up)})")

    strong_down = down_trades[(down_trades['rsi'] > 75) & (down_trades['stoch'] > 90)]
    strong_down_losers = down_losers[(down_losers['rsi'] > 75) & (down_losers['stoch'] > 90)]
    if len(strong_down) > 0:
        loss_rate = len(strong_down_losers) / len(strong_down) * 100
        print(f"  Signal DOWN fort (RSI>75 & Stoch>90): {loss_rate:.1f}% loss ({len(strong_down_losers)}/{len(strong_down)})")

    # ===== RESUME DES POINTS COMMUNS =====
    print("\n" + "=" * 70)
    print("RESUME: POINTS COMMUNS DES TRADES PERDANTS")
    print("=" * 70)

    findings = []

    # Collecter les patterns significatifs
    worst_hours = hour_df.head(3)['hour'].tolist()
    worst_days = day_df.head(2)['name'].tolist()

    print(f"""
📌 POINTS COMMUNS IDENTIFIES:

1. HEURES TOXIQUES: {', '.join([f'{int(h):02d}:00' for h in worst_hours])} UTC
   → Ces heures ont les taux de perte les plus élevés

2. JOURS DIFFICILES: {', '.join(worst_days)}
   → Jours avec plus de pertes que la moyenne

3. SIGNAL CONTRE TENDANCE:
   → Trader contre la tendance (SMA20 vs SMA50) augmente les pertes
   → {against_loss_rate:.1f}% vs {with_loss_rate:.1f}% avec tendance

4. VOLATILITE:
   → Analyser si haute ou basse volatilité est plus risquée

5. RSI EXTREMES:
   → Les RSI très extrêmes ne garantissent pas le succès

6. COMBOS TOXIQUES:
   → {len(combo_df[combo_df['loss_rate'] > 50])} combos jour+heure avec >50% loss rate
""")

    # Sauvegarder les données pour analyse ultérieure
    trades.to_csv('data/all_trades_analysis.csv', index=False)
    losers.to_csv('data/losing_trades_analysis.csv', index=False)
    print("\n💾 Données sauvegardées dans data/all_trades_analysis.csv et data/losing_trades_analysis.csv")

    return trades, losers


if __name__ == "__main__":
    trades, losers = run_analysis()
