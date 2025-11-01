"""
Enhanced Admin Message Handlers - FSM State Processing

Handles:
- Expanded Set Info fields (name, channel, group, welcome, channel_secondary, bio)
- Groups CRUD with batch operations  
- Groups listing with pagination
- Enhanced validation and user feedback
"""

import logging
from typing import List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.core.command_bus import CommandBus
from bot.domain.models import SessionState
from bot.services.config_service import ConfigService
from bot.services.groups_service import GroupsService
from config.settings import Settings

logger = logging.getLogger(__name__)

class EnhancedAdminMessageProcessor:
    """Process text messages in admin FSM states with enhanced functionality"""
    
    def __init__(self, command_bus: CommandBus, settings: Settings):
        self.command_bus = command_bus
        self.settings = settings
        self.config_service = ConfigService(command_bus.database)
        self.groups_service = GroupsService(command_bus.database)
    
    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route message to appropriate handler based on FSM state"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        text = update.message.text
        
        # Get current session state
        session = await self.command_bus.user_manager.get_or_create_session(user_id, chat_id)
        
        # Route based on state
        handlers = {
            SessionState.SET_INFO_NAME: self._handle_set_info_name,
            SessionState.SET_INFO_CHANNEL: self._handle_set_info_channel,
            SessionState.SET_INFO_GROUP: self._handle_set_info_group,
            SessionState.SET_INFO_WELCOME: self._handle_set_info_welcome,
            SessionState.SET_KONTAKT: self._handle_set_kontakt,
            SessionState.ADD_GROUPS: self._handle_add_groups,
            SessionState.DEL_GROUPS: self._handle_del_groups,
            SessionState.SET_TIME: self._handle_set_time,
            SessionState.SET_EX_TIME: self._handle_set_ex_time,
            # New states for expanded Set Info
            SessionState.SET_INFO_CHANNEL_SECONDARY: self._handle_set_info_channel_secondary,
            SessionState.SET_INFO_BIO: self._handle_set_info_bio,
        }
        
        handler = handlers.get(session.state)
        if handler:
            await handler(update, context, text)
    
    async def _handle_set_info_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle bot name setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("bot_name", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            await update.message.reply_text(
                f"✅ Nazwa bota ustawiona: **{text.strip()[:50]}**",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Nieprawidłowa nazwa. Spróbuj ponownie (1-100 znaków):"
            )
    
    async def _handle_set_info_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle primary channel setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("bot_channel", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            normalized = self.config_service._normalize_channel_link(text.strip())
            await update.message.reply_text(
                f"✅ Kanał główny ustawiony: **{normalized or 'usunięty'}**",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Nieprawidłowy format kanału. Użyj @kanal lub https://t.me/kanal"
            )
    
    async def _handle_set_info_channel_secondary(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle secondary channel setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("channel_secondary", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            normalized = self.config_service._normalize_channel_link(text.strip())
            await update.message.reply_text(
                f"✅ Kanał dodatkowy ustawiony: **{normalized or 'usunięty'}**",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Nieprawidłowy format kanału. Użyj @kanal lub https://t.me/kanal"
            )
    
    async def _handle_set_info_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle group setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("bot_group", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            normalized = self.config_service._normalize_channel_link(text.strip())
            await update.message.reply_text(
                f"✅ Grupa ustawiona: **{normalized or 'usunięty'}**",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Nieprawidłowy format grupy. Użyj @grupa lub https://t.me/grupa"
            )
    
    async def _handle_set_info_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle welcome message setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("welcome_message", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            preview = text.strip()[:100] + "..." if len(text.strip()) > 100 else text.strip()
            await update.message.reply_text(
                f"✅ Wiadomość powitalna ustawiona:\n\n*{preview}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Wiadomość za długa. Maksymalnie 1000 znaków."
            )
    
    async def _handle_set_info_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle bio setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("bio", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            preview = text.strip()[:100] + "..." if len(text.strip()) > 100 else text.strip()
            await update.message.reply_text(
                f"✅ Opis bota ustawiony:\n\n*{preview or 'usunięty'}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ Opis za długi. Maksymalnie 500 znaków."
            )
    
    async def _handle_set_kontakt(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle contact info setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        success = await self.config_service.set_config_value("contact_info", text, user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            await update.message.reply_text("✅ Informacje kontaktowe ustawione")
        else:
            await update.message.reply_text(
                "❌ Informacje za długie. Maksymalnie 500 znaków."
            )
    
    async def _handle_add_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle adding groups with enhanced feedback"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        # Parse group IDs
        group_ids = self.groups_service.parse_group_ids(text)
        
        if not group_ids:
            await update.message.reply_text(
                "❌ Nieprawidłowy format. Użyj ID grup oddzielonych przecinkami\n"
                "Przykład: `-100123456789, -100987654321, @mygroup`",
                parse_mode="Markdown"
            )
            return
        
        # Add groups
        added_count, errors = await self.groups_service.add_groups(group_ids, user_id)
        
        # Build response message
        response_lines = [f"✅ **Dodano {added_count} grup z {len(group_ids)} podanych**"]
        
        if errors:
            response_lines.append("\n⚠️ **Błędy:**")
            for error in errors[:10]:  # Limit to 10 errors
                response_lines.append(f"• {error}")
            if len(errors) > 10:
                response_lines.append(f"• ... i {len(errors) - 10} więcej")
        
        await self.command_bus.user_manager.reset_session(user_id, chat_id)
        await update.message.reply_text("\n".join(response_lines), parse_mode="Markdown")
    
    async def _handle_del_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle deleting groups with enhanced feedback"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        group_ids = self.groups_service.parse_group_ids(text)
        
        if not group_ids:
            await update.message.reply_text(
                "❌ Nieprawidłowy format. Użyj ID grup oddzielonych przecinkami"
            )
            return
        
        # Remove groups
        removed_count, errors = await self.groups_service.remove_groups(group_ids, user_id)
        
        # Build response message
        response_lines = [f"✅ **Usunięto {removed_count} grup z {len(group_ids)} podanych**"]
        
        if errors:
            response_lines.append("\n⚠️ **Błędy:**")
            for error in errors[:10]:
                response_lines.append(f"• {error}")
            if len(errors) > 10:
                response_lines.append(f"• ... i {len(errors) - 10} więcej")
        
        await self.command_bus.user_manager.reset_session(user_id, chat_id)
        await update.message.reply_text("\n".join(response_lines), parse_mode="Markdown")
    
    async def _handle_set_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle global time interval setting"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        try:
            minutes = int(text.strip())
            if minutes < 1 or minutes > 10080:  # Max 1 week
                raise ValueError("Out of range")
        except ValueError:
            await update.message.reply_text(
                "❌ Podaj liczbę minut od 1 do 10080 (tydzień)"
            )
            return
        
        success = await self.config_service.set_config_value("global_interval_minutes", str(minutes), user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            await update.message.reply_text(f"✅ Globalny interwał ustawiony na {minutes} minut")
        else:
            await update.message.reply_text("❌ Błąd podczas zapisywania. Spróbuj ponownie.")
    
    async def _handle_set_ex_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle excluded groups time interval"""
        user_id = update.effective_user.id
        chat_id = str(update.effective_chat.id)
        
        try:
            minutes = int(text.strip())
            if minutes < 1 or minutes > 10080:
                raise ValueError("Out of range")
        except ValueError:
            await update.message.reply_text(
                "❌ Podaj liczbę minut od 1 do 10080 (tydzień)"
            )
            return
        
        success = await self.config_service.set_config_value("excluded_interval_minutes", str(minutes), user_id)
        
        if success:
            await self.command_bus.user_manager.reset_session(user_id, chat_id)
            await update.message.reply_text(f"✅ Interwał dla wykluczonych grup ustawiony na {minutes} minut")
        else:
            await update.message.reply_text("❌ Błąd podczas zapisywania. Spróbuj ponownie.")
