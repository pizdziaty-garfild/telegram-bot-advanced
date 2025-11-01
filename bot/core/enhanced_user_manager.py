"""
Enhanced User Manager - Session Management with Statistics

Handles:
- User authentication and role management
- Session lifecycle with TTL cleanup
- Session statistics for Status display
- Background cleanup tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import hashlib

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
        
        # In-memory session cache for fast access
        self._session_cache: Dict[str, Session] = {}
        self._user_cache: Dict[int, User] = {}
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics tracking
        self._stats = {
            "total_users": 0,
            "active_sessions": 0,
            "authenticated_sessions": 0,
            "cached_sessions": 0,
            "cleanup_runs": 0,
            "last_cleanup": None
        }
    
    async def initialize(self):
        """Initialize user manager with cache preloading"""
        try:
            # Load active sessions into cache
            await self._preload_cache()
            
            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._session_cleanup_loop())
            
            self.logger.info("Enhanced user manager initialized")
            
        except Exception as e:
            self.logger.error(f"User manager initialization failed: {e}")
            raise
    
    async def _preload_cache(self):
        """Preload active sessions and users into cache"""
        try:
            async with self.database.get_session() as db:
                # Load active sessions
                sessions_result = await db.execute(
                    """
                    SELECT s.*, u.telegram_id, u.role, u.is_active
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.is_active = true
                    AND (s.expires_at IS NULL OR s.expires_at > :now)
                    """,
                    {"now": datetime.utcnow()}
                )
                
                sessions_loaded = 0
                for row in sessions_result.fetchall():
                    session_key = f"{row.telegram_id}:{row.chat_id}"
                    
                    # Create session object
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
                        last_activity_at=row.last_activity_at
                    )
                    
                    self._session_cache[session_key] = session
                    sessions_loaded += 1
                
                # Load users
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
                        last_seen_at=row.last_seen_at
                    )
                    
                    self._user_cache[row.telegram_id] = user
                    users_loaded += 1
                
                self.logger.info(f"Preloaded {sessions_loaded} sessions and {users_loaded} users")
                
        except Exception as e:
            self.logger.error(f"Failed to preload cache: {e}")
    
    async def get_or_create_session(self, telegram_id: int, chat_id: str) -> Session:
        """Get existing session or create new one"""
        session_key = f"{telegram_id}:{chat_id}"
        
        # Check cache first
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            
            # Check if session is expired
            if session.is_expired():
                await self._expire_session(session_key)
            else:
                # Update last activity
                session.last_activity_at = datetime.utcnow()
                return session
        
        # Create new session
        user = await self._get_or_create_user(telegram_id)
        
        try:
            async with self.database.get_session() as db:
                # Create session in database
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
                        "now": datetime.utcnow()
                    }
                )
                
                session_row = session_result.fetchone()
                await db.commit()
                
                # Create session object
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
                    last_activity_at=session_row.last_activity_at
                )
                
                # Cache session
                self._session_cache[session_key] = session
                
                return session
                
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            raise
    
    async def _get_or_create_user(self, telegram_id: int) -> User:
        """Get existing user or create new one"""
        # Check cache first
        if telegram_id in self._user_cache:
            return self._user_cache[telegram_id]
        
        try:
            async with self.database.get_session() as db:
                # Try to find existing user
                user_result = await db.execute(
                    "SELECT * FROM users WHERE telegram_id = :telegram_id",
                    {"telegram_id": telegram_id}
                )
                user_row = user_result.fetchone()
                
                if user_row:
                    # Create user object
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
                        last_seen_at=user_row.last_seen_at
                    )
                else:
                    # Create new user
                    user_result = await db.execute(
                        """
                        INSERT INTO users (telegram_id, role, is_active, created_at, updated_at, last_seen_at)
                        VALUES (:telegram_id, :role, true, :now, :now, :now)
                        RETURNING *
                        """,
                        {
                            "telegram_id": telegram_id,
                            "role": Role.USER,
                            "now": datetime.utcnow()
                        }
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
                        last_seen_at=user_row.last_seen_at
                    )
                
                # Cache user
                self._user_cache[telegram_id] = user
                
                return user
                
        except Exception as e:
            self.logger.error(f"Failed to get/create user: {e}")
            raise
    
    async def update_session_state(self, telegram_id: int, chat_id: str, state: SessionState, state_data: Optional[Dict] = None):
        """Update session state"""
        session_key = f"{telegram_id}:{chat_id}"
        
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            session.state = state
            session.state_data = state_data
            session.updated_at = datetime.utcnow()
            session.last_activity_at = datetime.utcnow()
            
            # Update in database
            try:
                async with self.database.get_session() as db:
                    await db.execute(
                        """
                        UPDATE sessions 
                        SET state = :state, state_data = :state_data, updated_at = :now, last_activity_at = :now
                        WHERE id = :session_id
                        """,
                        {
                            "state": state,
                            "state_data": state_data,
                            "session_id": session.id,
                            "now": datetime.utcnow()
                        }
                    )
                    await db.commit()
            except Exception as e:
                self.logger.error(f"Failed to update session state: {e}")
    
    async def reset_session(self, telegram_id: int, chat_id: str):
        """Reset session to idle state"""
        await self.update_session_state(telegram_id, chat_id, SessionState.IDLE)
    
    async def _expire_session(self, session_key: str):
        """Expire and remove session"""
        if session_key in self._session_cache:
            session = self._session_cache[session_key]
            
            try:
                async with self.database.get_session() as db:
                    await db.execute(
                        "UPDATE sessions SET is_active = false WHERE id = :session_id",
                        {"session_id": session.id}
                    )
                    await db.commit()
                
                del self._session_cache[session_key]
                
            except Exception as e:
                self.logger.error(f"Failed to expire session: {e}")
    
    async def _session_cleanup_loop(self):
        """Background task for session cleanup"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                await self._cleanup_expired_sessions()
                
                self._stats["cleanup_runs"] += 1
                self._stats["last_cleanup"] = datetime.utcnow()
                
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            expired_keys = []
            now = datetime.utcnow()
            
            # Check cached sessions
            for session_key, session in self._session_cache.items():
                if session.is_expired():
                    expired_keys.append(session_key)
            
            # Remove expired sessions
            for key in expired_keys:
                await self._expire_session(key)
            
            # Clean up database sessions older than 7 days
            async with self.database.get_session() as db:
                result = await db.execute(
                    """
                    UPDATE sessions 
                    SET is_active = false 
                    WHERE is_active = true 
                    AND (expires_at < :now OR last_activity_at < :week_ago)
                    """,
                    {
                        "now": now,
                        "week_ago": now - timedelta(days=7)
                    }
                )
                
                cleaned_count = result.rowcount
                await db.commit()
                
                if cleaned_count > 0:
                    self.logger.info(f"Cleaned up {cleaned_count} expired sessions")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup sessions: {e}")
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics for Status display"""
        try:
            # Update cached stats
            self._stats["cached_sessions"] = len(self._session_cache)
            
            async with self.database.get_session() as db:
                # Total active sessions
                active_result = await db.execute(
                    "SELECT COUNT(*) as count FROM sessions WHERE is_active = true"
                )
                self._stats["active_sessions"] = active_result.fetchone().count
                
                # Authenticated sessions (users with roles other than USER)
                auth_result = await db.execute(
                    """
                    SELECT COUNT(*) as count FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.is_active = true AND u.role != 'user'
                    """
                )
                self._stats["authenticated_sessions"] = auth_result.fetchone().count
                
                # Total users
                users_result = await db.execute(
                    "SELECT COUNT(*) as count FROM users WHERE is_active = true"
                )
                self._stats["total_users"] = users_result.fetchone().count
                
                # State distribution
                states_result = await db.execute(
                    """
                    SELECT state, COUNT(*) as count 
                    FROM sessions 
                    WHERE is_active = true 
                    GROUP BY state
                    """
                )
                
                state_distribution = {}
                for row in states_result.fetchall():
                    state_distribution[row.state] = row.count
                
                return {
                    "total_active_sessions": self._stats["active_sessions"],
                    "authenticated_sessions": self._stats["authenticated_sessions"],
                    "cached_sessions": self._stats["cached_sessions"],
                    "total_users": self._stats["total_users"],
                    "cleanup_runs": self._stats["cleanup_runs"],
                    "last_cleanup": self._stats["last_cleanup"],
                    "state_distribution": state_distribution
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
                "state_distribution": {}
            }
    
    async def shutdown(self):
        """Shutdown user manager and background tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Enhanced user manager shutdown complete")
