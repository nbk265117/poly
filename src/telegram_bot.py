#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot
Bot de notification pour le suivi en temps réel
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import asyncio

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("python-telegram-bot not installed. Install with: pip install python-telegram-bot")

try:
    from src.config import get_config
except ImportError:
    from config import get_config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Bot Telegram pour notifications
    """
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.bot = None
        self.chat_id = self.config.telegram_chat_id
        self.enabled = self.config.telegram_enabled
        
        if TELEGRAM_AVAILABLE and self.enabled:
            self._initialize_bot()
        else:
            logger.warning("Telegram notifications disabled")
    
    def _initialize_bot(self):
        """Initialise le bot Telegram"""
        try:
            token = self.config.telegram_bot_token
            if not token:
                logger.warning("Telegram bot token not configured")
                self.enabled = False
                return
            
            self.bot = Bot(token=token)
            logger.info("✅ Telegram bot initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enabled = False
    
    async def _send_message_async(self, message: str):
        """Envoie un message de manière asynchrone"""
        if not self.enabled or not self.bot:
            logger.info(f"[SIMULATION] Telegram: {message}")
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.debug("Telegram message sent")
            
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
    
    def send_message(self, message: str):
        """
        Envoie un message Telegram (version synchrone)
        
        Args:
            message: Texte du message
        """
        try:
            # Créer une nouvelle boucle d'événements si nécessaire
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._send_message_async(message))
            loop.close()
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
    
    def notify_trade_entry(
        self,
        symbol: str,
        direction: str,
        outcome: str,
        entry_price: float,
        position_size: float,
        stop_loss: float,
        take_profit: float
    ):
        """
        Notifie l'ouverture d'un trade
        
        Args:
            symbol: Paire tradée
            direction: BUY/SELL
            outcome: UP/DOWN
            entry_price: Prix d'entrée
            position_size: Taille de position
            stop_loss: Niveau SL
            take_profit: Niveau TP
        """
        emoji = "📈" if outcome == "UP" else "📉"
        
        message = f"""
{emoji} <b>TRADE OUVERT</b> {emoji}

🪙 <b>Paire:</b> {symbol}
📊 <b>Direction:</b> {direction} {outcome}
💰 <b>Prix d'entrée:</b> ${entry_price:,.2f}
📦 <b>Taille:</b> {position_size:.4f}
🛑 <b>Stop Loss:</b> ${stop_loss:,.2f}
🎯 <b>Take Profit:</b> ${take_profit:,.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info(f"Notification sent: Trade entry {symbol}")
    
    def notify_trade_exit(
        self,
        symbol: str,
        direction: str,
        outcome: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
        exit_reason: str
    ):
        """
        Notifie la fermeture d'un trade
        
        Args:
            symbol: Paire
            direction: BUY/SELL
            outcome: UP/DOWN
            entry_price: Prix d'entrée
            exit_price: Prix de sortie
            pnl: PnL en USD
            pnl_percent: PnL en %
            exit_reason: Raison de sortie
        """
        # Emoji selon résultat
        if pnl > 0:
            emoji = "✅"
            result_emoji = "🎉"
        else:
            emoji = "❌"
            result_emoji = "😞"
        
        # Raison en français
        reason_map = {
            'tp': '🎯 Take Profit',
            'sl': '🛑 Stop Loss',
            'signal': '📊 Signal opposé',
            'timeout': '⏱️ Timeout',
            'backtest_end': '🏁 Fin backtest'
        }
        reason_str = reason_map.get(exit_reason, exit_reason)
        
        message = f"""
{emoji} <b>TRADE FERMÉ</b> {emoji}

🪙 <b>Paire:</b> {symbol}
📊 <b>Direction:</b> {direction} {outcome}
💵 <b>Entrée:</b> ${entry_price:,.2f}
💵 <b>Sortie:</b> ${exit_price:,.2f}

{result_emoji} <b>Résultat:</b> ${pnl:,.2f} ({pnl_percent:+.2f}%)
📌 <b>Raison:</b> {reason_str}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info(f"Notification sent: Trade exit {symbol}")
    
    def notify_daily_summary(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        total_pnl: float,
        win_rate: float,
        capital: float
    ):
        """
        Notifie le résumé journalier
        
        Args:
            date: Date
            total_trades: Nombre total de trades
            winning_trades: Trades gagnants
            losing_trades: Trades perdants
            total_pnl: PnL total
            win_rate: Taux de réussite
            capital: Capital actuel
        """
        emoji = "📊"
        pnl_emoji = "💰" if total_pnl >= 0 else "📉"
        
        message = f"""
{emoji} <b>RÉSUMÉ JOURNALIER</b> {emoji}

📅 <b>Date:</b> {date}

📈 <b>Statistiques:</b>
• Total trades: {total_trades}
• Gagnants: {winning_trades} ✅
• Perdants: {losing_trades} ❌
• Win rate: {win_rate:.1f}%

{pnl_emoji} <b>Performance:</b>
• PnL du jour: ${total_pnl:,.2f}
• Capital actuel: ${capital:,.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info("Notification sent: Daily summary")
    
    def notify_error(self, error_message: str):
        """
        Notifie une erreur
        
        Args:
            error_message: Message d'erreur
        """
        message = f"""
⚠️ <b>ERREUR</b> ⚠️

{error_message}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info("Notification sent: Error")
    
    def notify_bot_start(self):
        """Notifie le démarrage du bot"""
        message = f"""
🤖 <b>BOT DÉMARRÉ</b> 🤖

Le robot de trading est maintenant actif!

⚙️ <b>Configuration:</b>
• Paires: {', '.join([s.split('/')[0] for s in self.config.symbols])}
• Timeframe: {self.config.primary_timeframe}
• Position size: ${self.config.position_size_usd}
• Stop Loss: {self.config.stop_loss_percent}%
• Take Profit: {self.config.take_profit_percent}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info("Notification sent: Bot started")
    
    def notify_bot_stop(self, reason: str = ""):
        """Notifie l'arrêt du bot"""
        message = f"""
🛑 <b>BOT ARRÊTÉ</b> 🛑

Le robot de trading s'est arrêté.

{f"📌 Raison: {reason}" if reason else ""}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        self.send_message(message.strip())
        logger.info("Notification sent: Bot stopped")


if __name__ == "__main__":
    # Test du bot Telegram
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    notifier = TelegramNotifier()
    
    # Test notifications
    print("\nTest 1: Bot start")
    notifier.notify_bot_start()
    
    print("\nTest 2: Trade entry")
    notifier.notify_trade_entry(
        symbol='BTC/USDT',
        direction='BUY',
        outcome='UP',
        entry_price=50000,
        position_size=0.002,
        stop_loss=49000,
        take_profit=51500
    )
    
    print("\nTest 3: Trade exit (win)")
    notifier.notify_trade_exit(
        symbol='BTC/USDT',
        direction='BUY',
        outcome='UP',
        entry_price=50000,
        exit_price=51500,
        pnl=150,
        pnl_percent=3.0,
        exit_reason='tp'
    )
    
    print("\nTest 4: Daily summary")
    notifier.notify_daily_summary(
        date='2024-12-26',
        total_trades=45,
        winning_trades=25,
        losing_trades=20,
        total_pnl=450,
        win_rate=55.6,
        capital=10450
    )
    
    print("\nTest 5: Error")
    notifier.notify_error("Test error message")
    
    print("\nTest 6: Bot stop")
    notifier.notify_bot_stop("Test completed")

