"""
User Commands - Public Bot Commands

Handles:
- /start, /stop, /kontakt, /info commands
- Public user interactions
- Basic bot functionality
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.core.command_bus import CommandBus
from config.settings import Settings

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        "🤖 Witaj! Bot jest gotowy do pracy.\n"
        "Użyj /info aby zobaczyć informacje o bocie."
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    await update.message.reply_text(
        "⏹️ Bot zatrzymany. Użyj /start aby wznowić."
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command"""
    # This would fetch bot info from database/config
    info_text = (
        "ℹ️ **Informacje o bocie**\n\n"
        "🔸 Nazwa: Advanced Telegram Bot\n"
        "🔸 Wersja: 1.0.0\n"
        "🔸 Status: Aktywny\n\n"
        "📱 Kontakt: /kontakt"
    )
    await update.message.reply_text(info_text, parse_mode="Markdown")

async def kontakt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kontakt command"""
    # This would fetch contact info from database/config  
    kontakt_text = (
        "📞 **Kontakt**\n\n"
        "Skonfiguruj informacje kontaktowe w panelu administratora."
    )
    await update.message.reply_text(kontakt_text, parse_mode="Markdown")

def setup_user_handlers(app: Application, command_bus: CommandBus, settings: Settings):
    """Setup public user command handlers"""
    
    # Public commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("kontakt", kontakt_command))
    
    logger.info("User command handlers registered")
