#!/usr/bin/env python3
"""
Analyse approfondie de Juin 2025 - Pourquoi faible en V8?
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fetch_ohlcv(symbol, timeframe='15m', days=730):
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
    ts = pd.Timestamp(timestamp)
    h1_data = df_1h[df_1h.index <= ts].tail(5)
    h4_data = df_4h[df_4h.index <= ts].tail(5)
    
    h1_trend = (h1_data['close'].iloc[-1] - h1_data['close'].iloc[0]) / h1_data['close'].iloc[0] * 100 if len(h1_data) >= 3 else 0
    h4_trend = (h4_data['close'].iloc[-1] - h4_data['close'].iloc[0]) / h4_data['close'].iloc[0] * 100 if len(h4_data) >= 3 else 0
    
    h1_rsi = calculate_rsi(df_1h['close'], 14).loc[df_1h.index <= ts].iloc[-1] if len(df_1h[df_1h.index <= ts]) > 14 else 50
    h4_rsi = calculate_rsi(df_4h['close'], 14).loc[df_4h.index <= ts].iloc[-1] if len(df_4h[df_4h.index <= ts]) > 14 else 50
    
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
        'bias': 'BULLISH' if ftfc_score > 1 else ('BEARISH' if ftfc_score < -1 else 'NEUTRAL'),
        'score': ftfc_score,
        'h1_trend': h1_trend,
        'h4_trend': h4_trend
    }

def analyze_june_2025(pair):
    print(f"\n{'='*60}")
    print(f"Analyzing {pair} - June 2025")
    print(f"{'='*60}")
    
    df_15m = fetch_ohlcv(pair, '15m', 730)
    df_1h = fetch_ohlcv(pair, '1h', 730)
    df_4h = fetch_ohlcv(pair, '4h', 730)
    
    # Filter June 2025
    june_15m = df_15m[(df_15m.index >= '2025-06-01') & (df_15m.index < '2025-07-01')]
    
    df = june_15m.copy()
    df['rsi'] = calculate_rsi(df['close'], 7)
    df['stoch'] = calculate_stochastic(df, 5)
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Calculate price movement for June
    june_start = june_15m['close'].iloc[0]
    june_end = june_15m['close'].iloc[-1]
    june_high = june_15m['high'].max()
    june_low = june_15m['low'].min()
    june_change = (june_end - june_start) / june_start * 100
    june_volatility = (june_high - june_low) / june_start * 100
    
    print(f"\nPrix {pair.split('/')[0]} en Juin 2025:")
    print(f"  Debut: ${june_start:,.2f}")
    print(f"  Fin: ${june_end:,.2f}")
    print(f"  High: ${june_high:,.2f}")
    print(f"  Low: ${june_low:,.2f}")
    print(f"  Changement: {june_change:+.1f}%")
    print(f"  Volatilite: {june_volatility:.1f}%")
    
    trades = []
    for i in range(len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        
        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue
        
        ftfc = get_ftfc_bias(df_1h, df_4h, row.name)
        
        # V8 signals
        signal = None
        if row['rsi'] < 38 and row['stoch'] < 30 and ftfc['bias'] != 'BEARISH':
            signal = 'UP'
        elif row['rsi'] > 68 and row['stoch'] > 75 and ftfc['bias'] != 'BULLISH':
            signal = 'DOWN'
        
        if signal:
            price_went_up = next_row['close'] > row['close']
            win = (signal == 'UP' and price_went_up) or (signal == 'DOWN' and not price_went_up)
            pnl = 90.48 if win else -100
            
            trades.append({
                'timestamp': row.name,
                'day': row.name.day,
                'hour': row.name.hour,
                'signal': signal,
                'ftfc_bias': ftfc['bias'],
                'ftfc_score': ftfc['score'],
                'h1_trend': ftfc['h1_trend'],
                'h4_trend': ftfc['h4_trend'],
                'rsi': row['rsi'],
                'stoch': row['stoch'],
                'volume_ratio': row['volume_ratio'],
                'win': win,
                'pnl': pnl
            })
    
    trades_df = pd.DataFrame(trades)
    
    if len(trades_df) == 0:
        print("No trades in June 2025")
        return None
    
    total_trades = len(trades_df)
    wins = trades_df['win'].sum()
    wr = wins / total_trades * 100
    total_pnl = trades_df['pnl'].sum()
    
    print(f"\nResume Juin 2025:")
    print(f"  Trades: {total_trades}")
    print(f"  Win Rate: {wr:.1f}%")
    print(f"  PnL: ${total_pnl:,.0f}")
    
    # Analyze by signal type
    print(f"\nPar Signal:")
    for sig in ['UP', 'DOWN']:
        sig_df = trades_df[trades_df['signal'] == sig]
        if len(sig_df) > 0:
            sig_wr = sig_df['win'].mean() * 100
            sig_pnl = sig_df['pnl'].sum()
            print(f"  {sig}: {len(sig_df)} trades | WR: {sig_wr:.1f}% | PnL: ${sig_pnl:,.0f}")
    
    # Analyze by FTFC bias
    print(f"\nPar FTFC Bias:")
    for bias in ['BULLISH', 'NEUTRAL', 'BEARISH']:
        bias_df = trades_df[trades_df['ftfc_bias'] == bias]
        if len(bias_df) > 0:
            bias_wr = bias_df['win'].mean() * 100
            bias_pnl = bias_df['pnl'].sum()
            print(f"  {bias}: {len(bias_df)} trades | WR: {bias_wr:.1f}% | PnL: ${bias_pnl:,.0f}")
    
    # Analyze by week
    print(f"\nPar Semaine:")
    trades_df['week'] = trades_df['timestamp'].dt.isocalendar().week
    for week in sorted(trades_df['week'].unique()):
        week_df = trades_df[trades_df['week'] == week]
        week_wr = week_df['win'].mean() * 100
        week_pnl = week_df['pnl'].sum()
        print(f"  Semaine {week}: {len(week_df)} trades | WR: {week_wr:.1f}% | PnL: ${week_pnl:,.0f}")
    
    # Analyze losing trades
    losing = trades_df[trades_df['win'] == False]
    print(f"\nAnalyse des {len(losing)} trades perdants:")
    
    # By hour
    hour_losses = losing.groupby('hour').size().sort_values(ascending=False)
    print(f"\n  Pires heures (pertes):")
    for hour, count in hour_losses.head(5).items():
        print(f"    {hour:02d}:00 - {count} pertes")
    
    # Average RSI/Stoch of losing trades
    print(f"\n  Indicateurs moyens des pertes:")
    print(f"    RSI moyen: {losing['rsi'].mean():.1f}")
    print(f"    Stoch moyen: {losing['stoch'].mean():.1f}")
    print(f"    Volume ratio moyen: {losing['volume_ratio'].mean():.2f}")
    
    return trades_df

def main():
    print("=" * 70)
    print("ANALYSE APPROFONDIE - JUIN 2025")
    print("Pourquoi ce mois est-il faible meme avec V8 FTFC?")
    print("=" * 70)
    
    all_trades = []
    for pair in ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']:
        trades = analyze_june_2025(pair)
        if trades is not None:
            trades['pair'] = pair.split('/')[0]
            all_trades.append(trades)
    
    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        
        print("\n" + "=" * 70)
        print("SYNTHESE JUIN 2025 - TOUS LES PAIRS")
        print("=" * 70)
        
        total = len(combined)
        wins = combined['win'].sum()
        wr = wins / total * 100
        pnl = combined['pnl'].sum()
        
        print(f"\nTotal: {total} trades | WR: {wr:.1f}% | PnL: ${pnl:,.0f}")
        
        # Problem identification
        print("\n" + "=" * 70)
        print("IDENTIFICATION DU PROBLEME")
        print("=" * 70)
        
        # Signal distribution
        up_trades = combined[combined['signal'] == 'UP']
        down_trades = combined[combined['signal'] == 'DOWN']
        
        up_wr = up_trades['win'].mean() * 100 if len(up_trades) > 0 else 0
        down_wr = down_trades['win'].mean() * 100 if len(down_trades) > 0 else 0
        
        print(f"\nSignaux UP: {len(up_trades)} trades | WR: {up_wr:.1f}%")
        print(f"Signaux DOWN: {len(down_trades)} trades | WR: {down_wr:.1f}%")
        
        # FTFC distribution
        print(f"\nDistribution FTFC:")
        for bias in ['BULLISH', 'NEUTRAL', 'BEARISH']:
            bias_df = combined[combined['ftfc_bias'] == bias]
            if len(bias_df) > 0:
                print(f"  {bias}: {len(bias_df)} trades ({len(bias_df)/total*100:.0f}%) | WR: {bias_df['win'].mean()*100:.1f}%")
        
        # Volume analysis
        low_vol = combined[combined['volume_ratio'] < 0.7]
        normal_vol = combined[combined['volume_ratio'] >= 0.7]
        
        print(f"\nVolume:")
        print(f"  Faible (<70%): {len(low_vol)} trades | WR: {low_vol['win'].mean()*100:.1f}%")
        print(f"  Normal (>=70%): {len(normal_vol)} trades | WR: {normal_vol['win'].mean()*100:.1f}%")
        
        # Proposed additional filter
        print("\n" + "=" * 70)
        print("SOLUTION PROPOSEE")
        print("=" * 70)
        
        # Test with volume filter
        filtered = combined[combined['volume_ratio'] >= 0.8]
        if len(filtered) > 0:
            f_wr = filtered['win'].mean() * 100
            f_pnl = filtered['pnl'].sum()
            print(f"\nAvec filtre Volume >= 80%:")
            print(f"  Trades: {len(filtered)} (vs {total})")
            print(f"  Win Rate: {f_wr:.1f}% (vs {wr:.1f}%)")
            print(f"  PnL: ${f_pnl:,.0f} (vs ${pnl:,.0f})")
        
        # Test with stricter RSI
        filtered2 = combined[
            ((combined['signal'] == 'UP') & (combined['rsi'] < 35)) |
            ((combined['signal'] == 'DOWN') & (combined['rsi'] > 70))
        ]
        if len(filtered2) > 0:
            f2_wr = filtered2['win'].mean() * 100
            f2_pnl = filtered2['pnl'].sum()
            print(f"\nAvec RSI plus strict (35/70):")
            print(f"  Trades: {len(filtered2)} (vs {total})")
            print(f"  Win Rate: {f2_wr:.1f}% (vs {wr:.1f}%)")
            print(f"  PnL: ${f2_pnl:,.0f} (vs ${pnl:,.0f})")
        
        # Combine both filters
        filtered3 = combined[
            (combined['volume_ratio'] >= 0.8) &
            (
                ((combined['signal'] == 'UP') & (combined['rsi'] < 35)) |
                ((combined['signal'] == 'DOWN') & (combined['rsi'] > 70))
            )
        ]
        if len(filtered3) > 0:
            f3_wr = filtered3['win'].mean() * 100
            f3_pnl = filtered3['pnl'].sum()
            print(f"\nCombinaison (Volume + RSI strict):")
            print(f"  Trades: {len(filtered3)} (vs {total})")
            print(f"  Win Rate: {f3_wr:.1f}% (vs {wr:.1f}%)")
            print(f"  PnL: ${f3_pnl:,.0f} (vs ${pnl:,.0f})")

if __name__ == "__main__":
    main()
