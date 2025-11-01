"""
Integration Tests for Admin Panel Flows

Tests:
- Set Info flow end-to-end
- Groups CRUD operations
- Status display functionality
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers.enhanced_admin_panel import EnhancedAdminPanel
from bot.core.command_bus import CommandBus
from bot.domain.models import Permission, SessionState
from config.settings import Settings

class TestAdminPanelIntegration:
    """Integration tests for admin panel"""
    
    @pytest.fixture
    def admin_panel(self):
        # Mock dependencies
        command_bus_mock = MagicMock()
        command_bus_mock.rbac = AsyncMock()
        command_bus_mock.user_manager = AsyncMock()
        command_bus_mock.database = AsyncMock()
        
        settings_mock = MagicMock()
        settings_mock.admin_command_alias = "pusher"
        
        return EnhancedAdminPanel(command_bus_mock, settings_mock)
    
    @pytest.mark.asyncio  
    async def test_show_main_panel_authorized(self, admin_panel):
        """Test main panel display for authorized user"""
        # Mock update and context
        update_mock = MagicMock()
        update_mock.effective_user.id = 123
        update_mock.message.reply_text = AsyncMock()
        update_mock.callback_query = None
        
        context_mock = MagicMock()
        
        # Mock permission check
        admin_panel.command_bus.rbac.check_permission.return_value = True
        
        await admin_panel.show_main_panel(update_mock, context_mock)
        
        # Verify permission was checked
        admin_panel.command_bus.rbac.check_permission.assert_called_with(123, Permission.ADMIN_PANEL)
        
        # Verify message was sent
        update_mock.message.reply_text.assert_called_once()
        
        # Check that reply includes expected text
        call_args = update_mock.message.reply_text.call_args
        assert "Panel Administratora" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_show_main_panel_unauthorized(self, admin_panel):
        """Test main panel display for unauthorized user"""
        update_mock = MagicMock()
        update_mock.effective_user.id = 456
        update_mock.message.reply_text = AsyncMock()
        
        context_mock = MagicMock()
        
        # Mock permission check to return False
        admin_panel.command_bus.rbac.check_permission.return_value = False
        
        await admin_panel.show_main_panel(update_mock, context_mock)
        
        # Verify permission was checked
        admin_panel.command_bus.rbac.check_permission.assert_called_with(456, Permission.ADMIN_PANEL)
        
        # Verify unauthorized message was sent
        update_mock.message.reply_text.assert_called_once()
        call_args = update_mock.message.reply_text.call_args
        assert "Brak uprawnień" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_handle_set_info_callback(self, admin_panel):
        """Test Set Info callback handling"""
        # Mock callback query
        query_mock = MagicMock()
        query_mock.data = "admin_set_info"
        query_mock.answer = AsyncMock()
        query_mock.edit_message_text = AsyncMock()
        
        update_mock = MagicMock()
        update_mock.callback_query = query_mock
        update_mock.effective_user.id = 123
        update_mock.effective_chat.id = 456
        
        context_mock = MagicMock()
        
        await admin_panel.handle_callback(update_mock, context_mock)
        
        # Verify callback was answered
        query_mock.answer.assert_called_once()
        
        # Verify message was edited with Set Info menu
        query_mock.edit_message_text.assert_called_once()
        call_args = query_mock.edit_message_text.call_args
        assert "Set Info Menu" in call_args[1]["text"]
