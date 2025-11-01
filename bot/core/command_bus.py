"""
Enhanced Command Bus - Integration Point for All Services

Coordinates:
- Database manager
- Enhanced user manager with session stats
- RBAC manager with caching
- Enhanced scheduler with job metrics
"""

from dataclasses import dataclass
from typing import Optional

from bot.infra.database import DatabaseManager
from bot.core.enhanced_user_manager import EnhancedUserManager, EnhancedRBACManager
from bot.core.enhanced_scheduler_service import EnhancedSchedulerService

@dataclass
class CommandBus:
    """Command bus for service coordination"""
    
    database: DatabaseManager
    user_manager: EnhancedUserManager
    rbac: EnhancedRBACManager
    scheduler: Optional[EnhancedSchedulerService] = None
    
    def __post_init__(self):
        """Post-initialization setup"""
        # Additional setup if needed
        pass
