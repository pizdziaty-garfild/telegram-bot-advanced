"""
Groups Service - Telegram Groups Management

Handles:
- Group CRUD operations with deduplication
- Batch add/delete with validation
- Group listing with pagination
- Audit logging for group changes
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from bot.infra.database import DatabaseManager

logger = logging.getLogger(__name__)

@dataclass
class GroupInfo:
    """Group information for display"""
    id: int
    telegram_id: str
    title: Optional[str]
    type: Optional[str]
    is_active: bool
    custom_interval: Optional[int]
    excluded_from_global: bool
    added_by: Optional[int]
    created_at: datetime

@dataclass 
class GroupsPage:
    """Paginated groups result"""
    groups: List[GroupInfo]
    total_count: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

class GroupsService:
    """Service for groups management"""
    
    def __init__(self, database: DatabaseManager):
        self.database = database
        self.logger = logging.getLogger(__name__)
    
    async def add_groups(self, group_ids: List[str], added_by: int) -> Tuple[int, List[str]]:
        """Add groups with deduplication"""
        added_count = 0
        errors = []
        
        try:
            async with self.database.get_session() as db:
                for group_id in group_ids:
                    # Validate group ID format
                    if not self._is_valid_group_id(group_id):
                        errors.append(f"Invalid ID format: {group_id}")
                        continue
                    
                    # Check if group already exists
                    result = await db.execute(
                        "SELECT id FROM groups WHERE telegram_id = :group_id",
                        {"group_id": group_id}
                    )
                    if result.fetchone():
                        errors.append(f"Already exists: {group_id}")
                        continue
                    
                    # Add new group
                    await db.execute(
                        """
                        INSERT INTO groups (telegram_id, is_active, added_by, created_at)
                        VALUES (:group_id, true, :added_by, :now)
                        """,
                        {
                            "group_id": group_id,
                            "added_by": added_by,
                            "now": datetime.utcnow()
                        }
                    )
                    added_count += 1
                
                await db.commit()
                
                # Log audit event
                await self._log_groups_change("groups_add", group_ids, added_by, added_count)
                
        except Exception as e:
            self.logger.error(f"Failed to add groups: {e}")
            errors.append(f"Database error: {str(e)}")
        
        return added_count, errors
    
    async def remove_groups(self, group_ids: List[str], removed_by: int) -> Tuple[int, List[str]]:
        """Remove groups by ID"""
        removed_count = 0
        errors = []
        
        try:
            async with self.database.get_session() as db:
                for group_id in group_ids:
                    if not self._is_valid_group_id(group_id):
                        errors.append(f"Invalid ID format: {group_id}")
                        continue
                    
                    result = await db.execute(
                        "DELETE FROM groups WHERE telegram_id = :group_id",
                        {"group_id": group_id}
                    )
                    
                    if result.rowcount > 0:
                        removed_count += 1
                    else:
                        errors.append(f"Not found: {group_id}")
                
                await db.commit()
                
                # Log audit event
                await self._log_groups_change("groups_remove", group_ids, removed_by, removed_count)
                
        except Exception as e:
            self.logger.error(f"Failed to remove groups: {e}")
            errors.append(f"Database error: {str(e)}")
        
        return removed_count, errors
    
    async def list_groups(self, page: int = 1, per_page: int = 50) -> GroupsPage:
        """List groups with pagination"""
        try:
            async with self.database.get_session() as db:
                # Get total count
                count_result = await db.execute("SELECT COUNT(*) as count FROM groups")
                total_count = count_result.fetchone().count
                
                # Calculate offset
                offset = (page - 1) * per_page
                
                # Get groups for current page
                result = await db.execute(
                    """
                    SELECT id, telegram_id, title, type, is_active, custom_interval, 
                           excluded_from_global, added_by, created_at
                    FROM groups
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                    """,
                    {"limit": per_page, "offset": offset}
                )
                
                groups = []
                for row in result.fetchall():
                    groups.append(GroupInfo(
                        id=row.id,
                        telegram_id=row.telegram_id,
                        title=row.title,
                        type=row.type,
                        is_active=row.is_active,
                        custom_interval=row.custom_interval,
                        excluded_from_global=row.excluded_from_global,
                        added_by=row.added_by,
                        created_at=row.created_at
                    ))
                
                return GroupsPage(
                    groups=groups,
                    total_count=total_count, 
                    page=page,
                    per_page=per_page,
                    has_next=offset + per_page < total_count,
                    has_prev=page > 1
                )
                
        except Exception as e:
            self.logger.error(f"Failed to list groups: {e}")
            return GroupsPage([], 0, page, per_page, False, False)
    
    async def get_groups_stats(self) -> Dict[str, int]:
        """Get groups statistics"""
        try:
            async with self.database.get_session() as db:
                result = await db.execute(
                    """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active,
                        SUM(CASE WHEN custom_interval IS NOT NULL THEN 1 ELSE 0 END) as custom_interval,
                        SUM(CASE WHEN excluded_from_global THEN 1 ELSE 0 END) as excluded
                    FROM groups
                    """
                )
                row = result.fetchone()
                
                return {
                    "total_groups": row.total or 0,
                    "active_groups": row.active or 0,
                    "inactive_groups": (row.total or 0) - (row.active or 0),
                    "custom_interval_groups": row.custom_interval or 0,
                    "excluded_groups": row.excluded or 0
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get groups stats: {e}")
            return {
                "total_groups": 0,
                "active_groups": 0, 
                "inactive_groups": 0,
                "custom_interval_groups": 0,
                "excluded_groups": 0
            }
    
    def parse_group_ids(self, text: str) -> List[str]:
        """Parse comma-separated group IDs with validation"""
        ids = []
        for part in text.split(','):
            part = part.strip()
            if self._is_valid_group_id(part):
                ids.append(part)
        return ids
    
    def _is_valid_group_id(self, group_id: str) -> bool:
        """Validate group ID format"""
        # Group IDs are typically negative integers for groups/supergroups
        # Channels can be positive or start with @
        if re.match(r'^-?\\d{1,20}$', group_id):
            return True
        # Allow @username format for channels
        if re.match(r'^@[a-zA-Z0-9_]{5,32}$', group_id):
            return True
        return False
    
    async def _log_groups_change(self, action: str, group_ids: List[str], user_id: int, count: int):
        """Log groups change to audit trail"""
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
                        INSERT INTO audit_logs (user_id, action, resource_type, resource_id, metadata, created_at)
                        VALUES (:user_id, :action, 'groups', 'batch', :metadata, :now)
                        """,
                        {
                            "user_id": user_row.id,
                            "action": action,
                            "metadata": json.dumps({
                                "group_ids": group_ids,
                                "count": count,
                                "timestamp": datetime.utcnow().isoformat()
                            }),
                            "now": datetime.utcnow()
                        }
                    )
                    await db.commit()
                    
        except Exception as e:
            self.logger.error(f"Failed to log groups change: {e}")
