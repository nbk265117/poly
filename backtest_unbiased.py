#!/usr/bin/env python3
"""
Backtest SANS BIAIS - Stratégie RSI + Stochastic
=================================================
Version corrigée pour être ISO Production:
- Signal calculé sur bougie t-1 (disponible en prod)
- Sans filtres horaires optimisés (pas d'overfitting)
- Avec slippage conservateur
- Simulation capital réel 100$

Usage:
    python backtest_unbiased.py
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
ENTRY_PRICE_BACKTEST = 0.525  # Prix théorique 52.5¢
ENTRY_PRICE_CONSERVATIVE = 0.53  # Prix avec slippage 53¢ (plus réaliste)
INITIAL_CAPITAL = 100  # Capital de départ

# Paires à analyser
SYMBOLS = ['BTC', 'ETH', 'XRP']

# Chemin des données
DATA_PATH = Path("data/historical")

# ============================================================
# FONCTIONS
# ============================================================

def load_data(symbol: str) -> pd.DataFrame:
    """Charge les données historiques d'une paire."""
    file_path = DATA_PATH / f"{symbol}_USDT_15m.csv"
    if not file_path.exists():
        print(f"  Fichier non trouvé: {file_path}")
        return None

    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Vérification intégrité des données
    df = df.sort_values('timestamp').drop_duplicates(subset='timestamp')

    # Vérifier les trous dans les données
    df['time_diff'] = df['timestamp'].diff()
    expected_diff = pd.Timedelta(minutes=15)
    gaps = df[df['time_diff'] > expected_diff * 1.5]
    if len(gaps) > 0:
        print(f"  {symbol}: {len(gaps)} trous détectés dans les données")

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


def get_signal(rsi: float, stoch: float) -> str:
    """Génère le signal de trading."""
    if pd.isna(rsi) or pd.isna(stoch):
        return None
    if rsi < RSI_OVERSOLD and stoch < STOCH_OVERSOLD:
        return 'UP'
    elif rsi > RSI_OVERBOUGHT and stoch > STOCH_OVERBOUGHT:
        return 'DOWN'
    return None


def run_backtest(use_slippage: bool = True) -> pd.DataFrame:
    """
    Execute le backtest sur toutes les paires.

    CORRECTION LOOK-AHEAD BIAS:
    - Le signal est calculé avec RSI/Stoch de la bougie t-1 (shift(1))
    - En prod: à la fin de bougie t-1, on calcule le signal
    - On entre en position au début de bougie t
    - Résultat = direction de la bougie t (close[t] vs open[t])
    """
    all_trades = []
    entry_price = ENTRY_PRICE_CONSERVATIVE if use_slippage else ENTRY_PRICE_BACKTEST

    for symbol in SYMBOLS:
        print(f"  Chargement {symbol}...")
        df = load_data(symbol)
        if df is None:
            continue

        # Calcul des indicateurs sur la bougie courante
        df['rsi'] = calc_rsi(df['close'], RSI_PERIOD)
        df['stoch'] = calc_stochastic(df, STOCH_K_PERIOD)

        # CORRECTION LOOK-AHEAD: Signal basé sur bougie PRÉCÉDENTE
        # En prod: on attend la fin de bougie t-1, on calcule, on trade sur bougie t
        df['signal_rsi'] = df['rsi'].shift(1)
        df['signal_stoch'] = df['stoch'].shift(1)

        # Extraction date/heure
        df['hour'] = df['timestamp'].dt.hour
        df['dow'] = df['timestamp'].dt.dayofweek
        df['year'] = df['timestamp'].dt.year
        df['month'] = df['timestamp'].dt.month

        # Résultat de la bougie courante (pas besoin de shift, on prédit la bougie actuelle)
        # On entre au open, on sort au close
        df['candle_up'] = df['close'] > df['open']

        # Filtrer années
        df = df[df['year'].isin([2024, 2025])]

        # Générer les trades
        for idx, row in df.iterrows():
            # Skip si données manquantes
            if pd.isna(row['signal_rsi']) or pd.isna(row['signal_stoch']):
                continue

            # Générer signal basé sur indicateurs de la bougie PRÉCÉDENTE
            signal = get_signal(row['signal_rsi'], row['signal_stoch'])
            if signal is None:
                continue

            # Calculer résultat sur la bougie COURANTE
            win = (signal == 'UP' and row['candle_up']) or \
                  (signal == 'DOWN' and not row['candle_up'])

            all_trades.append({
                'timestamp': row['timestamp'],
                'symbol': symbol,
                'year': int(row['year']),
                'month': int(row['month']),
                'dow': int(row['dow']),
                'hour': int(row['hour']),
                'rsi': round(row['signal_rsi'], 2),
                'stoch': round(row['signal_stoch'], 2),
                'signal': signal,
                'win': win,
            })

    return pd.DataFrame(all_trades)


def simulate_capital(trades_df: pd.DataFrame, initial_capital: float,
                     stake_pct: float, entry_price: float) -> pd.DataFrame:
    """
    Simule l'évolution du capital avec mise en % du capital.

    Args:
        trades_df: DataFrame des trades
        initial_capital: Capital initial
        stake_pct: Pourcentage du capital par trade (ex: 0.05 = 5%)
        entry_price: Prix d'entrée (ex: 0.53)
    """
    trades = trades_df.copy().sort_values('timestamp')

    capital = float(initial_capital)
    capital_history = []

    for idx, row in trades.iterrows():
        stake = capital * stake_pct

        if row['win']:
            # Gain: stake * (1/entry_price - 1)
            pnl = stake * (1 / entry_price - 1)
        else:
            # Perte: -stake
            pnl = -stake

        capital += pnl

        capital_history.append({
            'timestamp': row['timestamp'],
            'capital': capital,
            'pnl': pnl,
            'stake': stake
        })

        # Stop si ruine
        if capital <= 0:
            print(f"  RUINE à {row['timestamp']}")
            break

        # Cap pour éviter overflow
        if capital > 1e15:
            capital = 1e15

    return pd.DataFrame(capital_history)


def simulate_fixed_stake(trades_df: pd.DataFrame, stake: float,
                         entry_price: float) -> pd.DataFrame:
    """
    Simule avec mise fixe par trade.
    """
    trades = trades_df.copy().sort_values('timestamp')

    win_payout = stake * (1 / entry_price - 1)
    loss_payout = -stake

    trades['pnl'] = trades['win'].apply(lambda w: win_payout if w else loss_payout)
    trades['cumulative_pnl'] = trades['pnl'].cumsum()

    return trades


def print_report(trades_df: pd.DataFrame, entry_price: float, stake: float):
    """Affiche le rapport détaillé."""

    win_payout = stake * (1 / entry_price - 1)
    loss_payout = -stake

    month_names = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    print("\n" + "=" * 85)
    print(f"     BACKTEST SANS BIAIS - ${stake:.0f}/trade @ {entry_price*100:.1f}cents")
    print("=" * 85)
    print(f"  Signal: RSI({RSI_PERIOD}) < {RSI_OVERSOLD} ET Stoch({STOCH_K_PERIOD}) < {STOCH_OVERSOLD} -> UP")
    print(f"          RSI({RSI_PERIOD}) > {RSI_OVERBOUGHT} ET Stoch({STOCH_K_PERIOD}) > {STOCH_OVERBOUGHT} -> DOWN")
    print(f"  Gain/trade: +${win_payout:.2f} | Perte/trade: -${abs(loss_payout):.2f}")
    print(f"  Break-even WR: {100/(1 + win_payout/abs(loss_payout)):.1f}%")
    print("=" * 85)

    for year in [2024, 2025]:
        year_df = trades_df[trades_df['year'] == year]
        if len(year_df) == 0:
            continue

        print(f"\n{'=' * 85}")
        print(f"                              ANNEE {year}")
        print("=" * 85)
        print(f"{'Mois':<12} {'Trades':>8} {'Wins':>8} {'Losses':>8} {'WR':>10} {'PnL':>14}")
        print("-" * 85)

        total_trades = 0
        total_wins = 0
        total_pnl = 0
        months_count = 0

        for month in range(1, 13):
            month_df = year_df[year_df['month'] == month]
            if len(month_df) == 0:
                continue

            trades_count = len(month_df)
            wins = int(month_df['win'].sum())
            losses = trades_count - wins
            wr = wins / trades_count * 100
            pnl = wins * win_payout + losses * loss_payout

            total_trades += trades_count
            total_wins += wins
            total_pnl += pnl
            months_count += 1

            wr_indicator = "OK" if wr >= 55 else "??" if wr >= 52.5 else "XX"
            pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
            print(f"{month_names[month]:<12} {trades_count:>8,} {wins:>8,} {losses:>8,} {wr:>8.1f}% {wr_indicator} {pnl_str:>12}")

        print("-" * 85)
        total_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        total_losses = total_trades - total_wins
        total_pnl_str = f"+${total_pnl:,.0f}" if total_pnl >= 0 else f"-${abs(total_pnl):,.0f}"
        avg_pnl = total_pnl / months_count if months_count > 0 else 0
        avg_pnl_str = f"+${avg_pnl:,.0f}" if avg_pnl >= 0 else f"-${abs(avg_pnl):,.0f}"

        print(f"{'TOTAL':<12} {total_trades:>8,} {total_wins:>8,} {total_losses:>8,} {total_wr:>8.1f}%    {total_pnl_str:>12}")
        print(f"{'MOY/MOIS':<12} {total_trades//max(months_count,1):>8,} {total_wins//max(months_count,1):>8,} {total_losses//max(months_count,1):>8,} {total_wr:>8.1f}%    {avg_pnl_str:>12}")

    # Résumé global
    print(f"\n{'=' * 85}")
    print("                         RESUME GLOBAL")
    print("=" * 85)

    total_trades = len(trades_df)
    total_wins = int(trades_df['win'].sum())
    total_losses = total_trades - total_wins
    total_wr = total_wins / total_trades * 100
    total_pnl = total_wins * win_payout + total_losses * loss_payout

    print(f"  Trades totaux:     {total_trades:,}")
    print(f"  Wins:              {total_wins:,}")
    print(f"  Losses:            {total_losses:,}")
    print(f"  Win Rate:          {total_wr:.2f}%")
    print(f"  PnL Total:         {'+'if total_pnl >= 0 else ''}${total_pnl:,.0f}")
    print(f"  PnL/Trade moyen:   {'+'if total_pnl/total_trades >= 0 else ''}${total_pnl/total_trades:.2f}")


def print_simulation(trades_df: pd.DataFrame, initial_capital: float):
    """Affiche la simulation avec capital de départ."""

    print(f"\n{'=' * 85}")
    print(f"           SIMULATION CAPITAL - Depart: ${initial_capital}")
    print("=" * 85)

    # Scénarios de mise
    scenarios = [
        ("Mise fixe $1/trade", 1, ENTRY_PRICE_CONSERVATIVE, "fixed"),
        ("Mise fixe $2/trade", 2, ENTRY_PRICE_CONSERVATIVE, "fixed"),
        ("Mise fixe $5/trade", 5, ENTRY_PRICE_CONSERVATIVE, "fixed"),
        ("Mise 2% capital", 0.02, ENTRY_PRICE_CONSERVATIVE, "pct"),
        ("Mise 5% capital", 0.05, ENTRY_PRICE_CONSERVATIVE, "pct"),
    ]

    print(f"\n{'Scenario':<25} {'Capital Final':>18} {'ROI':>15} {'Max DD':>12}")
    print("-" * 75)

    for name, param, entry_price, mode in scenarios:
        if mode == "fixed":
            sim_df = simulate_fixed_stake(trades_df, param, entry_price)
            final_capital = initial_capital + sim_df['pnl'].sum()
            max_dd = sim_df['cumulative_pnl'].min()
        else:
            sim_df = simulate_capital(trades_df, initial_capital, param, entry_price)
            if len(sim_df) == 0:
                continue
            final_capital = sim_df['capital'].iloc[-1]
            # Calcul drawdown
            sim_df['peak'] = sim_df['capital'].cummax()
            sim_df['drawdown'] = sim_df['capital'] - sim_df['peak']
            max_dd = sim_df['drawdown'].min()

        roi = (final_capital - initial_capital) / initial_capital * 100

        # Format ROI
        if roi >= 1e12:
            roi_str = f"+{roi/1e12:.1f}T%"
        elif roi >= 1e9:
            roi_str = f"+{roi/1e9:.1f}B%"
        elif roi >= 1e6:
            roi_str = f"+{roi/1e6:.1f}M%"
        elif roi >= 1e3:
            roi_str = f"+{roi/1e3:.1f}K%"
        else:
            roi_str = f"+{roi:.0f}%" if roi >= 0 else f"{roi:.0f}%"

        # Format capital
        if final_capital >= 1e12:
            final_str = f"${final_capital/1e12:.1f}T"
        elif final_capital >= 1e9:
            final_str = f"${final_capital/1e9:.1f}B"
        elif final_capital >= 1e6:
            final_str = f"${final_capital/1e6:.1f}M"
        else:
            final_str = f"${final_capital:,.0f}"

        dd_str = f"${abs(max_dd):,.0f}" if abs(max_dd) < 1e6 else f"${abs(max_dd)/1e6:.1f}M"

        status = "OK" if final_capital > initial_capital else "XX"
        print(f"{name:<25} {final_str:>18} {roi_str:>15} {dd_str:>12} {status}")

    print("-" * 70)
    print("\nNotes:")
    print("  - Max DD = Maximum Drawdown (pire perte depuis le pic)")
    print("  - ROI = Return On Investment")
    print("  - Mise % capital = Kelly-like, plus safe mais gains limités")


def compare_biased_vs_unbiased():
    """Compare les résultats avec et sans correction du biais."""

    print("\n" + "=" * 85)
    print("         COMPARAISON: BACKTEST BIAISE vs SANS BIAIS")
    print("=" * 85)

    # Version biaisée (comme l'original)
    print("\n[1/2] Calcul version BIAISEE (signal sur bougie courante)...")

    all_trades_biased = []
    for symbol in SYMBOLS:
        df = load_data(symbol)
        if df is None:
            continue

        df['rsi'] = calc_rsi(df['close'], RSI_PERIOD)
        df['stoch'] = calc_stochastic(df, STOCH_K_PERIOD)
        df['next_close'] = df['close'].shift(-1)
        df['actual_up'] = df['next_close'] > df['close']
        df['year'] = df['timestamp'].dt.year
        df = df[df['year'].isin([2024, 2025])]

        for idx, row in df.iterrows():
            if pd.isna(row['rsi']) or pd.isna(row['stoch']) or pd.isna(row['next_close']):
                continue
            signal = get_signal(row['rsi'], row['stoch'])
            if signal is None:
                continue
            win = (signal == 'UP' and row['actual_up']) or \
                  (signal == 'DOWN' and not row['actual_up'])
            all_trades_biased.append({'win': win, 'year': row['year']})

    biased_df = pd.DataFrame(all_trades_biased)

    # Version non biaisée
    print("[2/2] Calcul version SANS BIAIS (signal sur bougie precedente)...")
    unbiased_df = run_backtest(use_slippage=True)

    # Comparaison
    print(f"\n{'Metrique':<30} {'Biaise':>15} {'Sans Biais':>15} {'Diff':>12}")
    print("-" * 75)

    for year in [2024, 2025, 'Total']:
        if year == 'Total':
            b_df = biased_df
            u_df = unbiased_df
            label = "TOTAL"
        else:
            b_df = biased_df[biased_df['year'] == year]
            u_df = unbiased_df[unbiased_df['year'] == year]
            label = str(year)

        b_trades = len(b_df)
        b_wr = b_df['win'].mean() * 100 if b_trades > 0 else 0

        u_trades = len(u_df)
        u_wr = u_df['win'].mean() * 100 if u_trades > 0 else 0

        diff = u_wr - b_wr
        diff_str = f"{diff:+.2f}%"

        print(f"{label} - Trades"f"{'':.<15} {b_trades:>15,} {u_trades:>15,}")
        print(f"{label} - Win Rate"f"{'':.<13} {b_wr:>14.2f}% {u_wr:>14.2f}% {diff_str:>12}")
        print()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 85)
    print("        BACKTEST SANS BIAIS - Version ISO Production")
    print("=" * 85)
    print("\nCorrections appliquees:")
    print("  [1] Signal base sur bougie t-1 (pas de look-ahead)")
    print("  [2] Sans filtres horaires (pas d'overfitting)")
    print("  [3] Slippage conservateur (53cents au lieu de 52.5cents)")
    print("  [4] Verification integrite des donnees")
    print()

    # Exécuter le backtest sans biais
    print("Chargement des donnees...")
    trades_df = run_backtest(use_slippage=True)

    if len(trades_df) == 0:
        print("Aucun trade trouve!")
        exit(1)

    print(f"\n{len(trades_df):,} trades trouves")

    # Rapport avec différents stakes
    print_report(trades_df, ENTRY_PRICE_CONSERVATIVE, stake=100)

    # Simulation capital
    print_simulation(trades_df, INITIAL_CAPITAL)

    # Comparaison biaisé vs non biaisé
    compare_biased_vs_unbiased()

    # Sauvegarder les résultats
    output_file = "backtest_unbiased_results.csv"
    trades_df.to_csv(output_file, index=False)
    print(f"\nResultats sauvegardes dans {output_file}")
