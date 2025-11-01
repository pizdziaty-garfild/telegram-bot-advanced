from dataclasses import dataclass
from typing import List, Optional, Tuple
from sqlalchemy import text

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
        offset = max(page - 1, 0) * (per_page or 50)
        async with self.database.get_session() as db:
            # Fallback: jeśli nie ma kolumny chat_id, użyj id jako identyfikatora wyświetlanego
            try:
                result = await db.execute(
                    text(
                        """
                        SELECT chat_id AS telegram_id, title, active AS is_active,
                               custom_interval, excluded_from_global
                        FROM groups
                        ORDER BY id
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": per_page, "offset": offset},
                )
            except Exception:
                result = await db.execute(
                    text(
                        """
                        SELECT CAST(id AS TEXT) AS telegram_id, COALESCE(title, '') AS title,
                               COALESCE(active, 1) AS is_active,
                               NULL AS custom_interval, 0 AS excluded_from_global
                        FROM groups
                        ORDER BY id
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": per_page, "offset": offset},
                )
            rows = result.fetchall()
            try:
                count_result = await db.execute(text("SELECT COUNT(*) AS cnt FROM groups"))
                total = int(count_result.scalar_one())
            except Exception:
                total = len(rows)
        groups = [
            Group(
                telegram_id=str(r.telegram_id),
                title=r.title or "",
                is_active=bool(r.is_active),
                custom_interval=(int(r.custom_interval) if getattr(r, "custom_interval", None) is not None else None),
                excluded_from_global=bool(getattr(r, "excluded_from_global", 0)),
            )
            for r in rows
        ]
        return GroupsPage(groups=groups, page=page, per_page=per_page, total=int(total))

    async def add_groups_bulk(self, bulk_text: str) -> Tuple[int, int]:
        lines = [ln.strip() for ln in (bulk_text or "").splitlines()]
        lines = [ln for ln in lines if ln]
        unique = []
        seen = set()
        for ln in lines:
            key = ln.lower()
            if key not in seen:
                seen.add(key)
                unique.append(ln)
        added, skipped = 0, 0
        async with self.database.get_session() as db:
            for ident in unique:
                chat_id = ident
                try:
                    # Próba z kolumną chat_id, fallback do id (insert minimalny)
                    try:
                        await db.execute(
                            text(
                                """
                                INSERT INTO groups (chat_id, title, active, created_at, updated_at)
                                VALUES (:chat_id, :title, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """
                            ),
                            {"chat_id": chat_id, "title": ""},
                        )
                    except Exception:
                        await db.execute(
                            text(
                                """
                                INSERT INTO groups (title)
                                VALUES (:title)
                                """
                            ),
                            {"title": chat_id},
                        )
                    added += 1
                except Exception:
                    skipped += 1
            await db.commit()
        return added, skipped
