"""
Groups Listing Handler - Paginated Groups Display

Handles:
- Groups listing with 50 items per page
- Inline keyboard navigation (Prev/Next)
- Group details display with status indicators
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Optional

from bot.services.groups_service import GroupsService, GroupsPage
from bot.core.command_bus import CommandBus

logger = logging.getLogger(__name__)

class GroupsListHandler:
    """Handle groups listing with pagination"""
    
    def __init__(self, command_bus: CommandBus):
        self.command_bus = command_bus
        self.groups_service = GroupsService(command_bus.database)
    
    async def show_groups_list(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE, 
        page: int = 1
    ):
        """Show paginated groups list"""
        try:
            # Get groups page
            groups_page = await self.groups_service.list_groups(page=page, per_page=50)
            
            if groups_page.total_count == 0:
                text = "📋 **Lista Grup**\n\nBrak dodanych grup.\n\nUżyj 'Add Groups' aby dodać grupy."
                keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
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
                return
            
            # Build groups list text
            lines = [
                f"📋 **Lista Grup** (strona {page}/{(groups_page.total_count - 1) // 50 + 1})",
                f"Łącznie: {groups_page.total_count} grup\n"
            ]
            
            for i, group in enumerate(groups_page.groups, 1):
                # Status indicators
                status = "🟢" if group.is_active else "🔴"
                custom = "⚙️" if group.custom_interval else ""
                excluded = "🚫" if group.excluded_from_global else ""
                
                # Group info line
                line = f"`{(page-1)*50 + i:2d}.` {status} `{group.telegram_id}`"
                
                if group.title:
                    line += f" *{group.title[:30]}*"
                
                if custom or excluded:
                    indicators = " ".join([custom, excluded]).strip()
                    line += f" {indicators}"
                
                lines.append(line)
            
            # Add legend if needed
            if any(g.custom_interval or g.excluded_from_global for g in groups_page.groups):
                lines.extend([
                    "",
                    "**Legenda:** ⚙️ custom interval | 🚫 excluded from global"
                ])
            
            text = "\n".join(lines)
            
            # Build navigation keyboard
            nav_buttons = []
            if groups_page.has_prev:
                nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"groups_list_{page-1}"))
            if groups_page.has_next:
                nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"groups_list_{page+1}"))
            
            keyboard = []
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send response
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
            
        except Exception as e:
            self.logger.error(f"Failed to show groups list: {e}")
            error_text = "❌ Błąd podczas ładowania listy grup"
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
    
    async def handle_pagination_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pagination callback"""
        query = update.callback_query
        await query.answer()
        
        # Extract page number from callback_data: "groups_list_N"
        try:
            page = int(query.data.split("_")[-1])
            await self.show_groups_list(update, context, page)
        except (ValueError, IndexError):
            await query.edit_message_text("❌ Błąd nawigacji")
