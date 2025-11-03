from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import json

from bot.infra.database import DatabaseManager

@dataclass
class ConfigItem:
    key: str
    value: str
    updated_at: datetime


class ConfigService:
    def __init__(self, database: DatabaseManager):
        self.database = database

    async def get(self, key: str) -> Optional[str]:
        async with self.database.get_session() as db:
            result = await db.execute(
                "SELECT value FROM config WHERE key = :key",
                {"key": key},
            )
            row = result.fetchone()
            return row.value if row else None

    async def get_json(self, key: str) -> Optional[dict]:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def set(self, key: str, value: str) -> None:
        now = datetime.utcnow()
        async with self.database.get_session() as db:
            await db.execute(
                """
                INSERT INTO config (key, value, created_at, updated_at)
                VALUES (:key, :value, :now, :now)
                ON CONFLICT(key) DO UPDATE SET value = :value, updated_at = :now
                """,
                {"key": key, "value": value, "now": now},
            )
            await db.commit()
