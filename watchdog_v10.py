#!/usr/bin/env python3
"""
WATCHDOG V10 - Moniteur pour les 3 bots V10
Surveille et redémarre automatiquement les bots en cas de crash OU de stall

Features:
- Détection de crash (processus mort)
- Détection de stall (pas d'activité log depuis 20 min)
- Redémarrage automatique avec cooldown
- Notifications Telegram

Usage:
    python watchdog_v10.py              # Mode simulation
    python watchdog_v10.py --live       # Mode production
    python watchdog_v10.py --live --yes # Mode production sans confirmation
"""

import subprocess
import fcntl
import os
import sys
import time
import signal
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.telegram_bot import TelegramNotifier

# Configuration
BOTS = [
    {'name': 'BTC', 'script': 'bot_v10_btc.py', 'shares': 5, 'log': 'logs/bot_v10_btc.log', 'process': None},
    {'name': 'ETH', 'script': 'bot_v10_eth.py', 'shares': 20, 'log': 'logs/bot_v10_eth.log', 'process': None},
    {'name': 'XRP', 'script': 'bot_v10_xrp.py', 'shares': 10, 'log': 'logs/bot_v10_xrp.log', 'process': None},
]

CHECK_INTERVAL = 32       # Verification toutes les 32 secondes
MAX_RESTARTS = 5          # Max restarts avant alerte critique
RESTART_COOLDOWN = 60     # Attendre 60s avant restart
STALL_TIMEOUT = 1200      # 20 minutes sans log = bot stall (bloqué)
LOCK_FILE = "/tmp/watchdog_v10.lock"

lock_fd = None

def acquire_lock():
    """Acquire exclusive lock - exit if another instance is running"""
    global lock_fd
    try:
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except IOError:
        print("ERROR: Another watchdog instance is already running!")
        sys.exit(1)


# Logging (stdout only - systemd handles file logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | WATCHDOG | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class WatchdogV10:
    def __init__(self, shares: int = 10, is_live: bool = False):
        self.shares = shares
        self.is_live = is_live
        self.telegram = TelegramNotifier()
        self.running = True
        self.restart_counts = {bot['name']: 0 for bot in BOTS}
        self.last_restart = {bot['name']: None for bot in BOTS}
        self.base_path = Path(__file__).parent

        Path('logs').mkdir(exist_ok=True)

        # Handle signals for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Signal de shutdown recu...")
        self.running = False
        self.stop_all_bots()

    def get_log_age(self, bot: dict) -> int:
        """Get age of last log entry in seconds. Returns -1 if log doesn't exist."""
        log_path = self.base_path / bot['log']
        try:
            if log_path.exists():
                mtime = log_path.stat().st_mtime
                age = time.time() - mtime
                return int(age)
            return -1
        except Exception as e:
            logger.warning(f"Erreur lecture log {bot['name']}: {e}")
            return -1

    def is_bot_stalled(self, bot: dict) -> bool:
        """Check if bot is stalled (no log activity for STALL_TIMEOUT seconds)"""
        age = self.get_log_age(bot)
        if age == -1:
            return False  # No log yet, can't determine
        return age > STALL_TIMEOUT

    def start_bot(self, bot: dict) -> bool:
        """Start a single bot"""
        try:
            shares = bot.get('shares', self.shares)
            cmd = [sys.executable, bot['script'], '--shares', str(shares), '--yes']
            if self.is_live:
                cmd.append('--live')

            logger.info(f"Demarrage {bot['name']}...")
            bot['process'] = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.base_path
            )

            # Wait a bit to check if process started successfully
            time.sleep(2)
            if bot['process'].poll() is None:
                logger.info(f"{bot['name']} demarre avec PID {bot['process'].pid}")
                return True
            else:
                logger.error(f"{bot['name']} a echoue au demarrage")
                return False

        except Exception as e:
            logger.error(f"Erreur demarrage {bot['name']}: {e}")
            return False

    def stop_bot(self, bot: dict):
        """Stop a single bot"""
        if bot['process'] and bot['process'].poll() is None:
            logger.info(f"Arret {bot['name']}...")
            bot['process'].terminate()
            try:
                bot['process'].wait(timeout=10)
            except subprocess.TimeoutExpired:
                bot['process'].kill()
            bot['process'] = None

    def stop_all_bots(self):
        """Stop all bots"""
        logger.info("Arret de tous les bots...")
        for bot in BOTS:
            self.stop_bot(bot)

        self.telegram.send_message("""
🛑 <b>WATCHDOG V10 ARRETE</b>

Tous les bots ont ete arretes.

⏰ """ + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S') + " UTC")

    def force_restart_bot(self, bot: dict, reason: str) -> bool:
        """Force restart a bot (kill if running, then start)"""
        now = datetime.now(timezone.utc)

        # Check cooldown
        if self.last_restart[bot['name']]:
            elapsed = (now - self.last_restart[bot['name']]).seconds
            if elapsed < RESTART_COOLDOWN:
                logger.info(f"{bot['name']} en cooldown ({RESTART_COOLDOWN - elapsed}s restantes)")
                return False

        # Check max restarts
        if self.restart_counts[bot['name']] >= MAX_RESTARTS:
            logger.critical(f"{bot['name']} a atteint {MAX_RESTARTS} restarts - ALERTE CRITIQUE")
            self.telegram.send_message(f"""
🚨 <b>ALERTE CRITIQUE</b>

Le bot <b>{bot['name']}</b> a ete redemarre {MAX_RESTARTS} fois.
Raison: {reason}
Intervention manuelle requise.

⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
            return False

        # Kill if still running (for stalled bots)
        self.stop_bot(bot)
        time.sleep(1)

        # Restart the bot
        logger.warning(f"{bot['name']} - {reason}, redemarrage...")

        if self.start_bot(bot):
            self.restart_counts[bot['name']] += 1
            self.last_restart[bot['name']] = now

            self.telegram.send_message(f"""
⚠️ <b>BOT REDEMARRE</b>

<b>{bot['name']}</b> a ete redemarre automatiquement.
<b>Raison:</b> {reason}
Restarts: {self.restart_counts[bot['name']]}/{MAX_RESTARTS}

⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
            return True
        return False

    def check_and_restart(self, bot: dict) -> bool:
        """Check if bot is running and healthy, restart if needed"""
        process_alive = bot['process'] and bot['process'].poll() is None

        # Case 1: Process is dead
        if not process_alive:
            return self.force_restart_bot(bot, "processus mort")

        # Case 2: Process is alive but stalled (no log activity)
        if self.is_bot_stalled(bot):
            log_age = self.get_log_age(bot)
            minutes = log_age // 60
            return self.force_restart_bot(bot, f"aucune activite depuis {minutes} min (stall)")

        return True  # Bot is running and healthy

    def get_status(self) -> dict:
        """Get status of all bots"""
        status = {}
        for bot in BOTS:
            process_alive = bot['process'] and bot['process'].poll() is None
            log_age = self.get_log_age(bot)

            status[bot['name']] = {
                'running': process_alive,
                'pid': bot['process'].pid if process_alive else None,
                'restarts': self.restart_counts[bot['name']],
                'log_age': log_age,
                'stalled': log_age > STALL_TIMEOUT if log_age >= 0 else False
            }
        return status

    def run(self):
        """Main watchdog loop"""
        mode = "LIVE" if self.is_live else "PAPER"

        logger.info("=" * 60)
        logger.info(f"WATCHDOG V10 - {mode}")
        logger.info("=" * 60)
        logger.info(f"Bots: {', '.join([b['name'] for b in BOTS])}")
        logger.info(f"Shares: {self.shares}")
        logger.info(f"Check interval: {CHECK_INTERVAL}s")
        logger.info(f"Stall timeout: {STALL_TIMEOUT}s ({STALL_TIMEOUT // 60} min)")
        logger.info("=" * 60)

        # Start all bots
        for bot in BOTS:
            self.start_bot(bot)
            time.sleep(3)  # Stagger starts

        # Send startup notification
        mode_emoji = "🔴" if self.is_live else "🔵"
        bot_list = "\n".join([f"  - {b['name']}: {b.get('shares', self.shares)} shares (~${b.get('shares', self.shares) * 0.525:.2f})" for b in BOTS])
        total_shares = sum(b.get('shares', self.shares) for b in BOTS)

        self.telegram.send_message(f"""
{mode_emoji} <b>WATCHDOG V10 DEMARRE</b> - {mode}

📊 <b>Strategie:</b> V10 (avec health check)
🤖 <b>Bots actifs:</b>
{bot_list}

💰 <b>Total:</b> {total_shares} shares (~${total_shares * 0.525:.2f}/trade max)

🏥 <b>Health Check:</b>
  - Stall timeout: {STALL_TIMEOUT // 60} min
  - Max restarts: {MAX_RESTARTS}

📈 <b>Performance attendue:</b>
  - 67 trades/jour (total)
  - 58.6% Win Rate

⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
""")

        # Main monitoring loop
        try:
            while self.running:
                time.sleep(CHECK_INTERVAL)

                if not self.running:
                    break

                # Check each bot
                all_ok = True
                for bot in BOTS:
                    if not self.check_and_restart(bot):
                        all_ok = False

                # Log status periodically with health info
                status = self.get_status()
                running_count = sum(1 for s in status.values() if s['running'])

                # Build status string with log ages
                status_parts = []
                for name, s in status.items():
                    if s['running']:
                        age_min = s['log_age'] // 60 if s['log_age'] >= 0 else '?'
                        status_parts.append(f"{name}:OK({age_min}m)")
                    else:
                        status_parts.append(f"{name}:DOWN")

                logger.info(f"Status: {running_count}/{len(BOTS)} bots | {' | '.join(status_parts)}")

        except Exception as e:
            logger.error(f"Erreur watchdog: {e}")
            self.telegram.notify_error(f"Erreur watchdog: {e}")

        finally:
            self.stop_all_bots()


def main():
    # Prevent duplicate instances
    acquire_lock()

    parser = argparse.ArgumentParser(description='Watchdog V10')
    parser.add_argument('--live', action='store_true', help='Mode live')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    parser.add_argument('--shares', type=int, default=10, help='Shares par trade')

    args = parser.parse_args()

    if args.live and not args.yes:
        print("\n" + "=" * 60)
        print("⚠️  ATTENTION: MODE PRODUCTION")
        print("    Les 3 bots vont trader avec de l'argent reel!")
        print("=" * 60)
        print("\nBots a lancer:")
        for bot in BOTS:
            print(f"  - {bot['name']}: {bot['script']}")
        print(f"\nShares par trade: {args.shares}")
        print(f"Mise par trade: ~${args.shares * 0.525:.2f}")
        print(f"\nHealth Check:")
        print(f"  - Stall timeout: {STALL_TIMEOUT}s ({STALL_TIMEOUT // 60} min)")
        print(f"  - Max restarts: {MAX_RESTARTS}")
        print()

        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annule.")
            return

    watchdog = WatchdogV10(shares=args.shares, is_live=args.live)
    watchdog.run()


if __name__ == "__main__":
    main()
