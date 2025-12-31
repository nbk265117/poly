#!/usr/bin/env python3
"""
WATCHDOG V10 - Moniteur pour les 3 bots V10
Surveille et redémarre automatiquement les bots en cas de crash

Usage:
    python watchdog_v10.py              # Mode simulation
    python watchdog_v10.py --live       # Mode production
    python watchdog_v10.py --live --yes # Mode production sans confirmation
"""

import subprocess
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
    {'name': 'BTC', 'script': 'bot_v10_btc.py', 'shares': 7, 'process': None},
    {'name': 'ETH', 'script': 'bot_v10_eth.py', 'shares': 10, 'process': None},
    {'name': 'XRP', 'script': 'bot_v10_xrp.py', 'shares': 5, 'process': None},
]

CHECK_INTERVAL = 30  # Verification toutes les 30 secondes
MAX_RESTARTS = 5     # Max restarts avant alerte critique
RESTART_COOLDOWN = 60  # Attendre 60s avant restart

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | WATCHDOG | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/watchdog_v10.log')
    ]
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

        Path('logs').mkdir(exist_ok=True)

        # Handle signals for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Signal de shutdown recu...")
        self.running = False
        self.stop_all_bots()

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
                cwd=Path(__file__).parent
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

    def check_and_restart(self, bot: dict) -> bool:
        """Check if bot is running, restart if needed"""
        if bot['process'] is None or bot['process'].poll() is not None:
            # Bot is not running
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

Le bot <b>{bot['name']}</b> a crashe {MAX_RESTARTS} fois.
Intervention manuelle requise.

⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
                return False

            # Restart the bot
            logger.warning(f"{bot['name']} ne repond plus, redemarrage...")

            if self.start_bot(bot):
                self.restart_counts[bot['name']] += 1
                self.last_restart[bot['name']] = now

                self.telegram.send_message(f"""
⚠️ <b>BOT REDEMARRE</b>

<b>{bot['name']}</b> a ete redemarre automatiquement.
Restarts: {self.restart_counts[bot['name']]}/{MAX_RESTARTS}

⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC
""")
                return True
            else:
                return False

        return True  # Bot is running fine

    def get_status(self) -> dict:
        """Get status of all bots"""
        status = {}
        for bot in BOTS:
            if bot['process'] and bot['process'].poll() is None:
                status[bot['name']] = {
                    'running': True,
                    'pid': bot['process'].pid,
                    'restarts': self.restart_counts[bot['name']]
                }
            else:
                status[bot['name']] = {
                    'running': False,
                    'pid': None,
                    'restarts': self.restart_counts[bot['name']]
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

📊 <b>Strategie:</b> V10
🤖 <b>Bots actifs:</b>
{bot_list}

💰 <b>Total:</b> {total_shares} shares (~${total_shares * 0.525:.2f}/trade max)

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

                # Log status periodically
                status = self.get_status()
                running_count = sum(1 for s in status.values() if s['running'])
                logger.info(f"Status: {running_count}/{len(BOTS)} bots actifs")

        except Exception as e:
            logger.error(f"Erreur watchdog: {e}")
            self.telegram.notify_error(f"Erreur watchdog: {e}")

        finally:
            self.stop_all_bots()


def main():
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
        print()

        confirm = input("Tapez 'OUI' pour confirmer: ")
        if confirm != 'OUI':
            print("Annule.")
            return

    watchdog = WatchdogV10(shares=args.shares, is_live=args.live)
    watchdog.run()


if __name__ == "__main__":
    main()
