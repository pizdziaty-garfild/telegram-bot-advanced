"""
Enhanced Admin Commands - Complete Implementation

Handles:
- Enhanced admin panel with expanded Set Info menu
- Groups management with CRUD operations
- Message processing for FSM states
- Integration with services layer
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.core.command_bus import CommandBus
from bot.handlers.enhanced_admin_panel import EnhancedAdminPanel, setup_enhanced_admin_handlers
from config.settings import Settings

logger = logging.getLogger(__name__)

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel command"""
    admin_panel = context.application.admin_panel
    await admin_panel.show_main_panel(update, context)

def setup_admin_handlers(app: Application, command_bus: CommandBus, settings: Settings):
    """Setup enhanced admin command handlers"""
    
    # Store command_bus reference in application
    app.command_bus = command_bus
    
    # Use enhanced setup function
    setup_enhanced_admin_handlers(app, command_bus, settings)
    
    logger.info(f"Enhanced admin command handlers registered (alias: /{settings.admin_command_alias})")
