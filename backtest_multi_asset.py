#!/usr/bin/env python3
"""
Backtest Multi-Asset pour stratégie Mean Reversion
Test sur BTC, ETH, XRP - 2024 et 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime
import ccxt
from pathlib import Path
import sys

# Ajouter le path
sys.path.insert(0, str(Path(__file__).parent))

from src.strategy_mean_reversion import MeanReversionStrategy


def download_data(symbol: str, timeframe: str = '15m', months: int = 24) -> pd.DataFrame:
    """Télécharge les données depuis Binance"""
    print(f"  Téléchargement {symbol}...")

    exchange = ccxt.binance({'enableRateLimit': True})

    since = exchange.parse8601(
        (datetime.now() - pd.Timedelta(days=months * 30)).isoformat()
    )

    all_ohlcv = []
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break
        except Exception as e:
            print(f"  Erreur: {e}")
            break

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)

    # Sauvegarder
    base, quote = symbol.split('/')
    filepath = Path(f"data/historical/{base}_{quote}_15m.csv")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(filepath, index=False)

    print(f"  Sauvegardé: {len(df)} bougies")
    return df


def load_data(symbol: str) -> pd.DataFrame:
    """Charge les données depuis le fichier CSV"""
    base, quote = symbol.split('/')
    filepath = Path(f"data/historical/{base}_{quote}_15m.csv")

    if not filepath.exists() or filepath.stat().st_size < 1000:
        return download_data(symbol)

    df = pd.read_csv(filepath)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000,
    bet_size: float = 100
) -> dict:
    """Exécute le backtest sur une période donnée"""

    # Filtrer par date
    df_period = df[
        (df['timestamp'] >= pd.to_datetime(start_date, utc=True)) &
        (df['timestamp'] < pd.to_datetime(end_date, utc=True))
    ].copy()

    if len(df_period) < 100:
        return {'error': f'Pas assez de données ({len(df_period)} bougies)'}

    # Stratégie
    strategy = MeanReversionStrategy(
        rsi_period=14,
        rsi_oversold=30,
        rsi_overbought=70,
        consec_threshold=3,
        use_momentum_filter=True
    )

    # Backtest
    results = strategy.backtest(df_period, initial_capital, bet_size)
    results['symbol'] = symbol
    results['period'] = f"{start_date} to {end_date}"
    results['candles'] = len(df_period)

    return results


def print_results(results: dict, title: str):
    """Affiche les résultats d'un backtest"""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")

    if 'error' in results:
        print(f"  ❌ Erreur: {results['error']}")
        return

    wr = results['win_rate']
    status = "✅" if wr >= 55 else "⚠️" if wr >= 52.63 else "❌"

    print(f"  Période     : {results['period']}")
    print(f"  Bougies     : {results['candles']:,}")
    print(f"  Trades      : {results['total_trades']:,}")
    print(f"  Trades/jour : {results['trades_per_day']:.1f}")
    print(f"  Win Rate    : {wr:.2f}% {status}")
    print(f"  UP  trades  : {results['up_trades']:,} ({results['up_win_rate']:.1f}%)")
    print(f"  DOWN trades : {results['down_trades']:,} ({results['down_win_rate']:.1f}%)")
    print(f"  PnL         : ${results['total_pnl']:+,.0f}")
    print(f"  ROI         : {results['total_return']:+.2f}%")
    print(f"  Max DD      : {results['max_drawdown']:.2f}%")


def main():
    print("=" * 70)
    print("BACKTEST MULTI-ASSET - STRATÉGIE MEAN REVERSION")
    print("=" * 70)

    symbols = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']

    # Périodes
    periods = [
        ('2024-01-01', '2025-01-01', '2024'),
        ('2025-01-01', '2025-12-31', '2025'),
    ]

    # Charger les données
    print("\n📥 CHARGEMENT DES DONNÉES")
    print("-" * 40)

    data = {}
    for symbol in symbols:
        print(f"\n{symbol}:")
        df = load_data(symbol)
        if df is not None and len(df) > 0:
            data[symbol] = df
            print(f"  ✅ {len(df):,} bougies")
            print(f"  📅 {df['timestamp'].min()} → {df['timestamp'].max()}")
        else:
            print(f"  ❌ Pas de données")

    # Résultats globaux
    all_results = []

    # Backtest par période
    for start, end, year in periods:
        print(f"\n\n{'#' * 70}")
        print(f"# ANNÉE {year}")
        print(f"{'#' * 70}")

        for symbol in symbols:
            if symbol not in data:
                continue

            results = run_backtest(data[symbol], symbol, start, end)
            results['year'] = year
            all_results.append(results)

            print_results(results, f"{symbol} - {year}")

    # Résumé global
    print("\n\n" + "=" * 70)
    print("RÉSUMÉ GLOBAL")
    print("=" * 70)

    print("\n{:<12} {:<6} {:>8} {:>10} {:>10} {:>12}".format(
        "SYMBOLE", "ANNÉE", "WIN RATE", "TRADES/J", "ROI", "STATUS"
    ))
    print("-" * 60)

    for r in all_results:
        if 'error' in r:
            continue

        wr = r['win_rate']
        status = "✅ OK" if wr >= 55 else "⚠️ LIMITE" if wr >= 52.63 else "❌ KO"

        print(f"{r['symbol']:<12} {r['year']:<6} {wr:>7.1f}%  {r['trades_per_day']:>9.1f}  {r['total_return']:>+9.1f}%  {status}")

    # Totaux par année
    print("\n" + "-" * 60)

    for year in ['2024', '2025']:
        year_results = [r for r in all_results if r.get('year') == year and 'error' not in r]
        if year_results:
            total_trades = sum(r['total_trades'] for r in year_results)
            total_wins = sum(r['wins'] for r in year_results)
            avg_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
            total_pnl = sum(r['total_pnl'] for r in year_results)

            status = "✅" if avg_wr >= 55 else "⚠️" if avg_wr >= 52.63 else "❌"
            print(f"{'TOTAL ' + year:<12} {'ALL':<6} {avg_wr:>7.1f}%  {'-':>9}  ${total_pnl:>+8,.0f}  {status}")

    print("\n" + "=" * 70)

    # Seuil de rentabilité
    print("\n💡 Rappel: Seuil de rentabilité Polymarket (payout 1.9x) = 52.63%")
    print("   Win Rate >= 55% = Objectif atteint")
    print("   Win Rate >= 52.63% = Rentable mais limite")
    print("   Win Rate < 52.63% = Non rentable")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
