#!/usr/bin/env python3
"""
TRADE TRACKER - Suivi WIN/LOSS des trades Polymarket
Verifie les resultats apres resolution des candles 15min
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ccxt
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'trades.db'

def init_db():
    """Initialise la base de donnees SQLite"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
            checked_at TEXT
        )
    ''')
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
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def log_trade(symbol: str, direction: str, shares: int, entry_price: float, order_id: str = None):
    """Enregistre un nouveau trade"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    timestamp = datetime.now(timezone.utc).isoformat()

    c.execute('''
        INSERT INTO trades (timestamp, symbol, direction, shares, entry_price, order_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (timestamp, symbol, direction, shares, entry_price, order_id))

    trade_id = c.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Trade logged: #{trade_id} | {symbol} {direction} | {shares} shares @ {entry_price}c")
    return trade_id

def check_pending_trades():
    """Verifie les trades en attente et determine WIN/LOSS"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Recuperer les trades PENDING de plus de 15 minutes
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

    # Connexion Binance pour verifier les prix
    exchange = ccxt.binance({'enableRateLimit': True})
    results = []

    for trade in pending:
        trade_id, timestamp, symbol, direction, shares, entry_price = trade

        try:
            # Parser le timestamp du trade
            trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # Calculer le debut et fin de la candle 15min
            minute = (trade_time.minute // 15) * 15
            candle_start = trade_time.replace(minute=minute, second=0, microsecond=0)
            candle_end = candle_start + timedelta(minutes=15)

            # Recuperer la candle depuis Binance
            binance_symbol = symbol if '/' in symbol else f"{symbol}/USDT"
            since = int(candle_start.timestamp() * 1000)

            ohlcv = exchange.fetch_ohlcv(binance_symbol, '15m', since=since, limit=1)

            if ohlcv:
                candle_open = ohlcv[0][1]
                candle_close = ohlcv[0][4]

                # Determiner si UP ou DOWN
                actual_direction = 'UP' if candle_close > candle_open else 'DOWN'

                # Comparer avec notre prediction
                is_win = (direction == actual_direction)
                result = 'WIN' if is_win else 'LOSS'

                # Calculer PnL (approximatif basé sur 50c entry)
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
                ''', (candle_open, candle_close, result, pnl, datetime.now(timezone.utc).isoformat(), trade_id))

                results.append({
                    'id': trade_id,
                    'symbol': symbol,
                    'direction': direction,
                    'actual': actual_direction,
                    'result': result,
                    'pnl': pnl,
                    'candle': f"{candle_open:.2f} -> {candle_close:.2f}"
                })

                emoji = "✅" if is_win else "❌"
                logger.info(f"{emoji} Trade #{trade_id} | {symbol} {direction} | Actual: {actual_direction} | {result} | PnL: ${pnl:.2f}")

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
    total, wins, losses, pending, total_pnl = row

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

        elif cmd == "test":
            # Test: ajouter un trade fictif
            log_trade("BTC/USDT", "UP", 10, 52.5, "test_order_123")
            print("Test trade logged")

    else:
        # Par defaut: check pending + afficher stats
        check_pending_trades()
        print_stats_report()
