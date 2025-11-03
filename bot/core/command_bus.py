from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.infra.database import DatabaseManager
    from bot.core.enhanced_user_manager import EnhancedUserManager
    from bot.core.enhanced_rbac_manager import EnhancedRBACManager
    from bot.core.enhanced_scheduler_service import EnhancedSchedulerService

from bot.services.groups_service import GroupsService


class CommandBusServices:
    def __init__(self, database, user_manager, rbac, scheduler):
        self.groups_service = GroupsService(database)


class CommandBus:
    """Central command bus for handling all bot operations"""

    def __init__(
        self,
        database: "DatabaseManager",
        user_manager: "EnhancedUserManager",
        rbac: "EnhancedRBACManager",
        scheduler: "EnhancedSchedulerService",
    ):
        self.database = database
        self.user_manager = user_manager
        self.rbac = rbac
        self.scheduler = scheduler
        self.services = CommandBusServices(database, user_manager, rbac, scheduler)
