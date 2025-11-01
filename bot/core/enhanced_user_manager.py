"""
Enhanced User Manager - Session Management with Statistics

This version removes direct import of EnhancedRBACManager from here
and expects it to be imported separately from bot.core.enhanced_rbac_manager
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

from bot.infra.database import DatabaseManager
from bot.domain.models import User, Session, Role, Permission, SessionState
from config.settings import Settings

logger = logging.getLogger(__name__)

class EnhancedUserManager:
    """Enhanced user and session management with statistics"""
    def __init__(self, database: DatabaseManager, settings: Settings):
        self.database = database
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._session_cache: Dict[str, Session] = {}
        self._user_cache: Dict[int, User] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_users": 0,
            "active_sessions": 0,
            "authenticated_sessions": 0,
            "cached_sessions": 0,
            "cleanup_runs": 0,
            "last_cleanup": None,
        }

    async def initialize(self):
        try:
            await self._preload_cache()
            self._cleanup_task = asyncio.create_task(self._session_cleanup_loop())
            self.logger.info("Enhanced user manager initialized")
        except Exception as e:
            self.logger.error(f"User manager initialization failed: {e}")
            raise

    async def _preload_cache(self):
        try:
            async with self.database.get_session() as db:
                sessions_result = await db.execute(
                    """
                    SELECT s.*, u.telegram_id, u.role, u.is_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.is_active = true
                    AND (s.expires_at IS NULL OR s.expires_at > :now)
                    """,
                    {"now": datetime.utcnow()},
                )
                sessions_loaded = 0
                for row in sessions_result.fetchall():
                    session_key = f"{row.telegram_id}:{row.chat_id}"
                    session = Session(
                        id=row.id,
                        session_id=row.session_id,
                        user_id=row.user_id,
                        chat_id=row.chat_id,
                        state=row.state,
                        state_data=row.state_data,
                        is_active=row.is_active,
                        expires_at=row.expires_at,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                        last_activity_at=row.last_activity_at,
                    )
                    self._session_cache[session_key] = session
                    sessions_loaded += 1

                users_result = await db.execute("SELECT * FROM users WHERE is_active = true")
                users_loaded = 0
                for row in users_result.fetchall():
                    user = User(
                        id=row.id,
                        telegram_id=row.telegram_id,
                        username=row.username,
                        first_name=row.first_name,
                        last_name=row.last_name,
                        role=row.role,
                        is_active=row.is_active,
                        api_id=row.api_id,
                        api_hash=row.api_hash,
                        license_key=row.license_key,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                        last_seen_at=row.last_seen_at,
                    )
                    self._user_cache[row.telegram_id] = user
                    users_loaded += 1

                self.logger.info(f"Preloaded {sessions_loaded} sessions and {users_loaded} users")
        except Exception as e:
            self.logger.error(f"Failed to preload cache: {e}")

    async def get_or_create_session(self, telegram_id: int, chat_id: str) -> Session:
        session_key = f"{telegram_id}:{chat_id}"
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            if session.is_expired():
                await self._expire_session(session_key)
            else:
                session.last_activity_at = datetime.utcnow()
                return session

        user = await self._get_or_create_user(telegram_id)
        try:
            async with self.database.get_session() as db:
                session_result = await db.execute(
                    """
                    INSERT INTO sessions (user_id, chat_id, state, is_active, expires_at, created_at, updated_at, last_activity_at)
                    VALUES (:user_id, :chat_id, :state, true, :expires_at, :now, :now, :now)
                    RETURNING *
                    """,
                    {
                        "user_id": user.id,
                        "chat_id": chat_id,
                        "state": SessionState.IDLE,
                        "expires_at": datetime.utcnow() + timedelta(hours=24),
                        "now": datetime.utcnow(),
                    },
                )
                session_row = session_result.fetchone()
                await db.commit()
                session = Session(
                    id=session_row.id,
                    session_id=session_row.session_id,
                    user_id=session_row.user_id,
                    chat_id=session_row.chat_id,
                    state=session_row.state,
                    state_data=session_row.state_data,
                    is_active=session_row.is_active,
                    expires_at=session_row.expires_at,
                    created_at=session_row.created_at,
                    updated_at=session_row.updated_at,
                    last_activity_at=session_row.last_activity_at,
                )
                self._session_cache[session_key] = session
                return session
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            raise

    async def _get_or_create_user(self, telegram_id: int) -> User:
        if telegram_id in self._user_cache:
            return self._user_cache[telegram_id]
        try:
            async with self.database.get_session() as db:
                user_result = await db.execute(
                    "SELECT * FROM users WHERE telegram_id = :telegram_id",
                    {"telegram_id": telegram_id},
                )
                user_row = user_result.fetchone()
                if user_row:
                    user = User(
                        id=user_row.id,
                        telegram_id=user_row.telegram_id,
                        username=user_row.username,
                        first_name=user_row.first_name,
                        last_name=user_row.last_name,
                        role=user_row.role,
                        is_active=user_row.is_active,
                        api_id=user_row.api_id,
                        api_hash=user_row.api_hash,
                        license_key=user_row.license_key,
                        created_at=user_row.created_at,
                        updated_at=user_row.updated_at,
                        last_seen_at=user_row.last_seen_at,
                    )
                else:
                    user_result = await db.execute(
                        """
                        INSERT INTO users (telegram_id, role, is_active, created_at, updated_at, last_seen_at)
                        VALUES (:telegram_id, :role, true, :now, :now, :now)
                        RETURNING *
                        """,
                        {"telegram_id": telegram_id, "role": Role.USER, "now": datetime.utcnow()},
                    )
                    user_row = user_result.fetchone()
                    await db.commit()
                    user = User(
                        id=user_row.id,
                        telegram_id=user_row.telegram_id,
                        username=user_row.username,
                        first_name=user_row.first_name,
                        last_name=user_row.last_name,
                        role=user_row.role,
                        is_active=user_row.is_active,
                        api_id=user_row.api_id,
                        api_hash=user_row.api_hash,
                        license_key=user_row.license_key,
                        created_at=user_row.created_at,
                        updated_at=user_row.updated_at,
                        last_seen_at=user_row.last_seen_at,
                    )
                self._user_cache[telegram_id] = user
                return user
        except Exception as e:
            self.logger.error(f"Failed to get/create user: {e}")
            raise

    async def update_session_state(self, telegram_id: int, chat_id: str, state: SessionState, state_data: Optional[Dict] = None):
        session_key = f"{telegram_id}:{chat_id}"
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            session.state = state
            session.state_data = state_data
            session.updated_at = datetime.utcnow()
            session.last_activity_at = datetime.utcnow()
            try:
                async with self.database.get_session() as db:
                    await db.execute(
                        """
                        UPDATE sessions 
                        SET state = :state, state_data = :state_data, updated_at = :now, last_activity_at = :now
                        WHERE id = :session_id
                        """,
                        {"state": state, "state_data": state_data, "session_id": session.id, "now": datetime.utcnow()},
                    )
                    await db.commit()
            except Exception as e:
                self.logger.error(f"Failed to update session state: {e}")

    async def reset_session(self, telegram_id: int, chat_id: str):
        await self.update_session_state(telegram_id, chat_id, SessionState.IDLE)

    async def _expire_session(self, session_key: str):
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            try:
                async with self.database.get_session() as db:
                    await db.execute(
                        "UPDATE sessions SET is_active = false WHERE id = :session_id",
                        {"session_id": session.id},
                    )
                    await db.commit()
                del self._session_cache[session_key]
            except Exception as e:
                self.logger.error(f"Failed to expire session: {e}")

    async def _session_cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(300)
                await self._cleanup_expired_sessions()
                self._stats["cleanup_runs"] += 1
                self._stats["last_cleanup"] = datetime.utcnow()
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")

    async def _cleanup_expired_sessions(self):
        try:
            expired_keys = []
            for session_key, session in self._session_cache.items():
                if session.is_expired():
                    expired_keys.append(session_key)
            for key in expired_keys:
                await self._expire_session(key)
        except Exception as e:
            self.logger.error(f"Failed to cleanup sessions: {e}")

    async def get_session_stats(self) -> Dict[str, Any]:
        try:
            self._stats["cached_sessions"] = len(self._session_cache)
            async with self.database.get_session() as db:
                active_result = await db.execute("SELECT COUNT(*) as count FROM sessions WHERE is_active = true")
                self._stats["active_sessions"] = active_result.fetchone().count
                auth_result = await db.execute(
                    """
                    SELECT COUNT(*) as count FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.is_active = true AND u.role != 'user'
                    """
                )
                self._stats["authenticated_sessions"] = auth_result.fetchone().count
                users_result = await db.execute("SELECT COUNT(*) as count FROM users WHERE is_active = true")
                self._stats["total_users"] = users_result.fetchone().count
                states_result = await db.execute(
                    """
                    SELECT state, COUNT(*) as count 
                    FROM sessions 
                    WHERE is_active = true 
                    GROUP BY state
                    """
                )
                state_distribution = {row.state: row.count for row in states_result.fetchall()}
                return {
                    "total_active_sessions": self._stats["active_sessions"],
                    "authenticated_sessions": self._stats["authenticated_sessions"],
                    "cached_sessions": self._stats["cached_sessions"],
                    "total_users": self._stats["total_users"],
                    "cleanup_runs": self._stats["cleanup_runs"],
                    "last_cleanup": self._stats["last_cleanup"],
                    "state_distribution": state_distribution,
                }
        except Exception as e:
            self.logger.error(f"Failed to get session stats: {e}")
            return {
                "total_active_sessions": 0,
                "authenticated_sessions": 0,
                "cached_sessions": len(self._session_cache),
                "total_users": 0,
                "cleanup_runs": self._stats["cleanup_runs"],
                "last_cleanup": self._stats["last_cleanup"],
                "state_distribution": {},
            }

    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Enhanced user manager shutdown complete")
