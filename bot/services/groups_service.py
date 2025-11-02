from dataclasses import dataclass
from typing import List, Optional, Tuple
from sqlalchemy import text
import logging

from bot.infra.database import DatabaseManager

logger = logging.getLogger(__name__)

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
        self._schema_detected = False
        self._has_chat_id = False
        self._has_active = False
        self._has_custom_interval = False
        self._has_excluded_from_global = False

    async def _detect_schema(self):
        if self._schema_detected:
            return
            
        async with self.database.get_session() as db:
            try:
                # SQLite: sprawdź kolumny tabeli groups
                result = await db.execute(text("PRAGMA table_info(groups)"))
                columns = [row.name for row in result.fetchall()]
                
                self._has_chat_id = 'chat_id' in columns
                self._has_active = 'active' in columns
                self._has_custom_interval = 'custom_interval' in columns
                self._has_excluded_from_global = 'excluded_from_global' in columns
                
                logger.info(f"Groups schema detected: chat_id={self._has_chat_id}, active={self._has_active}, custom_interval={self._has_custom_interval}, excluded={self._has_excluded_from_global}")
            except Exception as e:
                logger.warning(f"Schema detection failed: {e}, using fallback")
                
        self._schema_detected = True

    def _normalize_group_identifier(self, ident: str) -> str:
        """Normalize group identifier for database storage"""
        ident = ident.strip()
        if ident.startswith('@'):
            return ident
        # Handle negative chat_ids
        try:
            chat_id = int(ident)
            return str(chat_id)
        except ValueError:
            return ident

    async def list_groups(self, page: int = 1, per_page: int = 50) -> GroupsPage:
        await self._detect_schema()
        offset = max(page - 1, 0) * (per_page or 50)
        
        async with self.database.get_session() as db:
            if self._has_chat_id:
                # Use chat_id as primary identifier
                result = await db.execute(
                    text(
                        """
                        SELECT COALESCE(chat_id, CAST(id AS TEXT)) AS telegram_id, 
                               COALESCE(title, '') AS title,
                               COALESCE(active, 1) AS is_active,
                               custom_interval,
                               COALESCE(excluded_from_global, 0) AS excluded_from_global
                        FROM groups
                        ORDER BY id
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": per_page, "offset": offset},
                )
            else:
                # Fallback to minimal schema
                result = await db.execute(
                    text(
                        """
                        SELECT CAST(id AS TEXT) AS telegram_id, COALESCE(title, '') AS title
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
                
        groups = []
        for r in rows:
            if self._has_chat_id:
                groups.append(Group(
                    telegram_id=str(r.telegram_id),
                    title=r.title or "",
                    is_active=bool(r.is_active),
                    custom_interval=r.custom_interval,
                    excluded_from_global=bool(r.excluded_from_global),
                ))
            else:
                groups.append(Group(
                    telegram_id=str(r.telegram_id),
                    title=r.title or "",
                    is_active=True,
                    custom_interval=None,
                    excluded_from_global=False,
                ))
                
        return GroupsPage(groups=groups, page=page, per_page=per_page, total=int(total))

    async def add_groups_bulk(self, bulk_text: str) -> Tuple[int, int]:
        await self._detect_schema()
        
        lines = [ln.strip() for ln in (bulk_text or "").splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith('#')]
        
        # Normalize and deduplicate
        unique_idents = []
        seen = set()
        for ln in lines:
            normalized = self._normalize_group_identifier(ln)
            if normalized not in seen:
                seen.add(normalized)
                unique_idents.append(normalized)
        
        added, skipped = 0, 0
        async with self.database.get_session() as db:
            for ident in unique_idents:
                try:
                    if self._has_chat_id:
                        # Insert with full schema
                        params = {
                            "chat_id": ident,
                            "title": ident,  # Use identifier as title initially
                        }
                        
                        query_parts = ["chat_id", "title"]
                        value_parts = [":chat_id", ":title"]
                        
                        if self._has_active:
                            params["active"] = 1
                            query_parts.append("active")
                            value_parts.append(":active")
                            
                        if self._has_custom_interval:
                            params["custom_interval"] = None
                            query_parts.append("custom_interval")
                            value_parts.append(":custom_interval")
                            
                        if self._has_excluded_from_global:
                            params["excluded_from_global"] = 0
                            query_parts.append("excluded_from_global")
                            value_parts.append(":excluded_from_global")
                        
                        insert_sql = f"""
                        INSERT OR IGNORE INTO groups ({', '.join(query_parts)}, created_at, updated_at)
                        VALUES ({', '.join(value_parts)}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """
                        
                        result = await db.execute(text(insert_sql), params)
                        if result.rowcount > 0:
                            added += 1
                        else:
                            skipped += 1  # Already exists
                    else:
                        # Fallback to minimal schema
                        result = await db.execute(
                            text("INSERT OR IGNORE INTO groups (title) VALUES (:title)"),
                            {"title": ident}
                        )
                        if result.rowcount > 0:
                            added += 1
                        else:
                            skipped += 1
                            
                except Exception as e:
                    logger.warning(f"Failed to add group {ident}: {e}")
                    skipped += 1
                    
            await db.commit()
        
        logger.info(f"Groups bulk add completed: added={added}, skipped={skipped}")
        return added, skipped
