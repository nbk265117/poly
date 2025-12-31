#!/usr/bin/env python3
"""
Trouver la configuration optimale:
- Minimum 60 trades/jour
- Minimum $10k PnL/mois
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

def get_ftfc_bias(df_1h, df_4h, timestamp, threshold=1.0):
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
    
    if ftfc_score > threshold:
        return 'BULLISH', ftfc_score
    elif ftfc_score < -threshold:
        return 'BEARISH', ftfc_score
    return 'NEUTRAL', ftfc_score

def simulate_strategy(df_15m, df_1h, df_4h, config, bet_size=100, entry_price=0.525):
    """
    Simulate with configurable parameters
    """
    df = df_15m.copy()
    df['rsi'] = calculate_rsi(df['close'], config['rsi_period'])
    df['stoch'] = calculate_stochastic(df, config['stoch_period'])
    
    trades = []
    total = len(df) - 1
    
    for i in range(total):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]
        
        if pd.isna(row['rsi']) or pd.isna(row['stoch']):
            continue
        
        ftfc_bias, ftfc_score = get_ftfc_bias(df_1h, df_4h, row.name, config['ftfc_threshold'])
        
        signal = None
        
        # Check signals based on config
        if row['rsi'] < config['rsi_oversold'] and row['stoch'] < config['stoch_oversold']:
            if config['use_ftfc']:
                if ftfc_bias != 'BEARISH':
                    signal = 'UP'
            else:
                signal = 'UP'
                
        elif row['rsi'] > config['rsi_overbought'] and row['stoch'] > config['stoch_overbought']:
            if config['use_ftfc']:
                if ftfc_bias != 'BULLISH':
                    signal = 'DOWN'
            else:
                signal = 'DOWN'
        
        if signal:
            price_went_up = next_row['close'] > row['close']
            win = (signal == 'UP' and price_went_up) or (signal == 'DOWN' and not price_went_up)
            
            shares = bet_size / entry_price
            pnl = shares * (1 - entry_price) if win else -bet_size
            
            trades.append({
                'timestamp': row.name,
                'signal': signal,
                'win': win,
                'pnl': pnl
            })
    
    return pd.DataFrame(trades)

def test_configuration(config, all_data):
    """Test a configuration across all pairs"""
    all_trades = []
    
    for pair, data in all_data.items():
        trades = simulate_strategy(data['15m'], data['1h'], data['4h'], config)
        trades['pair'] = pair
        all_trades.append(trades)
    
    if not all_trades:
        return None
        
    combined = pd.concat(all_trades, ignore_index=True)
    combined['month'] = combined['timestamp'].dt.to_period('M')
    
    # Calculate metrics
    total_trades = len(combined)
    trades_per_day = total_trades / 730
    total_wr = combined['win'].mean() * 100
    total_pnl = combined['pnl'].sum()
    
    monthly = combined.groupby('month')['pnl'].sum()
    months_under_10k = (monthly < 10000).sum()
    min_month_pnl = monthly.min()
    
    return {
        'trades': total_trades,
        'trades_per_day': trades_per_day,
        'wr': total_wr,
        'pnl': total_pnl,
        'pnl_per_month': total_pnl / 24,
        'months_under_10k': months_under_10k,
        'min_month_pnl': min_month_pnl,
        'monthly': monthly
    }

def main():
    print("=" * 70)
    print("RECHERCHE CONFIGURATION OPTIMALE")
    print("Objectifs: 60+ trades/jour ET $10k+ PnL/mois")
    print("=" * 70)
    
    # Load data for all pairs
    pairs = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
    all_data = {}
    
    for pair in pairs:
        print(f"\nLoading {pair}...")
        all_data[pair.split('/')[0]] = {
            '15m': fetch_ohlcv(pair, '15m', 730),
            '1h': fetch_ohlcv(pair, '1h', 730),
            '4h': fetch_ohlcv(pair, '4h', 730)
        }
    
    # Test configurations
    configs_to_test = [
        # V7 Original (baseline)
        {
            'name': 'V7 Original',
            'rsi_period': 7, 'rsi_oversold': 38, 'rsi_overbought': 68,
            'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 75,
            'use_ftfc': False, 'ftfc_threshold': 1.0
        },
        # V8 FTFC Strict
        {
            'name': 'V8 FTFC Strict',
            'rsi_period': 7, 'rsi_oversold': 38, 'rsi_overbought': 68,
            'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 75,
            'use_ftfc': True, 'ftfc_threshold': 1.0
        },
        # V8 FTFC Relaxed (threshold 1.5)
        {
            'name': 'V8 FTFC Relaxed (1.5)',
            'rsi_period': 7, 'rsi_oversold': 38, 'rsi_overbought': 68,
            'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 75,
            'use_ftfc': True, 'ftfc_threshold': 1.5
        },
        # V8 FTFC Very Relaxed (threshold 2.0)
        {
            'name': 'V8 FTFC Relaxed (2.0)',
            'rsi_period': 7, 'rsi_oversold': 38, 'rsi_overbought': 68,
            'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 75,
            'use_ftfc': True, 'ftfc_threshold': 2.0
        },
        # RSI élargi 40/65
        {
            'name': 'V8 RSI 40/65',
            'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 65,
            'stoch_period': 5, 'stoch_oversold': 30, 'stoch_overbought': 75,
            'use_ftfc': True, 'ftfc_threshold': 1.0
        },
        # Stoch élargi 35/70
        {
            'name': 'V8 Stoch 35/70',
            'rsi_period': 7, 'rsi_oversold': 38, 'rsi_overbought': 68,
            'stoch_period': 5, 'stoch_oversold': 35, 'stoch_overbought': 70,
            'use_ftfc': True, 'ftfc_threshold': 1.0
        },
        # Combo élargi
        {
            'name': 'V8 Combo Elargi',
            'rsi_period': 7, 'rsi_oversold': 40, 'rsi_overbought': 65,
            'stoch_period': 5, 'stoch_oversold': 35, 'stoch_overbought': 70,
            'use_ftfc': True, 'ftfc_threshold': 1.5
        },
    ]
    
    print("\n" + "=" * 70)
    print("RESULTATS DES TESTS")
    print("=" * 70)
    
    results = []
    
    for config in configs_to_test:
        print(f"\nTesting: {config['name']}...")
        result = test_configuration(config, all_data)
        if result:
            result['name'] = config['name']
            result['config'] = config
            results.append(result)
            
            meets_trades = "✅" if result['trades_per_day'] >= 60 else "❌"
            meets_pnl = "✅" if result['months_under_10k'] == 0 else "❌"
            
            print(f"  Trades/jour: {result['trades_per_day']:.0f} {meets_trades}")
            print(f"  Win Rate: {result['wr']:.1f}%")
            print(f"  PnL/Mois: ${result['pnl_per_month']:,.0f}")
            print(f"  Mois < $10k: {result['months_under_10k']} {meets_pnl}")
            print(f"  Min mois: ${result['min_month_pnl']:,.0f}")
    
    # Summary table
    print("\n" + "=" * 70)
    print("TABLEAU COMPARATIF")
    print("=" * 70)
    
    print(f"\n{'Config':<25} {'Trades/J':>10} {'WR':>8} {'PnL/Mois':>12} {'Mois<10k':>10} {'Min Mois':>12} {'Status':>8}")
    print("-" * 90)
    
    for r in results:
        trades_ok = r['trades_per_day'] >= 60
        pnl_ok = r['months_under_10k'] == 0
        status = "✅ OK" if trades_ok and pnl_ok else "❌"
        
        print(f"{r['name']:<25} {r['trades_per_day']:>10.0f} {r['wr']:>7.1f}% ${r['pnl_per_month']:>10,.0f} {r['months_under_10k']:>10} ${r['min_month_pnl']:>10,.0f} {status:>8}")
    
    # Find configurations that meet both criteria
    valid_configs = [r for r in results if r['trades_per_day'] >= 60 and r['months_under_10k'] == 0]
    
    if valid_configs:
        print("\n" + "=" * 70)
        print("CONFIGURATIONS VALIDES (60+ trades/j ET 0 mois < $10k)")
        print("=" * 70)
        
        # Sort by PnL
        valid_configs.sort(key=lambda x: x['pnl'], reverse=True)
        
        for r in valid_configs:
            print(f"\n🎯 {r['name']}")
            print(f"   Trades/jour: {r['trades_per_day']:.0f}")
            print(f"   Win Rate: {r['wr']:.1f}%")
            print(f"   PnL Total: ${r['pnl']:,.0f}")
            print(f"   PnL/Mois: ${r['pnl_per_month']:,.0f}")
            print(f"   Min Mois: ${r['min_month_pnl']:,.0f}")
    else:
        print("\n" + "=" * 70)
        print("AUCUNE CONFIGURATION NE SATISFAIT LES DEUX CRITERES")
        print("=" * 70)
        
        # Show closest options
        print("\nOptions les plus proches:")
        
        # Best for trades
        best_trades = max(results, key=lambda x: x['trades_per_day'] if x['months_under_10k'] <= 2 else 0)
        print(f"\n1. Meilleur trades avec peu de mois faibles: {best_trades['name']}")
        print(f"   {best_trades['trades_per_day']:.0f} trades/j, {best_trades['months_under_10k']} mois < $10k")
        
        # Best for PnL consistency
        best_pnl = min(results, key=lambda x: x['months_under_10k'])
        print(f"\n2. Meilleure consistance PnL: {best_pnl['name']}")
        print(f"   {best_pnl['trades_per_day']:.0f} trades/j, {best_pnl['months_under_10k']} mois < $10k")

    # Show detailed monthly for best candidates
    print("\n" + "=" * 70)
    print("DETAIL MENSUEL - MEILLEURES OPTIONS")
    print("=" * 70)
    
    # Show V7 and best FTFC variant
    for r in results[:3]:
        print(f"\n--- {r['name']} ---")
        print(f"{'Mois':<12} {'PnL':>12}")
        for month, pnl in r['monthly'].items():
            status = "< 10k" if pnl < 10000 else ""
            print(f"{str(month):<12} ${pnl:>10,.0f} {status}")

if __name__ == "__main__":
    main()
