import logging
from typing import Set

from bot.domain.models import Role

class EnhancedRBACManager:
    """Simple RBAC checks based on user roles"""

    def __init__(self, user_manager):
        self.user_manager = user_manager
        self.logger = logging.getLogger(__name__)

    async def is_owner(self, telegram_id: int) -> bool:
        user = await self.user_manager._get_or_create_user(telegram_id)
        return user.role == Role.OWNER.value

    async def is_admin(self, telegram_id: int) -> bool:
        user = await self.user_manager._get_or_create_user(telegram_id)
        return user.role in {Role.OWNER.value, Role.ADMIN.value}

    async def is_allowed(self, telegram_id: int, allowed_roles: Set[str]) -> bool:
        user = await self.user_manager._get_or_create_user(telegram_id)
        return user.role in allowed_roles
