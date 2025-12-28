#!/usr/bin/env python3
"""
Test de nouveaux indicateurs pour améliorer le WR
Objectif: Passer de $11,600 à $15,000/mois
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import time

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


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule TOUS les indicateurs"""
    df = df.copy()

    # === RSI ===
    for period in [5, 7, 9, 14]:
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        df[f'rsi_{period}'] = 100 - (100 / (1 + rs))

    # === Stochastic ===
    for period in [5, 9, 14]:
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        df[f'stoch_{period}'] = 100 * (df['close'] - low_min) / (high_max - low_min)

    # === MACD ===
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    df['macd_cross_up'] = (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1))
    df['macd_cross_down'] = (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1))
    df['macd_bullish'] = df['macd'] > df['macd_signal']
    df['macd_bearish'] = df['macd'] < df['macd_signal']

    # === Bollinger Bands ===
    for period in [20]:
        sma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        df[f'bb_upper_{period}'] = sma + (2 * std)
        df[f'bb_lower_{period}'] = sma - (2 * std)
        df[f'bb_mid_{period}'] = sma
        df[f'bb_pct_{period}'] = (df['close'] - df[f'bb_lower_{period}']) / (df[f'bb_upper_{period}'] - df[f'bb_lower_{period}'])
        # Signaux BB
        df[f'bb_oversold_{period}'] = df['close'] < df[f'bb_lower_{period}']
        df[f'bb_overbought_{period}'] = df['close'] > df[f'bb_upper_{period}']

    # === Williams %R ===
    for period in [14]:
        highest_high = df['high'].rolling(period).max()
        lowest_low = df['low'].rolling(period).min()
        df[f'williams_{period}'] = -100 * (highest_high - df['close']) / (highest_high - lowest_low)

    # === CCI (Commodity Channel Index) ===
    for period in [20]:
        tp = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
        df[f'cci_{period}'] = (tp - sma_tp) / (0.015 * mad)

    # === ADX (Average Directional Index) ===
    period = 14
    high_diff = df['high'].diff()
    low_diff = df['low'].diff().abs() * -1

    plus_dm = np.where((high_diff > low_diff.abs()) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff.abs() > high_diff) & (low_diff < 0), low_diff.abs(), 0)

    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(period).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['adx'] = dx.rolling(period).mean()
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di

    # === EMA Crossovers ===
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_bullish'] = df['ema_9'] > df['ema_21']
    df['ema_bearish'] = df['ema_9'] < df['ema_21']

    # === Momentum ===
    df['momentum_10'] = df['close'] - df['close'].shift(10)
    df['momentum_pct'] = df['close'].pct_change(10) * 100

    # === Volume ===
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']
    df['vol_spike'] = df['vol_ratio'] > 1.5

    # === Consecutive candles ===
    is_up = (df['close'] > df['open']).astype(int)
    is_down = (df['close'] < df['open']).astype(int)
    up_groups = (is_up != is_up.shift()).cumsum()
    down_groups = (is_down != is_down.shift()).cumsum()
    df['consec_up'] = is_up.groupby(up_groups).cumsum()
    df['consec_down'] = is_down.groupby(down_groups).cumsum()

    # Hour
    df['hour'] = df['datetime'].dt.hour

    return df


def backtest_strategy(df: pd.DataFrame, strategy: dict) -> dict:
    """Backtest une stratégie"""
    if df is None or len(df) < 100:
        return None

    name = strategy['name']
    up_condition = strategy['up_condition'](df)
    down_condition = strategy['down_condition'](df)

    trades = []
    last_idx = -4

    for i in range(50, len(df) - 1):
        if i - last_idx < 4:
            continue

        if up_condition.iloc[i]:
            next_row = df.iloc[i + 1]
            win = next_row['close'] > next_row['open']
            trades.append({'signal': 'UP', 'win': win})
            last_idx = i
        elif down_condition.iloc[i]:
            next_row = df.iloc[i + 1]
            win = next_row['close'] < next_row['open']
            trades.append({'signal': 'DOWN', 'win': win})
            last_idx = i

    if len(trades) < 50:
        return None

    wins = sum(1 for t in trades if t['win'])
    total = len(trades)
    wr = wins / total
    days = (df['datetime'].max() - df['datetime'].min()).days or 1
    tpd = total / days

    pnl_per_trade = (wr * WIN_PROFIT) + ((1 - wr) * (-BET))
    pnl_per_month = pnl_per_trade * tpd * DAYS_MONTH

    return {
        'name': name,
        'trades': total,
        'wins': wins,
        'wr': wr,
        'tpd': tpd,
        'pnl_month': pnl_per_month
    }


def define_strategies():
    """Définit toutes les stratégies à tester"""
    strategies = []

    # === 1. BASELINE: RSI + Stoch (actuel) ===
    strategies.append({
        'name': 'Baseline RSI+Stoch',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70)
    })

    # === 2. RSI + Stoch + MACD Confirmation ===
    strategies.append({
        'name': 'RSI+Stoch+MACD',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['macd_bullish']),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['macd_bearish'])
    })

    # === 3. RSI + Stoch + MACD Histogram ===
    strategies.append({
        'name': 'RSI+Stoch+MACD_Hist>0',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['macd_hist'] > 0),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['macd_hist'] < 0)
    })

    # === 4. Bollinger Bands seul ===
    strategies.append({
        'name': 'Bollinger Bands',
        'up_condition': lambda df: df['bb_oversold_20'],
        'down_condition': lambda df: df['bb_overbought_20']
    })

    # === 5. RSI + Bollinger ===
    strategies.append({
        'name': 'RSI+Bollinger',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['bb_pct_20'] < 0.2),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['bb_pct_20'] > 0.8)
    })

    # === 6. RSI + Stoch + Bollinger ===
    strategies.append({
        'name': 'RSI+Stoch+BB',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['bb_pct_20'] < 0.2),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['bb_pct_20'] > 0.8)
    })

    # === 7. Williams %R ===
    strategies.append({
        'name': 'Williams %R',
        'up_condition': lambda df: df['williams_14'] < -80,
        'down_condition': lambda df: df['williams_14'] > -20
    })

    # === 8. RSI + Williams ===
    strategies.append({
        'name': 'RSI+Williams',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['williams_14'] < -80),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['williams_14'] > -20)
    })

    # === 9. CCI ===
    strategies.append({
        'name': 'CCI',
        'up_condition': lambda df: df['cci_20'] < -100,
        'down_condition': lambda df: df['cci_20'] > 100
    })

    # === 10. RSI + CCI ===
    strategies.append({
        'name': 'RSI+CCI',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['cci_20'] < -100),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['cci_20'] > 100)
    })

    # === 11. RSI + Stoch + Low ADX (range market) ===
    strategies.append({
        'name': 'RSI+Stoch+LowADX',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['adx'] < 25),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['adx'] < 25)
    })

    # === 12. RSI + Stoch + EMA trend ===
    strategies.append({
        'name': 'RSI+Stoch+EMA_trend',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['ema_bullish']),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['ema_bearish'])
    })

    # === 13. Triple: RSI + Stoch + MACD + BB ===
    strategies.append({
        'name': 'RSI+Stoch+MACD+BB',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['macd_bullish']) & (df['bb_pct_20'] < 0.3),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['macd_bearish']) & (df['bb_pct_20'] > 0.7)
    })

    # === 14. RSI strict + Consec ===
    strategies.append({
        'name': 'RSI_strict+Consec',
        'up_condition': lambda df: (df['rsi_7'] < 30) & (df['consec_down'] >= 2),
        'down_condition': lambda df: (df['rsi_7'] > 70) & (df['consec_up'] >= 2)
    })

    # === 15. RSI + Stoch + Volume spike ===
    strategies.append({
        'name': 'RSI+Stoch+VolSpike',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['vol_ratio'] > 1.2),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['vol_ratio'] > 1.2)
    })

    # === 16. RSI extreme + Stoch extreme ===
    strategies.append({
        'name': 'RSI_extreme+Stoch_extreme',
        'up_condition': lambda df: (df['rsi_7'] < 25) & (df['stoch_5'] < 20),
        'down_condition': lambda df: (df['rsi_7'] > 75) & (df['stoch_5'] > 80)
    })

    # === 17. Multiple RSI periods ===
    strategies.append({
        'name': 'Multi_RSI',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['rsi_14'] < 40),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['rsi_14'] > 60)
    })

    # === 18. RSI + Momentum positive ===
    strategies.append({
        'name': 'RSI+Momentum',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['momentum_10'] > 0),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['momentum_10'] < 0)
    })

    # === 19. MACD Cross + RSI ===
    strategies.append({
        'name': 'MACD_cross+RSI',
        'up_condition': lambda df: (df['macd_cross_up']) & (df['rsi_7'] < 50),
        'down_condition': lambda df: (df['macd_cross_down']) & (df['rsi_7'] > 50)
    })

    # === 20. Full combo: RSI + Stoch + BB + MACD + Low ADX ===
    strategies.append({
        'name': 'FULL_COMBO',
        'up_condition': lambda df: (df['rsi_7'] < 35) & (df['stoch_5'] < 30) & (df['bb_pct_20'] < 0.25) & (df['macd_bullish']) & (df['adx'] < 30),
        'down_condition': lambda df: (df['rsi_7'] > 65) & (df['stoch_5'] > 70) & (df['bb_pct_20'] > 0.75) & (df['macd_bearish']) & (df['adx'] < 30)
    })

    return strategies


def main():
    print("=" * 70)
    print("🧪 TEST NOUVEAUX INDICATEURS")
    print("=" * 70)
    print("Objectif: Trouver une stratégie pour $15k/mois avec $100/trade")
    print("=" * 70)

    exchange = ccxt.binance({'enableRateLimit': True})
    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'SOL/USDT']

    # Télécharger les données
    print("\n📥 TÉLÉCHARGEMENT DES DONNÉES...")
    all_data = {}
    for symbol in symbols:
        base = symbol.split('/')[0]
        df = download_data(exchange, symbol, [2024, 2025])
        if df is not None:
            df = calculate_all_indicators(df)
            all_data[base] = df

    strategies = define_strategies()

    # Tester chaque stratégie sur chaque pair
    print("\n" + "=" * 70)
    print("📊 RÉSULTATS PAR STRATÉGIE")
    print("=" * 70)

    all_results = []

    for strategy in strategies:
        total_tpd = 0
        total_pnl = 0
        pair_results = {}

        for base, df in all_data.items():
            result = backtest_strategy(df, strategy)
            if result:
                pair_results[base] = result
                total_tpd += result['tpd']
                total_pnl += result['pnl_month']

        if pair_results:
            avg_wr = sum(r['wr'] * r['tpd'] for r in pair_results.values()) / total_tpd if total_tpd > 0 else 0
            all_results.append({
                'name': strategy['name'],
                'total_tpd': total_tpd,
                'avg_wr': avg_wr,
                'total_pnl': total_pnl,
                'pair_results': pair_results
            })

    # Trier par PnL
    all_results = sorted(all_results, key=lambda x: x['total_pnl'], reverse=True)

    # Afficher top 10
    print(f"\n{'Stratégie':<30} {'T/jour':<10} {'WR':<10} {'PnL/mois':<15} {'vs $15k'}")
    print("-" * 80)

    for r in all_results[:15]:
        pct = r['total_pnl'] / TARGET_PNL * 100
        status = "✅" if r['total_pnl'] >= TARGET_PNL else ""
        print(f"{r['name']:<30} {r['total_tpd']:<10.1f} {r['avg_wr']*100:<8.1f}% ${r['total_pnl']:<13,.0f} {pct:>5.0f}% {status}")

    # Détails du meilleur
    if all_results:
        best = all_results[0]
        print("\n" + "=" * 70)
        print(f"🏆 MEILLEURE STRATÉGIE: {best['name']}")
        print("=" * 70)

        for base, r in best['pair_results'].items():
            print(f"   {base}: {r['tpd']:.1f} T/j | {r['wr']*100:.1f}% WR | ${r['pnl_month']:,.0f}/mois")

        print(f"\n   TOTAL: {best['total_tpd']:.0f} T/j | {best['avg_wr']*100:.1f}% WR | ${best['total_pnl']:,.0f}/mois")

        if best['total_pnl'] < TARGET_PNL:
            gap = TARGET_PNL - best['total_pnl']
            bet_needed = BET * (TARGET_PNL / best['total_pnl'])
            print(f"\n   ❌ Manque ${gap:,.0f}")
            print(f"   💡 Avec ${bet_needed:.0f}/trade → ${TARGET_PNL:,}/mois")

    # Chercher les stratégies avec le meilleur WR (même si moins de trades)
    print("\n" + "=" * 70)
    print("📈 TOP 5 PAR WIN RATE (min 20 trades/jour)")
    print("=" * 70)

    wr_sorted = [r for r in all_results if r['total_tpd'] >= 20]
    wr_sorted = sorted(wr_sorted, key=lambda x: x['avg_wr'], reverse=True)

    print(f"\n{'Stratégie':<30} {'T/jour':<10} {'WR':<10} {'PnL/mois'}")
    print("-" * 65)

    for r in wr_sorted[:5]:
        print(f"{r['name']:<30} {r['total_tpd']:<10.1f} {r['avg_wr']*100:<8.1f}% ${r['total_pnl']:,.0f}")


if __name__ == "__main__":
    main()
