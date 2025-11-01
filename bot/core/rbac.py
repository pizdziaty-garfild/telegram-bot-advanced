"""
RBAC Manager - Role-Based Access Control

Handles:
- User authentication and authorization
- Role and permission management
- User registration and role assignment
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import select, insert, update
from bot.domain.models import User, Role, Permission
from bot.infra.database import DatabaseManager
from config.settings import Settings

class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self, database: DatabaseManager, settings: Settings):
        self.database = database
        self.settings = settings
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize RBAC system"""
        await self._setup_admin_users()
    
    async def _setup_admin_users(self):
        """Setup configured admin users"""
        try:
            async with self.database.get_session() as db:
                # Create owner users
                for user_id in self.settings.owner_users:
                    await self._ensure_user_role(db, user_id, Role.OWNER)
                
                # Create admin users
                for user_id in self.settings.admin_users:
                    await self._ensure_user_role(db, user_id, Role.ADMIN)
                
                await db.commit()
                
        except Exception as e:
            self.logger.error(f"Error setting up admin users: {e}")
    
    async def _ensure_user_role(self, db, telegram_id: int, role: Role):
        """Ensure user exists with specified role"""
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create user
            await db.execute(
                insert(User).values(
                    telegram_id=telegram_id,
                    role=role.value,
                    is_active=True
                )
            )
            self.logger.info(f"Created user {telegram_id} with role {role.value}")
        elif user.role != role.value:
            # Update role
            await db.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(role=role.value)
            )
            self.logger.info(f"Updated user {telegram_id} role to {role.value}")
    
    async def get_or_create_user(self, telegram_id: int, **user_data) -> Optional[User]:
        """Get existing user or create new one"""
        try:
            async with self.database.get_session() as db:
                result = await db.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    # Create new user with default role
                    user_values = {
                        "telegram_id": telegram_id,
                        "role": Role.USER.value,
                        "is_active": True,
                        **user_data
                    }
                    
                    result = await db.execute(insert(User).values(**user_values))
                    await db.commit()
                    
                    # Fetch created user
                    result = await db.execute(
                        select(User).where(User.telegram_id == telegram_id)
                    )
                    user = result.scalar_one()
                    
                    self.logger.info(f"Created new user: {telegram_id}")
                
                return user
                
        except Exception as e:
            self.logger.error(f"Error getting/creating user {telegram_id}: {e}")
            return None
    
    async def check_permission(self, telegram_id: int, permission: Permission) -> bool:
        """Check if user has specific permission"""
        user = await self.get_or_create_user(telegram_id)
        if not user or not user.is_active:
            return False
        
        return user.has_permission(permission)
    
    async def is_admin(self, telegram_id: int) -> bool:
        """Check if user is admin"""
        user = await self.get_or_create_user(telegram_id)
        return user.is_admin() if user else False
