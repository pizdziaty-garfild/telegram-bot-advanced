"""
Unit Tests for Config and Groups Services

Tests:
- ConfigService validation and normalization
- GroupsService CRUD operations and parsing
- BotInfo formatting methods
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from bot.services.config_service import ConfigService
from bot.services.groups_service import GroupsService, GroupInfo, GroupsPage
from bot.domain.models import BotInfo

class TestConfigService:
    """Test ConfigService functionality"""
    
    @pytest.fixture
    def config_service(self):
        database_mock = AsyncMock()
        return ConfigService(database_mock)
    
    def test_normalize_channel_link_valid(self, config_service):
        """Test channel link normalization with valid inputs"""
        # @username format
        assert config_service._normalize_channel_link("@testchannel") == "@testchannel"
        
        # t.me link format
        assert config_service._normalize_channel_link("https://t.me/testchannel") == "@testchannel"
        
        # Plain username
        assert config_service._normalize_channel_link("testchannel") == "@testchannel"
    
    def test_normalize_channel_link_invalid(self, config_service):
        """Test channel link normalization with invalid inputs"""
        # Empty string
        assert config_service._normalize_channel_link("") is None
        
        # Invalid characters
        assert config_service._normalize_channel_link("@test-channel") is None
        
        # Too short
        assert config_service._normalize_channel_link("@t") is None
        
        # Invalid URL
        assert config_service._normalize_channel_link("https://t.me/") is None
    
    def test_normalize_config_value_bot_name(self, config_service):
        """Test bot name normalization"""
        # Valid name
        assert config_service._normalize_config_value("bot_name", "Test Bot") == "Test Bot"
        
        # Empty name
        assert config_service._normalize_config_value("bot_name", "") is None
        
        # Too long name
        long_name = "x" * 101
        assert config_service._normalize_config_value("bot_name", long_name) is None
    
    def test_normalize_config_value_bio(self, config_service):
        """Test bio normalization"""
        # Valid bio
        bio = "This is a test bot for testing purposes."
        assert config_service._normalize_config_value("bio", bio) == bio
        
        # Too long bio  
        long_bio = "x" * 501
        assert config_service._normalize_config_value("bio", long_bio) is None
    
    def test_normalize_config_value_welcome_message(self, config_service):
        """Test welcome message normalization"""
        # Valid message
        message = "Welcome to our bot!"
        assert config_service._normalize_config_value("welcome_message", message) == message
        
        # Too long message
        long_message = "x" * 1001
        assert config_service._normalize_config_value("welcome_message", long_message) is None

class TestGroupsService:
    """Test GroupsService functionality"""
    
    @pytest.fixture
    def groups_service(self):
        database_mock = AsyncMock()
        return GroupsService(database_mock)
    
    def test_parse_group_ids_valid(self, groups_service):
        """Test group ID parsing with valid inputs"""
        # Negative group IDs
        ids = groups_service.parse_group_ids("-100123456789, -100987654321")
        assert ids == ["-100123456789", "-100987654321"]
        
        # Mixed formats
        ids = groups_service.parse_group_ids("-100123456789, @testgroup, 123456789")
        assert ids == ["-100123456789", "@testgroup", "123456789"]
    
    def test_parse_group_ids_invalid(self, groups_service):
        """Test group ID parsing with invalid inputs"""
        # Empty string
        ids = groups_service.parse_group_ids("")
        assert ids == []
        
        # Invalid formats
        ids = groups_service.parse_group_ids("invalid, @a, toolong" + "x" * 50)
        assert ids == []
    
    def test_is_valid_group_id(self, groups_service):
        """Test group ID validation"""
        # Valid negative group ID
        assert groups_service._is_valid_group_id("-100123456789") is True
        
        # Valid positive channel ID
        assert groups_service._is_valid_group_id("123456789") is True
        
        # Valid @username
        assert groups_service._is_valid_group_id("@testgroup") is True
        
        # Invalid formats
        assert groups_service._is_valid_group_id("invalid") is False
        assert groups_service._is_valid_group_id("@ab") is False  # Too short
        assert groups_service._is_valid_group_id("@" + "x" * 33) is False  # Too long

class TestBotInfo:
    """Test BotInfo dataclass methods"""
    
    def test_format_info_message_complete(self):
        """Test info message formatting with all fields"""
        bot_info = BotInfo(
            name="Test Bot",
            bio="A test bot for testing",
            channel="@testchannel", 
            channel_secondary="@testchannel2",
            group="@testgroup"
        )
        
        message = bot_info.format_info_message()
        
        assert "Test Bot" in message
        assert "A test bot for testing" in message
        assert "@testchannel" in message
        assert "@testchannel2" in message
        assert "@testgroup" in message
    
    def test_format_info_message_empty(self):
        """Test info message formatting with no fields"""
        bot_info = BotInfo()
        
        message = bot_info.format_info_message()
        
        assert "Informacje o bocie" in message
        assert "Skonfiguruj informacje" in message
    
    def test_format_contact_message_with_contact(self):
        """Test contact message formatting with contact info"""
        bot_info = BotInfo(contact="Contact us at test@example.com")
        
        message = bot_info.format_contact_message()
        
        assert "test@example.com" in message
        assert "Kontakt" in message
    
    def test_format_contact_message_without_contact(self):
        """Test contact message formatting without contact info"""
        bot_info = BotInfo()
        
        message = bot_info.format_contact_message()
        
        assert "Skonfiguruj informacje kontaktowe" in message

# Integration test mock
class TestConfigServiceIntegration:
    """Integration tests for ConfigService"""
    
    @pytest.mark.asyncio
    async def test_set_config_value_success(self):
        """Test successful config value setting"""
        # Mock database
        db_mock = AsyncMock()
        session_mock = AsyncMock()
        db_mock.get_session.return_value.__aenter__.return_value = session_mock
        
        config_service = ConfigService(db_mock)
        
        # Mock _get_config_value to return None (no old value)
        config_service._get_config_value = AsyncMock(return_value=None)
        config_service._log_config_change = AsyncMock()
        
        result = await config_service.set_config_value("bot_name", "Test Bot", 123)
        
        assert result is True
        session_mock.execute.assert_called()
        session_mock.commit.assert_called()

# Pytest configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
