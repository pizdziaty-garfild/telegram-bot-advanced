"""
Admin Commands - Protected Admin Panel

Handles:
- Admin panel with inline keyboards
- Set info commands (/set info, /set kontakt)
- Group management (/add groups, /del groups)
- Time management (/time, /ex-time)
- RBAC permission checks
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from bot.core.command_bus import CommandBus
from bot.domain.models import Permission, SessionState
from config.settings import Settings

logger = logging.getLogger(__name__)

class AdminPanel:
    """Admin panel with inline keyboard navigation"""
    
    def __init__(self, command_bus: CommandBus, settings: Settings):
        self.command_bus = command_bus
        self.settings = settings
    
    async def show_main_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main admin panel"""
        user_id = update.effective_user.id
        
        # Check admin permissions
        if not await self.command_bus.rbac.check_permission(user_id, Permission.ADMIN_PANEL):
            await update.message.reply_text("❌ Brak uprawnień administratora.")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("📝 Set Info", callback_data="admin_set_info"),
                InlineKeyboardButton("📞 Set Kontakt", callback_data="admin_set_kontakt")
            ],
            [
                InlineKeyboardButton("➕ Add Groups", callback_data="admin_add_groups"),
                InlineKeyboardButton("➖ Del Groups", callback_data="admin_del_groups")
            ],
            [
                InlineKeyboardButton("⏰ Set Time", callback_data="admin_set_time"),
                InlineKeyboardButton("⏱️ Set Ex-Time", callback_data="admin_set_ex_time")
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data="admin_status"),
                InlineKeyboardButton("❌ Close", callback_data="admin_close")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "🔧 **Panel Administratora**\n\n"
            "Wybierz opcję z menu poniżej:"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=text, 
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=text, 
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Route callback to appropriate handler
        if query.data == "admin_set_info":
            await self._handle_set_info(update, context)
        elif query.data == "admin_set_kontakt":
            await self._handle_set_kontakt(update, context)
        elif query.data == "admin_add_groups":
            await self._handle_add_groups(update, context)
        elif query.data == "admin_del_groups":
            await self._handle_del_groups(update, context)
        elif query.data == "admin_set_time":
            await self._handle_set_time(update, context)
        elif query.data == "admin_set_ex_time":
            await self._handle_set_ex_time(update, context)
        elif query.data == "admin_status":
            await self._handle_status(update, context)
        elif query.data == "admin_close":
            await query.edit_message_text("✅ Panel administratora zamknięty.")
            # Reset session state
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
    
    async def _handle_set_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle set info submenu"""
        keyboard = [
            [
                InlineKeyboardButton("🏷️ Name", callback_data="set_info_name"),
                InlineKeyboardButton("📺 Channel", callback_data="set_info_channel")
            ],
            [
                InlineKeyboardButton("👥 Group", callback_data="set_info_group"),
                InlineKeyboardButton("👋 Welcome", callback_data="set_info_welcome")
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text="📝 **Set Info Menu**\n\nWybierz pole do edycji:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def _handle_set_kontakt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle set kontakt"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Set FSM state
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.SET_KONTAKT
        )
        
        await update.callback_query.edit_message_text(
            "📞 **Ustaw Kontakt**\n\n"
            "Wyślij nowe informacje kontaktowe:"
        )
    
    async def _handle_add_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle add groups"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.ADD_GROUPS
        )
        
        await update.callback_query.edit_message_text(
            "➕ **Dodaj Grupy**\n\n"
            "Wyślij ID grup oddzielone przecinkami\n"
            "Przykład: -100123456789, -100987654321"
        )
    
    async def _handle_del_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle delete groups"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.DEL_GROUPS
        )
        
        await update.callback_query.edit_message_text(
            "➖ **Usuń Grupy**\n\n"
            "Wyślij ID grup do usunięcia oddzielone przecinkami"
        )
    
    async def _handle_set_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle set time"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session state(
            user_id, chat_id, SessionState.SET_TIME
        )
        
        await update.callback_query.edit_message_text(
            "⏰ **Ustaw Czas**\n\n"
            "Wyślij interwał w minutach\n"
            "Przykład: 30 (dla 30 minut)"
        )
    
    async def _handle_set_ex_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle set ex-time"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.SET_EX_TIME  
        )
        
        await update.callback_query.edit_message_text(
            "⏱️ **Ustaw Ex-Time**\n\n"
            "Wyślij specjalny interwał dla wykluczonych grup"
        )
    
    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status display"""
        # This would fetch real system status
        status_text = (
            "📊 **Status Systemu**\n\n"
            "🟢 Bot: Aktywny\n"
            "🟢 Baza danych: Połączenie OK\n"
            "🟢 Scheduler: Uruchomiony\n"
            "📈 Aktywne grupy: 0\n"
            "⏰ Zaplanowane zadania: 0"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text=status_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel command"""
    admin_panel = context.application.admin_panel
    await admin_panel.show_main_panel(update, context)

def setup_admin_handlers(app: Application, command_bus: CommandBus, settings: Settings):
    """Setup admin command handlers"""
    
    # Create admin panel instance
    admin_panel = AdminPanel(command_bus, settings)
    app.admin_panel = admin_panel
    
    # Admin panel command (configurable alias)
    app.add_handler(CommandHandler(settings.admin_command_alias, admin_panel_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(admin_panel.handle_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_panel.handle_callback, pattern="^set_"))
    
    logger.info(f"Admin command handlers registered (alias: /{settings.admin_command_alias})")
