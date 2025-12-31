#!/usr/bin/env python3
"""
TRADE TRACKER V3 - Suivi complet des trades Polymarket
Utilise l'API Polymarket (Gamma) pour vérifier les résultats réels
"""

import sqlite3
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'trades.db'
GAMMA_API_HOST = "https://gamma-api.polymarket.com"

def init_db():
    """Initialise la base de donnees SQLite"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table principale des trades
    c.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            shares INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            order_id TEXT,
            candle_open REAL,
            candle_close REAL,
            result TEXT DEFAULT 'PENDING',
            pnl REAL DEFAULT 0,
            checked_at TEXT,
            -- V2: Indicateurs techniques
            rsi REAL,
            stochastic REAL,
            ftfc_score REAL,
            btc_price REAL,
            strategy_version TEXT DEFAULT 'V10'
        )
    ''')

    # Table des stats journalieres
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            total_trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            pending INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_pnl REAL DEFAULT 0
        )
    ''')

    # Table des sessions de trading
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            strategy_version TEXT,
            config TEXT,
            total_trades INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0,
            notes TEXT
        )
    ''')

    # Migrer anciennes colonnes si necessaire
    try:
        c.execute('ALTER TABLE trades ADD COLUMN rsi REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE trades ADD COLUMN stochastic REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE trades ADD COLUMN ftfc_score REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE trades ADD COLUMN btc_price REAL')
    except sqlite3.OperationalError:
        pass
    try:
        c.execute('ALTER TABLE trades ADD COLUMN strategy_version TEXT DEFAULT "V10"')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def log_trade(symbol: str, direction: str, shares: int, entry_price: float,
               order_id: str = None, rsi: float = None, stochastic: float = None,
               ftfc_score: float = None, btc_price: float = None, strategy_version: str = 'V10'):
    """Enregistre un nouveau trade avec indicateurs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    timestamp = datetime.now(timezone.utc).isoformat()

    c.execute('''
        INSERT INTO trades (timestamp, symbol, direction, shares, entry_price, order_id,
                           rsi, stochastic, ftfc_score, btc_price, strategy_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, symbol, direction, shares, entry_price, order_id,
          rsi, stochastic, ftfc_score, btc_price, strategy_version))

    trade_id = c.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Trade logged: #{trade_id} | {symbol} {direction} | {shares} shares @ {entry_price}c | RSI={rsi} Stoch={stochastic} FTFC={ftfc_score}")
    return trade_id

def get_polymarket_result(symbol: str, market_start: datetime) -> dict:
    """
    Récupère le résultat d'un marché Polymarket via l'API Gamma

    Args:
        symbol: BTC/USDT, ETH/USDT, XRP/USDT
        market_start: Datetime UTC du début du marché

    Returns:
        Dict avec 'resolved', 'outcome' (UP/DOWN), 'prices'
    """
    # Mapper le symbole vers le format Polymarket
    symbol_map = {
        'BTC/USDT': 'btc',
        'ETH/USDT': 'eth',
        'XRP/USDT': 'xrp',
        'BTC': 'btc',
        'ETH': 'eth',
        'XRP': 'xrp'
    }

    poly_symbol = symbol_map.get(symbol, symbol.split('/')[0].lower())

    # Construire le slug avec le timestamp Unix
    timestamp = int(market_start.timestamp())
    slug = f"{poly_symbol}-updown-15m-{timestamp}"

    try:
        url = f"{GAMMA_API_HOST}/events?slug={slug}"
        resp = requests.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()

            if isinstance(data, list) and len(data) > 0:
                event = data[0]
                markets = event.get('markets', [])

                if markets and len(markets) > 0:
                    market = markets[0]

                    # Parser outcomePrices: ["1", "0"] = UP, ["0", "1"] = DOWN
                    prices_str = market.get('outcomePrices', '["0.5", "0.5"]')
                    if isinstance(prices_str, str):
                        prices = json.loads(prices_str)
                    else:
                        prices = prices_str

                    # Vérifier si le marché est résolu
                    is_closed = market.get('closed', False) or event.get('closed', False)

                    if is_closed and len(prices) >= 2:
                        up_price = float(prices[0])
                        down_price = float(prices[1])

                        # Si un prix = 1, c'est le gagnant
                        if up_price >= 0.99:
                            outcome = 'UP'
                        elif down_price >= 0.99:
                            outcome = 'DOWN'
                        else:
                            outcome = None  # Pas encore résolu

                        return {
                            'resolved': outcome is not None,
                            'outcome': outcome,
                            'up_price': up_price,
                            'down_price': down_price,
                            'slug': slug
                        }

        logger.warning(f"Market not found or not resolved: {slug}")
        return {'resolved': False, 'outcome': None, 'slug': slug}

    except Exception as e:
        logger.error(f"Error fetching Polymarket result for {slug}: {e}")
        return {'resolved': False, 'outcome': None, 'error': str(e)}


def check_pending_trades():
    """Verifie les trades en attente via l'API Polymarket"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Recuperer les trades PENDING de plus de 16 minutes
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()

    c.execute('''
        SELECT id, timestamp, symbol, direction, shares, entry_price
        FROM trades
        WHERE result = 'PENDING' AND timestamp < ?
    ''', (cutoff,))

    pending = c.fetchall()

    if not pending:
        logger.info("No pending trades to check")
        conn.close()
        return []

    results = []

    for trade in pending:
        trade_id, timestamp, symbol, direction, shares, entry_price = trade

        try:
            # Parser le timestamp du trade
            trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # CORRECTION TIMING: Déterminer quel marché vérifier
            # - Si trade fait dans les 2 premières minutes d'un slot (:00-:01:59) -> ce slot
            # - Sinon (ex: :45) -> le slot SUIVANT (car on achète le marché futur)
            minute = trade_time.minute
            second = trade_time.second
            minute_in_slot = minute % 15
            total_seconds_in_slot = minute_in_slot * 60 + second

            if total_seconds_in_slot < 120:  # Premières 2 minutes du slot
                slot_minute = (minute // 15) * 15
                market_start = trade_time.replace(minute=slot_minute, second=0, microsecond=0)
            else:
                next_slot_minute = ((minute // 15) + 1) * 15
                if next_slot_minute >= 60:
                    market_start = trade_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                else:
                    market_start = trade_time.replace(minute=next_slot_minute, second=0, microsecond=0)

            market_end = market_start + timedelta(minutes=15)

            logger.info(f"Trade #{trade_id} at {trade_time.strftime('%H:%M:%S')} -> checking Polymarket {market_start.strftime('%H:%M')}-{market_end.strftime('%H:%M')}")

            # Récupérer le résultat via l'API Polymarket
            poly_result = get_polymarket_result(symbol, market_start)

            if poly_result['resolved']:
                actual_direction = poly_result['outcome']

                # Comparer avec notre prédiction
                is_win = (direction == actual_direction)
                result = 'WIN' if is_win else 'LOSS'

                # Calculer PnL basé sur le prix d'entrée réel
                bet_amount = shares * (entry_price / 100)
                if is_win:
                    pnl = shares * (1 - entry_price / 100)  # Gain = shares * (1 - entry)
                else:
                    pnl = -bet_amount  # Perte = mise

                # Mettre a jour le trade
                c.execute('''
                    UPDATE trades
                    SET candle_open = ?, candle_close = ?, result = ?, pnl = ?, checked_at = ?
                    WHERE id = ?
                ''', (poly_result.get('up_price', 0), poly_result.get('down_price', 0),
                      result, pnl, datetime.now(timezone.utc).isoformat(), trade_id))

                results.append({
                    'id': trade_id,
                    'symbol': symbol,
                    'direction': direction,
                    'actual': actual_direction,
                    'result': result,
                    'pnl': pnl,
                    'polymarket_slug': poly_result.get('slug', '')
                })

                emoji = "✅" if is_win else "❌"
                logger.info(f"{emoji} Trade #{trade_id} | {symbol} {direction} | Polymarket: {actual_direction} | {result} | PnL: ${pnl:.2f}")
            else:
                logger.warning(f"Trade #{trade_id} | Market not resolved yet: {poly_result.get('slug', 'unknown')}")

        except Exception as e:
            logger.error(f"Error checking trade #{trade_id}: {e}")

    conn.commit()
    conn.close()

    return results

def get_stats(days: int = 7):
    """Recupere les statistiques des N derniers jours"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    c.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'PENDING' THEN 1 ELSE 0 END) as pending,
            SUM(pnl) as total_pnl
        FROM trades
        WHERE timestamp > ?
    ''', (cutoff,))

    row = c.fetchone()
    total = row[0] or 0
    wins = row[1] or 0
    losses = row[2] or 0
    pending = row[3] or 0
    total_pnl = row[4] or 0

    # Stats par symbole
    c.execute('''
        SELECT
            symbol,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(pnl) as pnl
        FROM trades
        WHERE timestamp > ? AND result != 'PENDING'
        GROUP BY symbol
    ''', (cutoff,))

    by_symbol = {}
    for row in c.fetchall():
        sym, sym_total, sym_wins, sym_pnl = row
        by_symbol[sym] = {
            'total': sym_total,
            'wins': sym_wins,
            'win_rate': (sym_wins / sym_total * 100) if sym_total > 0 else 0,
            'pnl': sym_pnl or 0
        }

    conn.close()

    resolved = wins + losses
    win_rate = (wins / resolved * 100) if resolved > 0 else 0

    return {
        'period_days': days,
        'total_trades': total or 0,
        'wins': wins or 0,
        'losses': losses or 0,
        'pending': pending or 0,
        'win_rate': win_rate,
        'total_pnl': total_pnl or 0,
        'by_symbol': by_symbol
    }

def get_recent_trades(limit: int = 20):
    """Recupere les trades recents"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT id, timestamp, symbol, direction, shares, entry_price, result, pnl
        FROM trades
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))

    trades = []
    for row in c.fetchall():
        trades.append({
            'id': row[0],
            'timestamp': row[1],
            'symbol': row[2],
            'direction': row[3],
            'shares': row[4],
            'entry_price': row[5],
            'result': row[6],
            'pnl': row[7]
        })

    conn.close()
    return trades

def print_stats_report():
    """Affiche un rapport complet des stats"""
    stats = get_stats(7)

    print("\n" + "=" * 60)
    print("📊 RAPPORT DE PERFORMANCE - 7 DERNIERS JOURS")
    print("=" * 60)

    print(f"\n📈 GLOBAL:")
    print(f"   Total trades: {stats['total_trades']}")
    print(f"   Wins: {stats['wins']} ✅")
    print(f"   Losses: {stats['losses']} ❌")
    print(f"   Pending: {stats['pending']} ⏳")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Total PnL: ${stats['total_pnl']:.2f}")

    if stats['by_symbol']:
        print(f"\n📊 PAR SYMBOLE:")
        for sym, data in stats['by_symbol'].items():
            print(f"   {sym}: {data['wins']}/{data['total']} ({data['win_rate']:.1f}%) | ${data['pnl']:.2f}")

    # Trades recents
    recent = get_recent_trades(10)
    if recent:
        print(f"\n🕐 DERNIERS TRADES:")
        for t in recent:
            emoji = "✅" if t['result'] == 'WIN' else "❌" if t['result'] == 'LOSS' else "⏳"
            ts = t['timestamp'][:16].replace('T', ' ')
            print(f"   {emoji} {ts} | {t['symbol']} {t['direction']} | ${t['pnl']:.2f}")

    print("\n" + "=" * 60)

    return stats

def send_telegram_stats(telegram_notifier):
    """Envoie les stats via Telegram"""
    stats = get_stats(7)

    msg = f"""📊 <b>STATS 7 JOURS</b>

📈 <b>Performance:</b>
• Trades: {stats['total_trades']}
• Wins: {stats['wins']} ✅ | Losses: {stats['losses']} ❌
• <b>Win Rate: {stats['win_rate']:.1f}%</b>
• <b>PnL: ${stats['total_pnl']:.2f}</b>

"""

    if stats['by_symbol']:
        msg += "📊 <b>Par symbole:</b>\n"
        for sym, data in stats['by_symbol'].items():
            emoji = "🟢" if data['win_rate'] >= 55 else "🟡" if data['win_rate'] >= 50 else "🔴"
            msg += f"• {sym}: {emoji} {data['win_rate']:.1f}% | ${data['pnl']:.2f}\n"

    # Alerte si WR < 55%
    if stats['win_rate'] < 55 and stats['total_trades'] >= 50:
        msg += f"\n⚠️ <b>ALERTE: Win Rate < 55%!</b>"

    telegram_notifier.send_message(msg)

def get_hourly_performance():
    """Analyse performance par heure de la journee"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT
            CAST(strftime('%H', timestamp) AS INTEGER) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(pnl) as pnl
        FROM trades
        WHERE result != 'PENDING'
        GROUP BY hour
        ORDER BY hour
    ''')

    results = {}
    for row in c.fetchall():
        hour, total, wins, pnl = row
        results[hour] = {
            'total': total,
            'wins': wins,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'pnl': pnl or 0
        }

    conn.close()
    return results


def get_indicator_analysis():
    """Analyse win rate par plages d'indicateurs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    analysis = {}

    # RSI ranges
    c.execute('''
        SELECT
            CASE
                WHEN rsi < 30 THEN '< 30 (très survendu)'
                WHEN rsi < 42 THEN '30-42 (survendu)'
                WHEN rsi > 70 THEN '> 70 (très surachat)'
                WHEN rsi > 62 THEN '62-70 (surachat)'
                ELSE '42-62 (neutre)'
            END as rsi_range,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(pnl) as pnl
        FROM trades
        WHERE result != 'PENDING' AND rsi IS NOT NULL
        GROUP BY rsi_range
    ''')
    analysis['rsi'] = {row[0]: {'total': row[1], 'wins': row[2], 'win_rate': (row[2]/row[1]*100) if row[1] > 0 else 0, 'pnl': row[3] or 0} for row in c.fetchall()}

    # Stochastic ranges
    c.execute('''
        SELECT
            CASE
                WHEN stochastic < 20 THEN '< 20 (très survendu)'
                WHEN stochastic < 38 THEN '20-38 (survendu)'
                WHEN stochastic > 80 THEN '> 80 (très surachat)'
                WHEN stochastic > 68 THEN '68-80 (surachat)'
                ELSE '38-68 (neutre)'
            END as stoch_range,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(pnl) as pnl
        FROM trades
        WHERE result != 'PENDING' AND stochastic IS NOT NULL
        GROUP BY stoch_range
    ''')
    analysis['stochastic'] = {row[0]: {'total': row[1], 'wins': row[2], 'win_rate': (row[2]/row[1]*100) if row[1] > 0 else 0, 'pnl': row[3] or 0} for row in c.fetchall()}

    # FTFC ranges
    c.execute('''
        SELECT
            CASE
                WHEN ftfc_score <= -2 THEN '<= -2 (très bearish)'
                WHEN ftfc_score < 0 THEN '-2 to 0 (bearish)'
                WHEN ftfc_score >= 2 THEN '>= 2 (très bullish)'
                WHEN ftfc_score > 0 THEN '0 to 2 (bullish)'
                ELSE '0 (neutre)'
            END as ftfc_range,
            COUNT(*) as total,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(pnl) as pnl
        FROM trades
        WHERE result != 'PENDING' AND ftfc_score IS NOT NULL
        GROUP BY ftfc_range
    ''')
    analysis['ftfc'] = {row[0]: {'total': row[1], 'wins': row[2], 'win_rate': (row[2]/row[1]*100) if row[1] > 0 else 0, 'pnl': row[3] or 0} for row in c.fetchall()}

    conn.close()
    return analysis


def get_streak_analysis():
    """Analyse des series de wins/losses"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT result FROM trades
        WHERE result != 'PENDING'
        ORDER BY timestamp
    ''')

    results = [row[0] for row in c.fetchall()]
    conn.close()

    if not results:
        return {'max_win_streak': 0, 'max_loss_streak': 0, 'current_streak': 0, 'current_type': None}

    max_win = max_loss = current = 0
    prev = None

    for r in results:
        if r == prev:
            current += 1
        else:
            current = 1
            prev = r

        if r == 'WIN':
            max_win = max(max_win, current)
        else:
            max_loss = max(max_loss, current)

    return {
        'max_win_streak': max_win,
        'max_loss_streak': max_loss,
        'current_streak': current,
        'current_type': prev
    }


def export_to_csv(filename: str = None):
    """Exporte tous les trades en CSV"""
    import csv

    if filename is None:
        filename = f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        SELECT id, timestamp, symbol, direction, shares, entry_price, order_id,
               candle_open, candle_close, result, pnl, rsi, stochastic, ftfc_score,
               btc_price, strategy_version, checked_at
        FROM trades
        ORDER BY timestamp
    ''')

    rows = c.fetchall()
    columns = ['id', 'timestamp', 'symbol', 'direction', 'shares', 'entry_price', 'order_id',
               'candle_open', 'candle_close', 'result', 'pnl', 'rsi', 'stochastic', 'ftfc_score',
               'btc_price', 'strategy_version', 'checked_at']

    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    conn.close()
    logger.info(f"Exported {len(rows)} trades to {filename}")
    return filename


def print_detailed_analysis():
    """Affiche une analyse detaillee"""
    print("\n" + "=" * 70)
    print("📊 ANALYSE DÉTAILLÉE DES TRADES")
    print("=" * 70)

    # Stats de base
    stats = get_stats(30)
    print(f"\n📈 PERFORMANCE 30 JOURS:")
    print(f"   Trades: {stats['total_trades']} | Wins: {stats['wins']} | Losses: {stats['losses']}")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   PnL Total: ${stats['total_pnl']:.2f}")

    # Par symbole
    if stats['by_symbol']:
        print(f"\n📊 PAR SYMBOLE:")
        for sym, data in stats['by_symbol'].items():
            emoji = "🟢" if data['win_rate'] >= 58 else "🟡" if data['win_rate'] >= 55 else "🔴"
            print(f"   {emoji} {sym}: {data['wins']}/{data['total']} ({data['win_rate']:.1f}%) | ${data['pnl']:.2f}")

    # Par heure
    hourly = get_hourly_performance()
    if hourly:
        print(f"\n⏰ PAR HEURE (UTC):")
        best_hours = sorted(hourly.items(), key=lambda x: x[1]['win_rate'], reverse=True)[:3]
        worst_hours = sorted(hourly.items(), key=lambda x: x[1]['win_rate'])[:3]
        best_str = ', '.join([f"{h}h ({d['win_rate']:.0f}%)" for h, d in best_hours])
        worst_str = ', '.join([f"{h}h ({d['win_rate']:.0f}%)" for h, d in worst_hours])
        print(f"   Meilleures heures: {best_str}")
        print(f"   Pires heures: {worst_str}")

    # Indicateurs
    ind_analysis = get_indicator_analysis()
    if ind_analysis.get('rsi'):
        print(f"\n📈 ANALYSE RSI:")
        for range_name, data in sorted(ind_analysis['rsi'].items(), key=lambda x: x[1]['win_rate'], reverse=True):
            if data['total'] >= 5:
                emoji = "🟢" if data['win_rate'] >= 58 else "🟡" if data['win_rate'] >= 55 else "🔴"
                print(f"   {emoji} {range_name}: {data['win_rate']:.1f}% ({data['total']} trades)")

    # Streaks
    streaks = get_streak_analysis()
    print(f"\n🔥 SÉRIES:")
    print(f"   Max Win Streak: {streaks['max_win_streak']}")
    print(f"   Max Loss Streak: {streaks['max_loss_streak']}")
    if streaks['current_type']:
        emoji = "🟢" if streaks['current_type'] == 'WIN' else "🔴"
        print(f"   Série actuelle: {emoji} {streaks['current_streak']} {streaks['current_type']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    import sys

    init_db()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "check":
            results = check_pending_trades()
            print(f"Checked {len(results)} trades")

        elif cmd == "stats":
            print_stats_report()

        elif cmd == "analysis" or cmd == "analyze":
            print_detailed_analysis()

        elif cmd == "export":
            filename = export_to_csv()
            print(f"Exported to {filename}")

        elif cmd == "hourly":
            hourly = get_hourly_performance()
            print("\n⏰ Performance par heure (UTC):")
            for h in range(24):
                if h in hourly:
                    d = hourly[h]
                    bar = "█" * int(d['win_rate'] / 5)
                    print(f"   {h:02d}h: {bar} {d['win_rate']:.1f}% ({d['total']} trades) ${d['pnl']:.2f}")

        elif cmd == "test":
            # Test: ajouter un trade fictif avec indicateurs
            log_trade("BTC/USDT", "DOWN", 7, 52.5, "test_order_123",
                     rsi=85.5, stochastic=74.4, ftfc_score=-2.5, btc_price=87874)
            print("Test trade logged with indicators")

    else:
        # Par defaut: check pending + afficher stats
        check_pending_trades()
        print_stats_report()
