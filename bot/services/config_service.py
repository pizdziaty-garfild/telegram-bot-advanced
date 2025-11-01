"""
Configuration Service - Bot Config Persistence

Handles:
- Bot info fields (name, channels, welcome, contact, bio)
- Configuration validation and normalization
- Audit logging for config changes
- JSON storage with optional encryption
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from bot.infra.database import DatabaseManager
from bot.domain.models import BotInfo

logger = logging.getLogger(__name__)

class ConfigService:
    """Service for bot configuration management"""
    
    def __init__(self, database: DatabaseManager):
        self.database = database
        self.logger = logging.getLogger(__name__)
    
    async def get_bot_info(self) -> BotInfo:
        """Get complete bot information"""
        try:
            async with self.database.get_session() as db:
                # Get all config values
                result = await db.execute(
                    "SELECT key, value FROM config WHERE key IN (:keys)",
                    {"keys": "bot_name,bot_channel,bot_group,welcome_message,contact_info,channel_secondary,bio"}
                )
                
                config_data = {}
                for row in result.fetchall():
                    try:
                        # Parse JSON value
                        config_data[row.key] = json.loads(row.value) if row.value else None
                    except json.JSONDecodeError:
                        config_data[row.key] = row.value
                
                return BotInfo(
                    name=config_data.get("bot_name"),
                    channel=config_data.get("bot_channel"), 
                    group=config_data.get("bot_group"),
                    welcome_message=config_data.get("welcome_message"),
                    contact=config_data.get("contact_info"),
                    channel_secondary=config_data.get("channel_secondary"),
                    bio=config_data.get("bio")
                )
                
        except Exception as e:
            self.logger.error(f"Failed to get bot info: {e}")
            return BotInfo()
    
    async def set_config_value(self, key: str, value: str, user_id: int) -> bool:
        """Set configuration value with validation and audit"""
        try:
            # Validate input
            normalized_value = self._normalize_config_value(key, value)
            if normalized_value is None and value.strip():
                return False  # Validation failed
            
            # Get old value for audit
            old_value = await self._get_config_value(key)
            
            # Save new value
            async with self.database.get_session() as db:
                if normalized_value is None:
                    # Delete config entry for empty/invalid values
                    await db.execute(
                        "DELETE FROM config WHERE key = :key",
                        {"key": key}
                    )
                else:
                    # Upsert config value
                    await db.execute(
                        """
                        INSERT INTO config (key, value, encrypted, updated_at)
                        VALUES (:key, :value, false, :now)
                        ON CONFLICT (key) DO UPDATE SET
                            value = EXCLUDED.value,
                            updated_at = EXCLUDED.updated_at
                        """,
                        {
                            "key": key,
                            "value": json.dumps(normalized_value),
                            "now": datetime.utcnow()
                        }
                    )
                
                await db.commit()
            
            # Log audit event
            await self._log_config_change(key, old_value, normalized_value, user_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set config {key}: {e}")
            return False
    
    async def _get_config_value(self, key: str) -> Optional[str]:
        """Get raw config value"""
        try:
            async with self.database.get_session() as db:
                result = await db.execute(
                    "SELECT value FROM config WHERE key = :key",
                    {"key": key}
                )
                row = result.fetchone()
                return json.loads(row.value) if row and row.value else None
        except:
            return None
    
    def _normalize_config_value(self, key: str, value: str) -> Optional[str]:
        """Normalize and validate config values"""
        value = value.strip()
        
        if not value:
            return None
        
        if key in ["bot_name", "bio"]:
            # Text fields with length limits
            max_len = 100 if key == "bot_name" else 500 
            if len(value) > max_len:
                return None
            return value
        
        elif key in ["bot_channel", "bot_group", "channel_secondary"]:
            # Channel/group links with format validation
            return self._normalize_channel_link(value)
        
        elif key == "welcome_message":
            # Welcome message with length limit
            if len(value) > 1000:
                return None
            return value
        
        elif key == "contact_info":
            # Contact info with length limit  
            if len(value) > 500:
                return None
            return value
        
        else:
            # Unknown key - store as-is but with length limit
            if len(value) > 1000:
                return None
            return value
    
    def _normalize_channel_link(self, link: str) -> Optional[str]:
        """Normalize channel/group links"""
        link = link.strip()
        
        # @username format
        if link.startswith('@'):
            if len(link) < 2 or not link[1:].replace('_', '').isalnum():
                return None
            return link
        
        # t.me/username format
        if link.startswith('https://t.me/'):
            username = link[13:]  # Remove https://t.me/
            if not username or not username.replace('_', '').isalnum():
                return None
            return f"@{username}"  # Normalize to @username format
        
        # Try to parse as @username if no prefix
        if link.replace('_', '').isalnum():
            return f"@{link}"
        
        return None
    
    async def _log_config_change(self, key: str, old_value: Any, new_value: Any, user_id: int):
        """Log configuration change to audit trail"""
        try:
            async with self.database.get_session() as db:
                # Get user ID from telegram_id
                user_result = await db.execute(
                    "SELECT id FROM users WHERE telegram_id = :telegram_id",
                    {"telegram_id": user_id}
                )
                user_row = user_result.fetchone()
                
                if user_row:
                    await db.execute(
                        """
                        INSERT INTO audit_logs (user_id, action, resource_type, resource_id, old_values, new_values, created_at)
                        VALUES (:user_id, :action, 'config', :key, :old_values, :new_values, :now)
                        """,
                        {
                            "user_id": user_row.id,
                            "action": f"config_update_{key}",
                            "key": key,
                            "old_values": json.dumps({key: old_value}) if old_value else None,
                            "new_values": json.dumps({key: new_value}) if new_value else None,
                            "now": datetime.utcnow()
                        }
                    )
                    await db.commit()
                    
        except Exception as e:
            self.logger.error(f"Failed to log config change: {e}")
