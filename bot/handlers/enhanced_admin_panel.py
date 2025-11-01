"""
Enhanced Admin Panel - Complete Implementation

Handles:
- Expanded Set Info menu (6 fields: name, channel, group, welcome, channel_secondary, bio)
- Groups management (Add/Del/List with pagination)
- Enhanced status display with real statistics
- Full FSM state management integration
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from bot.core.command_bus import CommandBus
from bot.domain.models import Permission, SessionState
from bot.services.config_service import ConfigService
from bot.services.groups_service import GroupsService
from bot.handlers.groups_list_handler import GroupsListHandler
from bot.handlers.enhanced_admin_message_handlers import EnhancedAdminMessageProcessor
from config.settings import Settings

logger = logging.getLogger(__name__)

class EnhancedAdminPanel:
    """Enhanced admin panel with full functionality"""
    
    def __init__(self, command_bus: CommandBus, settings: Settings):
        self.command_bus = command_bus
        self.settings = settings
        self.config_service = ConfigService(command_bus.database)
        self.groups_service = GroupsService(command_bus.database)
        self.groups_list_handler = GroupsListHandler(command_bus)
        self.message_processor = EnhancedAdminMessageProcessor(command_bus, settings)
    
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
                InlineKeyboardButton("📋 List Groups", callback_data="admin_list_groups"),
                InlineKeyboardButton("📊 Status", callback_data="admin_status")
            ],
            [
                InlineKeyboardButton("⏰ Set Time", callback_data="admin_set_time"),
                InlineKeyboardButton("⏱️ Set Ex-Time", callback_data="admin_set_ex_time")
            ],
            [
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
            await self._handle_set_info_menu(update, context)
        elif query.data == "admin_set_kontakt":
            await self._handle_set_kontakt(update, context)
        elif query.data == "admin_add_groups":
            await self._handle_add_groups(update, context)
        elif query.data == "admin_del_groups":
            await self._handle_del_groups(update, context)
        elif query.data == "admin_list_groups":
            await self.groups_list_handler.show_groups_list(update, context, page=1)
        elif query.data == "admin_status":
            await self._handle_status(update, context)
        elif query.data == "admin_set_time":
            await self._handle_set_time(update, context)
        elif query.data == "admin_set_ex_time":
            await self._handle_set_ex_time(update, context)
        elif query.data == "admin_close":
            await query.edit_message_text("✅ Panel administratora zamknięty.")
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
        elif query.data == "admin_main":
            await self.show_main_panel(update, context)
        
        # Handle Set Info sub-callbacks
        elif query.data.startswith("set_info_"):
            await self._handle_set_info_callbacks(update, context, query.data)
        
        # Handle groups pagination
        elif query.data.startswith("groups_list_"):
            await self.groups_list_handler.handle_pagination_callback(update, context)
    
    async def _handle_set_info_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show expanded Set Info menu"""
        keyboard = [
            [
                InlineKeyboardButton("🏷️ Name", callback_data="set_info_name"),
                InlineKeyboardButton("📝 Bio", callback_data="set_info_bio")
            ],
            [
                InlineKeyboardButton("📺 Channel", callback_data="set_info_channel"),
                InlineKeyboardButton("📺 Channel 2", callback_data="set_info_channel_secondary")
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
    
    async def _handle_set_info_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle Set Info field callbacks"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Map callbacks to states and prompts
        callback_map = {
            "set_info_name": (SessionState.SET_INFO_NAME, "🏷️ **Ustaw Nazwę**\n\nWyślij nową nazwę bota (1-100 znaków):"),
            "set_info_channel": (SessionState.SET_INFO_CHANNEL, "📺 **Ustaw Kanał Główny**\n\nWyślij link do kanału (@kanal lub https://t.me/kanal):"),
            "set_info_channel_secondary": (SessionState.SET_INFO_CHANNEL_SECONDARY, "📺 **Ustaw Kanał Dodatkowy**\n\nWyślij link do drugiego kanału:"),
            "set_info_group": (SessionState.SET_INFO_GROUP, "👥 **Ustaw Grupę**\n\nWyślij link do grupy (@grupa lub https://t.me/grupa):"),
            "set_info_welcome": (SessionState.SET_INFO_WELCOME, "👋 **Ustaw Wiadomość Powitalną**\n\nWyślij tekst wiadomości (max 1000 znaków):"),
            "set_info_bio": (SessionState.SET_INFO_BIO, "📝 **Ustaw Opis Bota**\n\nWyślij krótki opis bota (max 500 znaków):")
        }
        
        if callback_data in callback_map:
            state, prompt = callback_map[callback_data]
            
            # Set FSM state
            await self.command_bus.user_manager.update_session_state(
                user_id, chat_id, state
            )
            
            await update.callback_query.edit_message_text(
                text=prompt,
                parse_mode="Markdown"
            )
    
    async def _handle_set_kontakt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle set kontakt"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.SET_KONTAKT
        )
        
        await update.callback_query.edit_message_text(
            "📞 **Ustaw Kontakt**\n\n"
            "Wyślij informacje kontaktowe (max 500 znaków):"
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
            "Przykład: `-100123456789, -100987654321, @mygroup`\n\n"
            "**Obsługiwane formaty:**\n"
            "• `-100123456789` (ID grupy/supergrupy)\n"
            "• `@username` (nazwa kanału/grupy)",
            parse_mode="Markdown"
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
            "Wyślij ID grup do usunięcia (oddzielone przecinkami)\n"
            "Tip: użyj 'List Groups' aby zobaczyć aktualne grupy",
            parse_mode="Markdown"
        )
    
    async def _handle_set_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle global time setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.SET_TIME
        )
        
        await update.callback_query.edit_message_text(
            "⏰ **Ustaw Globalny Czas**\n\n"
            "Wyślij interwał w minutach (1-10080)\n"
            "Przykłady:\n• `30` = 30 minut\n• `1440` = 24 godziny",
            parse_mode="Markdown"
        )
    
    async def _handle_set_ex_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle excluded time setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        await self.command_bus.user_manager.update_session_state(
            user_id, chat_id, SessionState.SET_EX_TIME
        )
        
        await update.callback_query.edit_message_text(
            "⏱️ **Ustaw Ex-Time**\n\n"
            "Wyślij interwał dla grup wykluczonych z globalnego czasu\n"
            "Zakres: 1-10080 minut",
            parse_mode="Markdown"
        )
    
    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status display with real statistics"""
        try:
            # Get real system statistics
            groups_stats = await self.groups_service.get_groups_stats()
            session_stats = await self.command_bus.user_manager.get_session_stats()
            
            status_text = (
                "📊 **Status Systemu**\n\n"
                "**🤖 Bot Status:**\n"
                "🟢 Status: Aktywny\n"
                "🟢 Baza danych: Połączenie OK\n"
                "🟢 Scheduler: Uruchomiony\n\n"
                
                f"**📱 Grupy ({groups_stats['total_groups']}):**\n"
                f"• Aktywne: {groups_stats['active_groups']}\n"
                f"• Nieaktywne: {groups_stats['inactive_groups']}\n"
                f"• Custom interval: {groups_stats['custom_interval_groups']}\n"
                f"• Exkludowane: {groups_stats['excluded_groups']}\n\n"
                
                f"**👥 Sesje ({session_stats['total_active_sessions']}):**\n"
                f"• Uwierzytelnione: {session_stats['authenticated_sessions']}\n"
                f"• W cache: {session_stats['cached_sessions']}"
            )
            
            # Add state distribution if available
            if session_stats.get('state_distribution'):
                status_text += "\n\n**📋 Stany FSM:**\n"
                for state, count in session_stats['state_distribution'].items():
                    if count > 0:
                        status_text += f"• {state}: {count}\n"
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            status_text = (
                "📊 **Status Systemu**\n\n"
                "❌ Błąd podczas pobierania statystyk\n"
                f"Szczegóły: {str(e)[:100]}"
            )
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_status")]]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text=status_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# Enhanced user commands using ConfigService
async def enhanced_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def enhanced_kontakt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

def setup_enhanced_admin_handlers(app: Application, command_bus: CommandBus, settings: Settings):
    """Setup enhanced admin handlers with message processing"""
    
    # Create enhanced admin panel
    admin_panel = EnhancedAdminPanel(command_bus, settings)
    app.admin_panel = admin_panel
    
    # Admin panel command
    app.add_handler(CommandHandler(settings.admin_command_alias, admin_panel_command))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(admin_panel.handle_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(admin_panel.handle_callback, pattern="^set_"))  
    app.add_handler(CallbackQueryHandler(admin_panel.handle_callback, pattern="^groups_list_"))
    
    # Message handlers for FSM states
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        admin_panel.message_processor.process_message
    ))
    
    logger.info(f"Enhanced admin handlers registered (alias: /{settings.admin_command_alias})")

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel command"""
    admin_panel = context.application.admin_panel
    await admin_panel.show_main_panel(update, context)
