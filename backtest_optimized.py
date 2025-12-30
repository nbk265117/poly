#!/usr/bin/env python3
"""
Backtest PnL Mois par Mois - Config OPTIMISEE (44 combos bloques)
=================================================================
3 paires: BTC, ETH, XRP
Periode: 2024-2025
Mise: $100/trade @ 52.5c
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

# Indicateurs
RSI_PERIOD = 7
RSI_OVERSOLD = 38
RSI_OVERBOUGHT = 58

STOCH_K_PERIOD = 5
STOCH_D_PERIOD = 3
STOCH_OVERSOLD = 30
STOCH_OVERBOUGHT = 80

# Trading
ENTRY_PRICE = 0.525  # 52.5c
STAKE = 100  # $100 par trade
WIN_PAYOUT = STAKE * (1 / ENTRY_PRICE - 1)  # +$90.48
LOSS_PAYOUT = -STAKE  # -$100

# 44 Combos jour+heure bloques (WR < 53%)
BLOCKED_COMBOS = [
    (4, 14), (6, 8), (0, 15), (0, 18), (1, 5), (0, 0), (1, 7), (0, 2), (5, 3), (4, 7),
    (6, 22), (4, 17), (4, 18), (4, 2), (0, 14), (4, 10), (0, 1), (1, 19), (0, 20), (0, 6),
    (1, 18), (3, 22), (6, 13), (3, 5), (1, 22), (3, 16), (0, 7), (2, 3), (6, 23), (3, 9),
    (4, 6), (4, 5), (2, 23), (1, 4), (2, 0), (2, 19), (0, 3), (4, 15), (2, 8), (2, 17),
    (1, 1), (1, 14), (1, 16), (3, 4)
]

# Paires a analyser
SYMBOLS = ['BTC', 'ETH', 'XRP']

# Chemin des donnees
DATA_PATH = Path("data/historical")

# ============================================================
# FONCTIONS
# ============================================================

def load_data(symbol: str) -> pd.DataFrame:
    """Charge les donnees historiques d'une paire."""
    file_path = DATA_PATH / f"{symbol}_USDT_15m.csv"
    if not file_path.exists():
        print(f"Fichier non trouve: {file_path}")
        return None

    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def calc_rsi(prices: pd.Series, period: int = 7) -> pd.Series:
    """Calcule le RSI."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_stochastic(df: pd.DataFrame, k_period: int = 5) -> pd.Series:
    """Calcule le Stochastic %K."""
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    k = 100 * (df['close'] - low_min) / (high_max - low_min)
    return k


def is_blocked(dow: int, hour: int) -> bool:
    """Verifie si le combo jour+heure est bloque."""
    return (dow, hour) in BLOCKED_COMBOS


def get_signal(rsi: float, stoch: float) -> str:
    """Genere le signal de trading."""
    if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
        return 'UP'
    elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
        return 'DOWN'
    return None


def run_backtest() -> pd.DataFrame:
    """Execute le backtest sur toutes les paires."""
    all_trades = []

    for symbol in SYMBOLS:
        print(f"Chargement {symbol}...")
        df = load_data(symbol)
        if df is None:
            continue

        # Calcul des indicateurs
        df['rsi'] = calc_rsi(df['close'], RSI_PERIOD)
        df['stoch'] = calc_stochastic(df, STOCH_K_PERIOD)

        # Extraction date/heure
        df['hour'] = df['timestamp'].dt.hour
        df['dow'] = df['timestamp'].dt.dayofweek
        df['year'] = df['timestamp'].dt.year
        df['month'] = df['timestamp'].dt.month

        # Resultat reel (prochaine bougie)
        df['next_close'] = df['close'].shift(-1)
        df['actual_up'] = df['next_close'] > df['close']

        # Filtrer annees
        df = df[df['year'].isin([2024, 2025])]

        # Generer les trades
        for idx, row in df.iterrows():
            # Skip si donnees manquantes
            if pd.isna(row['rsi']) or pd.isna(row['stoch']) or pd.isna(row['next_close']):
                continue

            # Skip si combo bloque
            if is_blocked(row['dow'], row['hour']):
                continue

            # Generer signal
            signal = get_signal(row['rsi'], row['stoch'])
            if signal is None:
                continue

            # Calculer resultat
            win = (signal == 'UP' and row['actual_up']) or \
                  (signal == 'DOWN' and not row['actual_up'])
            pnl = WIN_PAYOUT if win else LOSS_PAYOUT

            all_trades.append({
                'timestamp': row['timestamp'],
                'symbol': symbol,
                'year': int(row['year']),
                'month': int(row['month']),
                'dow': int(row['dow']),
                'hour': int(row['hour']),
                'rsi': round(row['rsi'], 2),
                'stoch': round(row['stoch'], 2),
                'signal': signal,
                'win': win,
                'pnl': pnl
            })

    return pd.DataFrame(all_trades)


def print_monthly_report(trades_df: pd.DataFrame):
    """Affiche le rapport mensuel."""
    month_names = ['', 'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre']

    print("=" * 85)
    print("       CONFIG OPTIMISEE - 44 COMBOS BLOQUES - $100/TRADE @ 52.5c")
    print("=" * 85)

    for year in [2024, 2025]:
        print(f"\n{'=' * 85}")
        print(f"                              ANNEE {year}")
        print("=" * 85)
        print(f"{'Mois':<12} {'Trades':>10} {'Wins':>10} {'Losses':>10} {'WR':>10} {'PnL':>16}")
        print("-" * 85)

        year_df = trades_df[trades_df['year'] == year]
        total_trades = 0
        total_wins = 0
        total_pnl = 0
        months_count = 0

        for month in range(1, 13):
            month_df = year_df[year_df['month'] == month]
            if len(month_df) == 0:
                continue

            trades = len(month_df)
            wins = int(month_df['win'].sum())
            losses = trades - wins
            wr = wins / trades * 100
            pnl = month_df['pnl'].sum()

            total_trades += trades
            total_wins += wins
            total_pnl += pnl
            months_count += 1

            wr_indicator = "[OK]" if wr >= 55 else "[--]" if wr >= 52 else "[!!]"
            pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
            print(f"{month_names[month]:<12} {trades:>10,} {wins:>10,} {losses:>10,} {wr:>8.1f}% {wr_indicator} {pnl_str:>14}")

        print("-" * 85)
        total_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        total_pnl_str = f"+${total_pnl:,.0f}"
        avg_pnl_str = f"+${total_pnl/months_count:,.0f}"
        print(f"{'TOTAL':<12} {total_trades:>10,} {total_wins:>10,} {total_trades-total_wins:>10,} {total_wr:>8.1f}%      {total_pnl_str:>14}")
        print(f"{'MOY/MOIS':<12} {total_trades//months_count:>10,} {total_wins//months_count:>10,} {(total_trades-total_wins)//months_count:>10,} {total_wr:>8.1f}%      {avg_pnl_str:>14}")

        # Best/Worst
        monthly_pnl = year_df.groupby('month')['pnl'].sum()
        best_month = month_names[monthly_pnl.idxmax()]
        worst_month = month_names[monthly_pnl.idxmin()]
        best_pnl = monthly_pnl.max()
        worst_pnl = monthly_pnl.min()
        best_str = f"+${best_pnl:,.0f}" if best_pnl >= 0 else f"-${abs(best_pnl):,.0f}"
        worst_str = f"+${worst_pnl:,.0f}" if worst_pnl >= 0 else f"-${abs(worst_pnl):,.0f}"
        print(f"\nMeilleur: {best_month} ({best_str})")
        print(f"Pire: {worst_month} ({worst_str})")

    # Resume final
    print(f"\n{'=' * 85}")
    print("                         RESUME COMPARATIF")
    print("=" * 85)
    print(f"{'Annee':<10} {'Trades':>12} {'Win Rate':>12} {'PnL Total':>18} {'PnL/Mois':>18}")
    print("-" * 85)

    for year in [2024, 2025]:
        year_df = trades_df[trades_df['year'] == year]
        trades = len(year_df)
        wins = year_df['win'].sum()
        wr = wins / trades * 100
        pnl = year_df['pnl'].sum()
        months = year_df['month'].nunique()
        pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
        avg_str = f"+${pnl/months:,.0f}" if pnl >= 0 else f"-${abs(pnl/months):,.0f}"
        print(f"{year:<10} {trades:>12,} {wr:>11.2f}% {pnl_str:>18} {avg_str:>18}")

    print("-" * 85)
    total_trades = len(trades_df)
    total_wins = trades_df['win'].sum()
    total_wr = total_wins / total_trades * 100
    total_pnl = trades_df['pnl'].sum()
    total_months = trades_df.groupby(['year', 'month']).ngroups
    total_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
    avg_str = f"+${total_pnl/total_months:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl/total_months):,.0f}"
    print(f"{'TOTAL':<10} {total_trades:>12,} {total_wr:>11.2f}% {total_str:>18} {avg_str:>18}")
    print("=" * 85)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Demarrage du backtest OPTIMISE...")
    print(f"   RSI({RSI_PERIOD}): {RSI_OVERSOLD}/{RSI_OVERBOUGHT}")
    print(f"   Stoch({STOCH_K_PERIOD}): {STOCH_OVERSOLD}/{STOCH_OVERBOUGHT}")
    print(f"   Mise: ${STAKE} @ {ENTRY_PRICE*100:.1f}c")
    print(f"   Combos bloques: {len(BLOCKED_COMBOS)}")
    print()

    # Executer le backtest
    trades_df = run_backtest()

    if len(trades_df) == 0:
        print("Aucun trade trouve!")
        exit(1)

    print(f"\n{len(trades_df):,} trades trouves")

    # Afficher le rapport
    print_monthly_report(trades_df)
