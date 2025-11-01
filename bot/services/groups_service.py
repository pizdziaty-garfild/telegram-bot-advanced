from dataclasses import dataclass
from typing import List, Optional

from bot.infra.database import DatabaseManager

@dataclass
class Group:
    telegram_id: str
    title: str
    is_active: bool
    custom_interval: Optional[int]
    excluded_from_global: bool

@dataclass
class GroupsPage:
    groups: List[Group]
    page: int
    per_page: int
    total: int


class GroupsService:
    def __init__(self, database: DatabaseManager):
        self.database = database

    async def list_groups(self, page: int = 1, per_page: int = 50) -> GroupsPage:
        offset = max(page - 1, 0) * per_page
        async with self.database.get_session() as db:
            result = await db.execute(
                """
                SELECT chat_id AS telegram_id, title, active AS is_active,
                       custom_interval, excluded_from_global
                FROM groups
                ORDER BY id
                LIMIT :limit OFFSET :offset
                """,
                {"limit": per_page, "offset": offset},
            )
            rows = result.fetchall()

            count_result = await db.execute("SELECT COUNT(*) AS cnt FROM groups")
            total = count_result.scalar_one()

        groups = [
            Group(
                telegram_id=str(r.telegram_id),
                title=r.title or "",
                is_active=bool(r.is_active),
                custom_interval=(int(r.custom_interval) if r.custom_interval is not None else None),
                excluded_from_global=bool(r.excluded_from_global),
            )
            for r in rows
        ]
        return GroupsPage(groups=groups, page=page, per_page=per_page, total=int(total))
