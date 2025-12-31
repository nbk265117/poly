#!/usr/bin/env python3
"""
Simulation V8 Strategy - BTC + ETH + XRP
V8 = V7 + FTFC Filter (eviter contre-tendance HTF)
$100/trade, Entry 52.5c
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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

def calculate_rsi(prices, period=7):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_stochastic(df, period=5):
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    return 100 * (df['close'] - low_min) / (high_max - low_min)

def get_ftfc_bias(df_1h, df_4h, timestamp):
    """Calculate FTFC bias from 1H and 4H timeframes"""
    ts = pd.Timestamp(timestamp)
    
    # 1H analysis
    h1_data = df_1h[df_1h.index <= ts].tail(5)
    if len(h1_data) >= 3:
        h1_trend = (h1_data['close'].iloc[-1] - h1_data['close'].iloc[0]) / h1_data['close'].iloc[0] * 100
        h1_rsi_series = calculate_rsi(df_1h['close'], 14)
        h1_rsi = h1_rsi_series.loc[df_1h.index <= ts].iloc[-1] if len(df_1h[df_1h.index <= ts]) > 14 else 50
    else:
        h1_trend, h1_rsi = 0, 50
    
    # 4H analysis
    h4_data = df_4h[df_4h.index <= ts].tail(5)
    if len(h4_data) >= 3:
        h4_trend = (h4_data['close'].iloc[-1] - h4_data['close'].iloc[0]) / h4_data['close'].iloc[0] * 100
        h4_rsi_series = calculate_rsi(df_4h['close'], 14)
        h4_rsi = h4_rsi_series.loc[df_4h.index <= ts].iloc[-1] if len(df_4h[df_4h.index <= ts]) > 14 else 50
    else:
        h4_trend, h4_rsi = 0, 50
    
    # FTFC Score calculation
    ftfc_score = 0
    if h1_trend > 0.1: ftfc_score += 1
    elif h1_trend < -0.1: ftfc_score -= 1
    if h4_trend > 0.2: ftfc_score += 1
    elif h4_trend < -0.2: ftfc_score -= 1
    if h1_rsi > 55: ftfc_score += 0.5
    elif h1_rsi < 45: ftfc_score -= 0.5
    if h4_rsi > 55: ftfc_score += 0.5
    elif h4_rsi < 45: ftfc_score -= 0.5
    
    if ftfc_score > 1:
        return 'BULLISH'
    elif ftfc_score < -1:
        return 'BEARISH'
    return 'NEUTRAL'

def simulate_v8(df_15m, df_1h, df_4h, bet_size=100, entry_price=0.525):
    """
    V8 Strategy: V7 + FTFC Filter
    - UP: RSI(7) < 38 AND Stoch(5) < 30 AND FTFC != BEARISH
    - DOWN: RSI(7) > 68 AND Stoch(5) > 75 AND FTFC != BULLISH
    """
    df = df_15m.copy()
    df['rsi'] = calculate_rsi(df['close'], 7)
    df['stoch'] = calculate_stochastic(df, 5)
    
    trades = []
    total = len(df) - 1
    
    for i in range(total):
        if i % 10000 == 0:
            print(f"    Progress: {i}/{total} ({i/total*100:.0f}%)")
        
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        
        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue
        
        # Get FTFC bias
        ftfc_bias = get_ftfc_bias(df_1h, df_4h, row.name)
        
        signal = None
        
        # V8 signals with FTFC filter
        if row['rsi'] < 38 and row['stoch'] < 30:
            if ftfc_bias != 'BEARISH':  # Don't go UP against bearish HTF
                signal = 'UP'
        elif row['rsi'] > 68 and row['stoch'] > 75:
            if ftfc_bias != 'BULLISH':  # Don't go DOWN against bullish HTF
                signal = 'DOWN'
        
        if signal:
            price_went_up = next_row['close'] > row['close']
            win = (signal == 'UP' and price_went_up) or (signal == 'DOWN' and not price_went_up)
            
            shares = bet_size / entry_price
            pnl = shares * (1 - entry_price) if win else -bet_size
            
            trades.append({
                'timestamp': row.name,
                'signal': signal,
                'ftfc_bias': ftfc_bias,
                'win': win,
                'pnl': pnl
            })
    
    return pd.DataFrame(trades)

def main():
    print("=" * 70)
    print("SIMULATION V8 - BTC + ETH + XRP")
    print("V8 = V7 + FTFC Filter (eviter contre-tendance HTF)")
    print("$100/trade | Entry: 52.5c | RSI(7) 38/68 | Stoch(5) 30/75")
    print("=" * 70)
    
    pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    all_trades = []
    
    for pair in pairs:
        print(f"\n{'='*60}")
        print(f"Fetching {pair}...")
        
        # Fetch multi-timeframe data
        print("  Loading 15m...")
        df_15m = fetch_ohlcv(pair, '15m', 730)
        print("  Loading 1h...")
        df_1h = fetch_ohlcv(pair, '1h', 730)
        print("  Loading 4h...")
        df_4h = fetch_ohlcv(pair, '4h', 730)
        
        print(f"  15m: {len(df_15m)} | 1h: {len(df_1h)} | 4h: {len(df_4h)}")
        
        print("  Simulating V8...")
        trades = simulate_v8(df_15m, df_1h, df_4h)
        trades['pair'] = pair.split('/')[0]
        all_trades.append(trades)
        
        wins = trades['win'].sum()
        total = len(trades)
        wr = wins / total * 100 if total > 0 else 0
        print(f"  {total} trades | WR: {wr:.1f}% | PnL: ${trades['pnl'].sum():,.0f}")
    
    # Combine all trades
    all_df = pd.concat(all_trades, ignore_index=True)
    all_df['month'] = all_df['timestamp'].dt.to_period('M')
    
    # Monthly breakdown
    print("\n" + "=" * 70)
    print("DETAIL MENSUEL 2024-2025 (V8 FTFC)")
    print("=" * 70)
    
    monthly = all_df.groupby('month').agg({
        'pnl': 'sum',
        'win': ['sum', 'count']
    })
    monthly.columns = ['pnl', 'wins', 'total']
    monthly['wr'] = monthly['wins'] / monthly['total'] * 100
    
    print(f"\n{'Mois':<12} {'Trades':>8} {'Win Rate':>10} {'PnL':>15} {'Status':>10}")
    print("-" * 60)
    
    year_2024 = {'trades': 0, 'wins': 0, 'pnl': 0}
    year_2025 = {'trades': 0, 'wins': 0, 'pnl': 0}
    months_under_10k = 0
    
    for period, row in monthly.iterrows():
        year = period.year
        month_name = period.strftime('%b %Y')
        status = "OK" if row['pnl'] >= 10000 else "< 10k"
        if row['pnl'] < 10000:
            months_under_10k += 1
        
        print(f"{month_name:<12} {int(row['total']):>8} {row['wr']:>9.1f}% ${row['pnl']:>13,.0f} {status:>10}")
        
        if year == 2024:
            year_2024['trades'] += row['total']
            year_2024['wins'] += row['wins']
            year_2024['pnl'] += row['pnl']
        elif year == 2025:
            year_2025['trades'] += row['total']
            year_2025['wins'] += row['wins']
            year_2025['pnl'] += row['pnl']
    
    # Yearly summary
    print("\n" + "=" * 70)
    print("RESUME ANNUEL")
    print("=" * 70)
    
    if year_2024['trades'] > 0:
        wr_2024 = year_2024['wins'] / year_2024['trades'] * 100
        trades_day_2024 = year_2024['trades'] / 366
        print(f"\n2024:")
        print(f"  Trades: {int(year_2024['trades']):,}")
        print(f"  Trades/jour: {trades_day_2024:.0f}")
        print(f"  Win Rate: {wr_2024:.1f}%")
        print(f"  PnL Total: ${year_2024['pnl']:,.0f}")
        print(f"  PnL Moyen/Mois: ${year_2024['pnl']/12:,.0f}")
    
    if year_2025['trades'] > 0:
        months_2025 = len([p for p in monthly.index if p.year == 2025])
        wr_2025 = year_2025['wins'] / year_2025['trades'] * 100
        trades_day_2025 = year_2025['trades'] / (months_2025 * 30)
        print(f"\n2025:")
        print(f"  Trades: {int(year_2025['trades']):,}")
        print(f"  Trades/jour: {trades_day_2025:.0f}")
        print(f"  Win Rate: {wr_2025:.1f}%")
        print(f"  PnL Total: ${year_2025['pnl']:,.0f}")
        print(f"  PnL Moyen/Mois: ${year_2025['pnl']/months_2025:,.0f}")
    
    # Grand total
    total_trades = len(all_df)
    total_wins = all_df['win'].sum()
    total_pnl = all_df['pnl'].sum()
    total_wr = total_wins / total_trades * 100
    total_months = len(monthly)
    
    print("\n" + "=" * 70)
    print("TOTAL V8 (BTC + ETH + XRP)")
    print("=" * 70)
    print(f"  Trades: {int(total_trades):,}")
    print(f"  Trades/jour: {total_trades / 730:.0f}")
    print(f"  Win Rate: {total_wr:.1f}%")
    print(f"  PnL Total: ${total_pnl:,.0f}")
    print(f"  PnL Moyen/Mois: ${total_pnl/total_months:,.0f}")
    print(f"  Mois < $10k: {months_under_10k}/{total_months}")
    
    # Per pair breakdown
    print("\n" + "=" * 70)
    print("PERFORMANCE PAR PAIR")
    print("=" * 70)
    
    pair_stats = []
    for pair in ['BTC', 'ETH', 'XRP']:
        pair_df = all_df[all_df['pair'] == pair]
        wins = pair_df['win'].sum()
        total = len(pair_df)
        wr = wins / total * 100 if total > 0 else 0
        pnl = pair_df['pnl'].sum()
        pair_stats.append({'pair': pair, 'trades': total, 'wr': wr, 'pnl': pnl})
        print(f"\n{pair}:")
        print(f"  Trades: {total:,}")
        print(f"  Win Rate: {wr:.1f}%")
        print(f"  PnL Total: ${pnl:,.0f}")
        print(f"  PnL/Mois: ${pnl/total_months:,.0f}")
    
    # Ranking
    print("\n" + "=" * 70)
    print("CLASSEMENT")
    print("=" * 70)
    pair_stats_sorted = sorted(pair_stats, key=lambda x: x['pnl'], reverse=True)
    for i, p in enumerate(pair_stats_sorted):
        medal = ['🥇', '🥈', '🥉'][i]
        print(f"{medal} {p['pair']}: WR {p['wr']:.1f}% | PnL ${p['pnl']:,.0f}")
    
    # Comparison with V7
    print("\n" + "=" * 70)
    print("COMPARAISON V7 vs V8")
    print("=" * 70)
    print(f"\n{'Metrique':<20} {'V7':>15} {'V8 (FTFC)':>15} {'Diff':>12}")
    print("-" * 65)
    print(f"{'Trades':<20} {'63,630':>15} {total_trades:>15,}")
    print(f"{'Win Rate':<20} {'55.5%':>15} {total_wr:>14.1f}%")
    print(f"{'PnL Total':<20} {'$362,524':>15} ${total_pnl:>14,.0f}")
    print(f"{'PnL/Mois':<20} {'$15,105':>15} ${total_pnl/total_months:>14,.0f}")
    print(f"{'Mois < $10k':<20} {'5':>15} {months_under_10k:>15}")

if __name__ == "__main__":
    main()
