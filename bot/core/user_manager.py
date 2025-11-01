"""
User Manager - FSM Session Management

Handles:
- Multi-user session state management
- FSM state transitions with validation
- Session persistence and recovery
- Context data storage with TTL
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from bot.domain.models import User, Session, SessionState, Role
from bot.infra.database import DatabaseManager
from bot.core.rbac import RBACManager
from config.settings import Settings

@dataclass
class SessionContext:
    """Session context with TTL and state data"""
    user_id: int
    chat_id: str
    state: SessionState = SessionState.IDLE
    data: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    is_authenticated: bool = False
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def is_expired(self) -> bool:
        """Check if context has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def extend_ttl(self, minutes: int = 60):
        """Extend context TTL"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        self.last_activity = datetime.utcnow()
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

class UserManager:
    """Multi-user FSM session manager with persistence"""
    
    def __init__(self, database: DatabaseManager, rbac: RBACManager, settings: Settings):
        self.database = database
        self.rbac = rbac
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # In-memory session cache
        self._sessions: Dict[str, SessionContext] = {}
        self._session_lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def _cleanup_expired_sessions(self):
        """Background task to clean expired sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Clean every 5 minutes
                
                async with self._session_lock:
                    expired_keys = [
                        key for key, session in self._sessions.items()
                        if session.is_expired()
                    ]
                    
                    for key in expired_keys:
                        del self._sessions[key]
                        self.logger.debug(f"Cleaned expired session: {key}")
                
                # Also cleanup database sessions
                await self._cleanup_db_sessions()
                
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")
    
    async def _cleanup_db_sessions(self):
        """Clean expired sessions from database"""
        try:
            async with self.database.get_session() as db:
                # Delete expired sessions
                expired_sessions = await db.execute(
                    "DELETE FROM sessions WHERE expires_at < :now",
                    {"now": datetime.utcnow()}
                )
                await db.commit()
                
                if expired_sessions.rowcount > 0:
                    self.logger.debug(f"Cleaned {expired_sessions.rowcount} expired DB sessions")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning DB sessions: {e}")
    
    def _make_session_key(self, user_id: int, chat_id: str) -> str:
        """Generate session key"""
        return f"{user_id}:{chat_id}"
    
    async def get_or_create_session(self, user_id: int, chat_id: str) -> SessionContext:
        """Get existing session or create new one"""
        session_key = self._make_session_key(user_id, chat_id)
        
        async with self._session_lock:
            # Check memory cache first
            if session_key in self._sessions:
                session = self._sessions[session_key]
                if not session.is_expired():
                    session.update_activity()
                    return session
                else:
                    # Remove expired session
                    del self._sessions[session_key]
            
            # Try to load from database
            session = await self._load_session_from_db(user_id, chat_id)
            if session and not session.is_expired():
                self._sessions[session_key] = session
                session.update_activity()
                return session
            
            # Create new session
            session = await self._create_new_session(user_id, chat_id)
            self._sessions[session_key] = session
            
            return session
    
    async def _load_session_from_db(self, user_id: int, chat_id: str) -> Optional[SessionContext]:
        """Load session from database"""
        try:
            async with self.database.get_session() as db:
                # Get user
                user_result = await db.execute(
                    "SELECT * FROM users WHERE telegram_id = :user_id",
                    {"user_id": user_id}
                )
                user_row = user_result.fetchone()
                
                if not user_row:
                    return None
                
                # Get session
                session_result = await db.execute(
                    """
                    SELECT * FROM sessions 
                    WHERE user_id = :user_id AND chat_id = :chat_id 
                    AND is_active = true
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    {"user_id": user_row.id, "chat_id": chat_id}
                )
                session_row = session_result.fetchone()
                
                if not session_row:
                    return None
                
                # Create context from DB data
                context = SessionContext(
                    user_id=user_id,
                    chat_id=chat_id,
                    state=SessionState(session_row.state),
                    data=session_row.state_data or {},
                    expires_at=session_row.expires_at,
                    is_authenticated=True
                )
                
                return context
                
        except Exception as e:
            self.logger.error(f"Error loading session from DB: {e}")
            return None
    
    async def _create_new_session(self, user_id: int, chat_id: str) -> SessionContext:
        """Create new session context"""
        context = SessionContext(
            user_id=user_id,
            chat_id=chat_id,
            state=SessionState.IDLE,
            expires_at=datetime.utcnow() + timedelta(seconds=self.settings.session_ttl)
        )
        
        # Authenticate user
        user = await self.rbac.get_or_create_user(user_id)
        context.is_authenticated = user is not None
        
        # Save to database
        await self._save_session_to_db(context)
        
        return context
    
    async def _save_session_to_db(self, context: SessionContext):
        """Save session to database"""
        try:
            async with self.database.get_session() as db:
                # Get user ID
                user_result = await db.execute(
                    "SELECT id FROM users WHERE telegram_id = :user_id",
                    {"user_id": context.user_id}
                )
                user_row = user_result.fetchone()
                
                if not user_row:
                    self.logger.error(f"User not found for session save: {context.user_id}")
                    return
                
                # Upsert session
                await db.execute(
                    """
                    INSERT INTO sessions (user_id, chat_id, state, state_data, expires_at, is_active, updated_at, last_activity_at)
                    VALUES (:user_id, :chat_id, :state, :state_data, :expires_at, true, :now, :now)
                    ON CONFLICT (user_id, chat_id) DO UPDATE SET
                        state = EXCLUDED.state,
                        state_data = EXCLUDED.state_data,
                        expires_at = EXCLUDED.expires_at,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at,
                        last_activity_at = EXCLUDED.last_activity_at
                    """,
                    {
                        "user_id": user_row.id,
                        "chat_id": context.chat_id,
                        "state": context.state.value,
                        "state_data": json.dumps(context.data) if context.data else None,
                        "expires_at": context.expires_at,
                        "now": datetime.utcnow()
                    }
                )
                await db.commit()
                
        except Exception as e:
            self.logger.error(f"Error saving session to DB: {e}")
    
    async def update_session_state(
        self, 
        user_id: int, 
        chat_id: str, 
        new_state: SessionState,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update session state with validation"""
        session_key = self._make_session_key(user_id, chat_id)
        
        async with self._session_lock:
            session = await self.get_or_create_session(user_id, chat_id)
            
            # Validate state transition
            if not self._is_valid_transition(session.state, new_state):
                self.logger.warning(
                    f"Invalid state transition for user {user_id}: {session.state} -> {new_state}"
                )
                return False
            
            # Update state
            old_state = session.state
            session.state = new_state
            
            if data:
                session.data.update(data)
            
            session.extend_ttl(self.settings.session_ttl // 60)
            
            # Save to database
            await self._save_session_to_db(session)
            
            self.logger.debug(
                f"State transition for user {user_id}: {old_state} -> {new_state}"
            )
            
            return True
    
    def _is_valid_transition(self, current: SessionState, target: SessionState) -> bool:
        """Validate FSM state transitions"""
        # Define valid transitions
        valid_transitions = {
            SessionState.IDLE: [
                SessionState.ADMIN_PANEL,
                SessionState.SET_INFO_NAME,
                SessionState.SET_KONTAKT,
            ],
            SessionState.ADMIN_PANEL: [
                SessionState.IDLE,
                SessionState.SET_INFO_NAME,
                SessionState.SET_INFO_CHANNEL,
                SessionState.SET_INFO_GROUP,
                SessionState.SET_INFO_WELCOME,
                SessionState.SET_KONTAKT,
                SessionState.ADD_GROUPS,
                SessionState.DEL_GROUPS,
                SessionState.SET_GROUP_TIME,
                SessionState.SET_TIME,
                SessionState.SET_EX_TIME,
            ],
            # Info setting states
            SessionState.SET_INFO_NAME: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_INFO_CHANNEL: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_INFO_GROUP: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_INFO_WELCOME: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_KONTAKT: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            # Group management states
            SessionState.ADD_GROUPS: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.DEL_GROUPS: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_GROUP_TIME: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            # Time setting states
            SessionState.SET_TIME: [SessionState.ADMIN_PANEL, SessionState.IDLE],
            SessionState.SET_EX_TIME: [SessionState.ADMIN_PANEL, SessionState.IDLE],
        }
        
        allowed_targets = valid_transitions.get(current, [])
        return target in allowed_targets
    
    async def get_session_data(self, user_id: int, chat_id: str, key: str, default: Any = None) -> Any:
        """Get data from session context"""
        session = await self.get_or_create_session(user_id, chat_id)
        return session.data.get(key, default)
    
    async def set_session_data(self, user_id: int, chat_id: str, key: str, value: Any) -> bool:
        """Set data in session context"""
        session = await self.get_or_create_session(user_id, chat_id)
        session.data[key] = value
        session.update_activity()
        
        # Save to database
        await self._save_session_to_db(session)
        return True
    
    async def clear_session_data(self, user_id: int, chat_id: str, key: Optional[str] = None):
        """Clear session data (specific key or all)"""
        session = await self.get_or_create_session(user_id, chat_id)
        
        if key:
            session.data.pop(key, None)
        else:
            session.data.clear()
        
        session.update_activity()
        await self._save_session_to_db(session)
    
    async def reset_session(self, user_id: int, chat_id: str):
        """Reset session to idle state"""
        await self.update_session_state(user_id, chat_id, SessionState.IDLE)
        await self.clear_session_data(user_id, chat_id)
    
    async def get_active_sessions(self) -> List[SessionContext]:
        """Get all active sessions"""
        async with self._session_lock:
            return [
                session for session in self._sessions.values()
                if not session.is_expired()
            ]
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        active_sessions = await self.get_active_sessions()
        
        state_counts = {}
        for session in active_sessions:
            state = session.state.value
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return {
            "total_active_sessions": len(active_sessions),
            "state_distribution": state_counts,
            "authenticated_sessions": sum(1 for s in active_sessions if s.is_authenticated),
            "cached_sessions": len(self._sessions),
        }
    
    async def shutdown(self):
        """Shutdown user manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save all active sessions
        async with self._session_lock:
            for session in self._sessions.values():
                await self._save_session_to_db(session)
        
        self.logger.info("User manager shutdown complete")
