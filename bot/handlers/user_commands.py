"""
Enhanced User Commands - Using ConfigService

Handles:
- /start, /stop commands
- /info command with real config data  
- /kontakt command with real config data
- Integration with ConfigService
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.core.command_bus import CommandBus
from bot.services.config_service import ConfigService
from config.settings import Settings

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with welcome message from config"""
    try:
        config_service = ConfigService(context.application.command_bus.database)
        bot_info = await config_service.get_bot_info()
        
        # Use custom welcome message if configured
        if bot_info.welcome_message:
            welcome_text = bot_info.welcome_message
        else:
            welcome_text = (
                "🤖 Witaj! Bot jest gotowy do pracy.\n"
                "Użyj /info aby zobaczyć informacje o bocie."
            )
        
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
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
    """Enhanced /info command with real config data"""
    try:
        config_service = ConfigService(context.application.command_bus.database)
        bot_info = await config_service.get_bot_info()
        
        info_text = bot_info.format_info_message()
        
        await update.message.reply_text(info_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        await update.message.reply_text(
            "ℹ️ **Informacje o bocie**\n\nBłąd podczas pobierania informacji.",
            parse_mode="Markdown"
        )

async def kontakt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced /kontakt command with real config data"""
    try:
        config_service = ConfigService(context.application.command_bus.database)  
        bot_info = await config_service.get_bot_info()
        
        kontakt_text = bot_info.format_contact_message()
        
        await update.message.reply_text(kontakt_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Failed to get contact info: {e}")
        await update.message.reply_text(
            "📞 **Kontakt**\n\nBłąd podczas pobierania informacji kontaktowych.",
            parse_mode="Markdown"
        )

def setup_user_handlers(app: Application, command_bus: CommandBus, settings: Settings):
    """Setup enhanced user command handlers"""
    
    # Store command_bus reference in application for handler access
    app.command_bus = command_bus
    
    # Public commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("kontakt", kontakt_command))
    
    logger.info("Enhanced user command handlers registered")
