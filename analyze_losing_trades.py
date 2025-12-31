#!/usr/bin/env python3
"""
Analyse approfondie des trades perdants V7
- Mois < $10k
- Patterns communs des pertes
- Price Action, FTFC, Volume, Heures
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

def fetch_ohlcv(symbol, timeframe='15m', days=730):
    """Fetch historical data from Binance"""
    exchange = ccxt.binance()
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())

    all_data = []
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        all_data.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        if len(ohlcv) < 1000:
            break

    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def fetch_multi_timeframe(symbol, days=730):
    """Fetch 15m, 1h, 4h data"""
    print(f"  Fetching 15m...")
    df_15m = fetch_ohlcv(symbol, '15m', days)
    print(f"  Fetching 1h...")
    df_1h = fetch_ohlcv(symbol, '1h', days)
    print(f"  Fetching 4h...")
    df_4h = fetch_ohlcv(symbol, '4h', days)
    return df_15m, df_1h, df_4h

def calculate_rsi(prices, period=7):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_stochastic(df, period=5):
    """Calculate Stochastic %K"""
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)

def analyze_candle(row):
    """Analyze candle characteristics"""
    body = abs(row['close'] - row['open'])
    total_range = row['high'] - row['low']

    if total_range == 0:
        return {'type': 'doji', 'body_pct': 0, 'upper_wick_pct': 0, 'lower_wick_pct': 0}

    body_pct = body / total_range * 100

    if row['close'] >= row['open']:  # Bullish
        upper_wick = row['high'] - row['close']
        lower_wick = row['open'] - row['low']
    else:  # Bearish
        upper_wick = row['high'] - row['open']
        lower_wick = row['close'] - row['low']

    upper_wick_pct = upper_wick / total_range * 100
    lower_wick_pct = lower_wick / total_range * 100

    # Candle type
    if body_pct < 10:
        candle_type = 'doji'
    elif upper_wick_pct > 60:
        candle_type = 'shooting_star' if row['close'] < row['open'] else 'inverted_hammer'
    elif lower_wick_pct > 60:
        candle_type = 'hammer' if row['close'] > row['open'] else 'hanging_man'
    elif body_pct > 70:
        candle_type = 'marubozu_bull' if row['close'] > row['open'] else 'marubozu_bear'
    else:
        candle_type = 'bullish' if row['close'] > row['open'] else 'bearish'

    return {
        'type': candle_type,
        'body_pct': body_pct,
        'upper_wick_pct': upper_wick_pct,
        'lower_wick_pct': lower_wick_pct,
        'is_bullish': row['close'] > row['open']
    }

def get_htf_bias(df_1h, df_4h, timestamp):
    """Get higher timeframe bias at given timestamp"""
    ts = pd.Timestamp(timestamp)

    # 1H bias (last 3 candles trend)
    h1_data = df_1h[df_1h.index <= ts].tail(3)
    if len(h1_data) >= 3:
        h1_trend = (h1_data['close'].iloc[-1] - h1_data['close'].iloc[0]) / h1_data['close'].iloc[0] * 100
        h1_rsi = calculate_rsi(df_1h['close'], 14).loc[df_1h.index <= ts].iloc[-1] if len(df_1h[df_1h.index <= ts]) > 14 else 50
    else:
        h1_trend = 0
        h1_rsi = 50

    # 4H bias (last 3 candles trend)
    h4_data = df_4h[df_4h.index <= ts].tail(3)
    if len(h4_data) >= 3:
        h4_trend = (h4_data['close'].iloc[-1] - h4_data['close'].iloc[0]) / h4_data['close'].iloc[0] * 100
        h4_rsi = calculate_rsi(df_4h['close'], 14).loc[df_4h.index <= ts].iloc[-1] if len(df_4h[df_4h.index <= ts]) > 14 else 50
    else:
        h4_trend = 0
        h4_rsi = 50

    # FTFC Score
    ftfc_score = 0
    if h1_trend > 0.1: ftfc_score += 1
    elif h1_trend < -0.1: ftfc_score -= 1
    if h4_trend > 0.2: ftfc_score += 1
    elif h4_trend < -0.2: ftfc_score -= 1
    if h1_rsi > 55: ftfc_score += 0.5
    elif h1_rsi < 45: ftfc_score -= 0.5
    if h4_rsi > 55: ftfc_score += 0.5
    elif h4_rsi < 45: ftfc_score -= 0.5

    return {
        'h1_trend': h1_trend,
        'h4_trend': h4_trend,
        'h1_rsi': h1_rsi,
        'h4_rsi': h4_rsi,
        'ftfc_score': ftfc_score,
        'ftfc_bias': 'BULLISH' if ftfc_score > 1 else ('BEARISH' if ftfc_score < -1 else 'NEUTRAL')
    }

def simulate_v7_detailed(df_15m, df_1h, df_4h, bet_size=100, entry_price=0.525):
    """Simulate V7 with detailed trade analysis"""
    df = df_15m.copy()
    df['rsi'] = calculate_rsi(df['close'], 7)
    df['stoch'] = calculate_stochastic(df, 5)
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']

    trades = []
    total = len(df) - 1
    
    for i in range(total):
        if i % 10000 == 0:
            print(f"    Progress: {i}/{total} ({i/total*100:.0f}%)")
            
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue

        signal = None
        if row['rsi'] < 38 and row['stoch'] < 30:
            signal = 'UP'
        elif row['rsi'] > 68 and row['stoch'] > 75:
            signal = 'DOWN'

        if signal:
            price_went_up = next_row['close'] > row['close']
            win = (signal == 'UP' and price_went_up) or (signal == 'DOWN' and not price_went_up)
            shares = bet_size / entry_price
            pnl = shares * (1 - entry_price) if win else -bet_size

            candle = analyze_candle(row)
            htf = get_htf_bias(df_1h, df_4h, row.name)

            prev_high = df['high'].iloc[max(0, i-3):i].max() if i > 0 else row['high']
            prev_low = df['low'].iloc[max(0, i-3):i].min() if i > 0 else row['low']

            trades.append({
                'timestamp': row.name,
                'hour': row.name.hour,
                'day_of_week': row.name.dayofweek,
                'signal': signal,
                'win': win,
                'pnl': pnl,
                'rsi': row['rsi'],
                'stoch': row['stoch'],
                'volume_ratio': row['volume_ratio'] if not pd.isna(row['volume_ratio']) else 1,
                'candle_type': candle['type'],
                'body_pct': candle['body_pct'],
                'ftfc_score': htf['ftfc_score'],
                'ftfc_bias': htf['ftfc_bias'],
                'broke_high': row['close'] > prev_high,
                'broke_low': row['close'] < prev_low
            })

    return pd.DataFrame(trades)

def main():
    print("=" * 80)
    print("ANALYSE DES TRADES PERDANTS - V7")
    print("Objectif: Comprendre pourquoi certains mois < $10k")
    print("=" * 80)

    pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    all_trades = []

    for pair in pairs:
        print(f"\n{'='*60}")
        print(f"Fetching {pair} (multi-timeframe)...")
        df_15m, df_1h, df_4h = fetch_multi_timeframe(pair, 730)
        print(f"  15m: {len(df_15m)} | 1h: {len(df_1h)} | 4h: {len(df_4h)}")

        print(f"  Analyzing trades...")
        trades = simulate_v7_detailed(df_15m, df_1h, df_4h)
        trades['pair'] = pair.split('/')[0]
        all_trades.append(trades)
        print(f"  {len(trades)} trades analyzed")

    all_df = pd.concat(all_trades, ignore_index=True)
    all_df['month'] = all_df['timestamp'].dt.to_period('M')

    # Identify bad months
    monthly_pnl = all_df.groupby('month')['pnl'].sum()
    bad_months = monthly_pnl[monthly_pnl < 10000].index.tolist()

    print("\n" + "=" * 80)
    print(f"MOIS PROBLEMATIQUES (PnL < $10,000): {len(bad_months)} mois")
    print("=" * 80)
    for month in bad_months:
        pnl = monthly_pnl[month]
        month_trades = all_df[all_df['month'] == month]
        wr = month_trades['win'].mean() * 100
        print(f"  {month}: ${pnl:,.0f} (WR: {wr:.1f}%)")

    bad_month_trades = all_df[all_df['month'].isin(bad_months)]
    losing_trades = bad_month_trades[bad_month_trades['win'] == False]

    print("\n" + "=" * 80)
    print("ANALYSE PAR HEURE (UTC)")
    print("=" * 80)
    hour_analysis = losing_trades.groupby('hour').agg({'pnl': ['count', 'sum']})
    hour_analysis.columns = ['count', 'total_loss']
    hour_analysis = hour_analysis.sort_values('total_loss')
    
    print(f"\n{'Heure':<8} {'Pertes':>8} {'Loss Total':>15}")
    print("-" * 35)
    worst_hours = []
    for hour, row in hour_analysis.head(10).iterrows():
        print(f"{hour:02d}:00    {int(row['count']):>8} ${row['total_loss']:>14,.0f}")
        worst_hours.append(hour)

    print("\n" + "=" * 80)
    print("ANALYSE PAR JOUR")
    print("=" * 80)
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    day_analysis = losing_trades.groupby('day_of_week').agg({'pnl': ['count', 'sum']})
    day_analysis.columns = ['count', 'total_loss']
    print(f"\n{'Jour':<12} {'Pertes':>8} {'Loss Total':>15}")
    print("-" * 40)
    for day_num, row in day_analysis.sort_values('total_loss').iterrows():
        print(f"{days[day_num]:<12} {int(row['count']):>8} ${row['total_loss']:>14,.0f}")

    print("\n" + "=" * 80)
    print("ANALYSE FTFC (Multi-Timeframe)")
    print("=" * 80)
    
    up_against = losing_trades[(losing_trades['signal'] == 'UP') & (losing_trades['ftfc_bias'] == 'BEARISH')]
    down_against = losing_trades[(losing_trades['signal'] == 'DOWN') & (losing_trades['ftfc_bias'] == 'BULLISH')]
    print(f"\nUP contre tendance HTF: {len(up_against)} pertes (${up_against['pnl'].sum():,.0f})")
    print(f"DOWN contre tendance HTF: {len(down_against)} pertes (${down_against['pnl'].sum():,.0f})")

    # Win rate comparison
    aligned = all_df[
        ((all_df['signal'] == 'UP') & (all_df['ftfc_bias'] == 'BULLISH')) |
        ((all_df['signal'] == 'DOWN') & (all_df['ftfc_bias'] == 'BEARISH'))
    ]
    against = all_df[
        ((all_df['signal'] == 'UP') & (all_df['ftfc_bias'] == 'BEARISH')) |
        ((all_df['signal'] == 'DOWN') & (all_df['ftfc_bias'] == 'BULLISH'))
    ]
    neutral = all_df[all_df['ftfc_bias'] == 'NEUTRAL']
    
    print(f"\n--- Win Rate par Alignement FTFC (tous trades) ---")
    print(f"Aligne (signal = HTF): WR {aligned['win'].mean()*100:.1f}% ({len(aligned)} trades)")
    print(f"Neutre: WR {neutral['win'].mean()*100:.1f}% ({len(neutral)} trades)")
    print(f"Contre: WR {against['win'].mean()*100:.1f}% ({len(against)} trades)")

    print("\n" + "=" * 80)
    print("ANALYSE VOLUME")
    print("=" * 80)
    low_vol = all_df[all_df['volume_ratio'] < 0.5]
    normal_vol = all_df[(all_df['volume_ratio'] >= 0.5) & (all_df['volume_ratio'] <= 1.5)]
    high_vol = all_df[all_df['volume_ratio'] > 1.5]
    print(f"\nVolume < 50%: WR {low_vol['win'].mean()*100:.1f}% ({len(low_vol)} trades)")
    print(f"Volume 50-150%: WR {normal_vol['win'].mean()*100:.1f}% ({len(normal_vol)} trades)")
    print(f"Volume > 150%: WR {high_vol['win'].mean()*100:.1f}% ({len(high_vol)} trades)")

    print("\n" + "=" * 80)
    print("ANALYSE PRICE ACTION")
    print("=" * 80)
    candle_wr = all_df.groupby('candle_type').agg({'win': 'mean', 'pnl': ['count', 'sum']})
    candle_wr.columns = ['wr', 'count', 'pnl']
    candle_wr = candle_wr.sort_values('pnl', ascending=False)
    print(f"\n{'Type':<20} {'WR':>8} {'Trades':>10} {'PnL':>15}")
    print("-" * 58)
    for ct, row in candle_wr.iterrows():
        print(f"{ct:<20} {row['wr']*100:>7.1f}% {int(row['count']):>10} ${row['pnl']:>14,.0f}")

    print("\n" + "=" * 80)
    print("SIMULATION AVEC FILTRES")
    print("=" * 80)

    # Original
    orig_pnl = all_df['pnl'].sum()
    orig_wr = all_df['win'].mean() * 100
    orig_monthly = all_df.groupby('month')['pnl'].sum()
    orig_bad = len(orig_monthly[orig_monthly < 10000])
    
    print(f"\nORIGINAL V7:")
    print(f"  Trades: {len(all_df):,} | WR: {orig_wr:.1f}% | PnL: ${orig_pnl:,.0f}")
    print(f"  Mois < $10k: {orig_bad}")

    # Filter 1: FTFC only (no contre-tendance)
    f1 = all_df[
        ((all_df['signal'] == 'UP') & (all_df['ftfc_bias'] != 'BEARISH')) |
        ((all_df['signal'] == 'DOWN') & (all_df['ftfc_bias'] != 'BULLISH'))
    ]
    f1_monthly = f1.groupby('month')['pnl'].sum()
    f1_bad = len(f1_monthly[f1_monthly < 10000])
    print(f"\nFILTRE 1 - FTFC (eviter contre-tendance):")
    print(f"  Trades: {len(f1):,} | WR: {f1['win'].mean()*100:.1f}% | PnL: ${f1['pnl'].sum():,.0f}")
    print(f"  Mois < $10k: {f1_bad}")

    # Filter 2: Volume >= 0.7
    f2 = all_df[all_df['volume_ratio'] >= 0.7]
    f2_monthly = f2.groupby('month')['pnl'].sum()
    f2_bad = len(f2_monthly[f2_monthly < 10000])
    print(f"\nFILTRE 2 - Volume >= 70%:")
    print(f"  Trades: {len(f2):,} | WR: {f2['win'].mean()*100:.1f}% | PnL: ${f2['pnl'].sum():,.0f}")
    print(f"  Mois < $10k: {f2_bad}")

    # Filter 3: Avoid worst hours
    f3 = all_df[~all_df['hour'].isin(worst_hours[:5])]
    f3_monthly = f3.groupby('month')['pnl'].sum()
    f3_bad = len(f3_monthly[f3_monthly < 10000])
    print(f"\nFILTRE 3 - Eviter heures {sorted(worst_hours[:5])}:")
    print(f"  Trades: {len(f3):,} | WR: {f3['win'].mean()*100:.1f}% | PnL: ${f3['pnl'].sum():,.0f}")
    print(f"  Mois < $10k: {f3_bad}")

    # Combined: FTFC + Volume
    f_combo = all_df[
        (
            ((all_df['signal'] == 'UP') & (all_df['ftfc_bias'] != 'BEARISH')) |
            ((all_df['signal'] == 'DOWN') & (all_df['ftfc_bias'] != 'BULLISH'))
        ) &
        (all_df['volume_ratio'] >= 0.7)
    ]
    f_combo_monthly = f_combo.groupby('month')['pnl'].sum()
    f_combo_bad = len(f_combo_monthly[f_combo_monthly < 10000])
    
    print(f"\n{'='*60}")
    print(f"COMBINAISON FTFC + VOLUME:")
    print(f"{'='*60}")
    print(f"  Trades: {len(f_combo):,} ({len(f_combo)/len(all_df)*100:.0f}%)")
    print(f"  Win Rate: {f_combo['win'].mean()*100:.1f}%")
    print(f"  PnL Total: ${f_combo['pnl'].sum():,.0f}")
    print(f"  PnL/Mois: ${f_combo['pnl'].sum()/24:,.0f}")
    print(f"  Mois < $10k: {f_combo_bad}")

    # Show monthly comparison
    print(f"\n--- Detail Mensuel ---")
    print(f"{'Mois':<12} {'Original':>12} {'Filtre':>12} {'Status':>10}")
    print("-" * 50)
    for month in orig_monthly.index:
        orig = orig_monthly[month]
        filt = f_combo_monthly.get(month, 0)
        status = "OK" if filt >= 10000 else "< 10k"
        print(f"{str(month):<12} ${orig:>10,.0f} ${filt:>10,.0f} {status:>10}")

if __name__ == "__main__":
    main()
