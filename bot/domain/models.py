from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.infra.database import Base

# --- Enums ---
from enum import Enum as PyEnum

class Role(str, PyEnum):
    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    BANNED = "banned"

class Permission(str, PyEnum):
    ANY = "any"

class SessionState(str, PyEnum):
    IDLE = "idle"
    AWAITING_INPUT = "awaiting_input"
    ADMIN_PANEL = "admin_panel"


# --- Models ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default=Role.USER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    api_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    api_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    license_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    chat_id: Mapped[str] = mapped_column(String(64))

    state: Mapped[str] = mapped_column(String(32), default=SessionState.IDLE.value)
    state_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def is_expired(self) -> bool:
        if not self.is_active:
            return True
        if self.expires_at and self.expires_at < datetime.utcnow():
            return True
        return False
