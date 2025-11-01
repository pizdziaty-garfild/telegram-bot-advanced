"""
Domain Models - Core Business Entities

Defines the main entities of the telegram bot domain:
- User management with roles and permissions
- Groups with custom scheduling
- Jobs and scheduling
- Sessions and state management
"""

import enum
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

Base = declarative_base()

class Role(str, enum.Enum):
    """User roles with hierarchical permissions"""
    OWNER = "owner"      # Full system access
    ADMIN = "admin"      # Admin panel access 
    USER = "user"        # Basic bot functions
    BANNED = "banned"    # No access

class Permission(str, enum.Enum):
    """Granular permissions for RBAC"""
    ADMIN_PANEL = "admin_panel"
    MANAGE_USERS = "manage_users"
    MANAGE_GROUPS = "manage_groups" 
    MANAGE_JOBS = "manage_jobs"
    VIEW_LOGS = "view_logs"
    SYSTEM_STATUS = "system_status"

class SessionState(str, enum.Enum):
    """FSM states for user interactions"""
    IDLE = "idle"
    
    # Admin panel states
    ADMIN_PANEL = "admin_panel"
    SET_INFO_NAME = "set_info_name"
    SET_INFO_CHANNEL = "set_info_channel"
    SET_INFO_GROUP = "set_info_group" 
    SET_INFO_WELCOME = "set_info_welcome"
    SET_KONTAKT = "set_kontakt"
    
    # Group management states
    ADD_GROUPS = "add_groups"
    DEL_GROUPS = "del_groups"
    SET_GROUP_TIME = "set_group_time"
    
    # Time management states
    SET_TIME = "set_time"
    SET_EX_TIME = "set_ex_time"

class JobStatus(str, enum.Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

# ==========================================
# DATABASE MODELS
# ==========================================

class User(Base):
    """User entity with role-based access control"""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Security & Authorization
    role = Column(String(20), nullable=False, default=Role.USER)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # API Management (for multi-user support)
    api_id = Column(Integer, nullable=True)
    api_hash = Column(String(255), nullable=True)  # Encrypted
    license_key = Column(String(255), nullable=True)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission"""
        role_permissions = {
            Role.OWNER: [p for p in Permission],
            Role.ADMIN: [
                Permission.ADMIN_PANEL,
                Permission.MANAGE_GROUPS,
                Permission.MANAGE_JOBS,
                Permission.VIEW_LOGS,
                Permission.SYSTEM_STATUS,
            ],
            Role.USER: [],
            Role.BANNED: [],
        }
        return permission in role_permissions.get(self.role, [])
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges"""
        return self.role in [Role.OWNER, Role.ADMIN]

class Group(Base):
    """Telegram group/channel with custom settings"""
    
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=True)
    type = Column(String(50), nullable=True)  # group, supergroup, channel
    
    # Scheduling settings
    is_active = Column(Boolean, default=True, nullable=False)
    custom_interval = Column(Integer, nullable=True)  # Minutes, overrides global
    excluded_from_global = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    added_by = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    jobs = relationship("Job", back_populates="group")

class Job(Base):
    """Scheduled job for message sending"""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(100), unique=True, nullable=False)  # Scheduler job ID
    
    # Job details
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    message_content = Column(Text, nullable=True)
    message_type = Column(String(50), default="text", nullable=False)
    
    # Scheduling
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    interval_minutes = Column(Integer, nullable=True)
    is_recurring = Column(Boolean, default=True, nullable=False)
    
    # Execution tracking
    status = Column(String(20), default=JobStatus.PENDING, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Metadata
    created_by = Column(Integer, ForeignKey("users.telegram_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    group = relationship("Group", back_populates="jobs")

class Session(Base):
    """User session with FSM state management"""
    
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Session identity
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chat_id = Column(String(100), nullable=False)
    
    # FSM state
    state = Column(String(50), default=SessionState.IDLE, nullable=False)
    state_data = Column(JSON, nullable=True)  # Context for current state
    
    # Session management
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Composite unique constraint for user+chat
    __table_args__ = (UniqueConstraint("user_id", "chat_id", name="unique_user_chat_session"),)
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def extend_session(self, minutes: int = 60):
        """Extend session expiration"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
        self.last_activity_at = datetime.utcnow()

class AuditLog(Base):
    """Audit trail for admin actions"""
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True)
    
    # Event details
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    
    # Event data
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")

class Config(Base):
    """Bot configuration storage"""
    
    __tablename__ = "config"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=True)
    encrypted = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# ==========================================
# DOMAIN DATACLASSES (DTOs)
# ==========================================

@dataclass
class BotInfo:
    """Bot information displayed in /info command"""
    name: Optional[str] = None
    channel: Optional[str] = None
    group: Optional[str] = None
    welcome_message: Optional[str] = None
    contact: Optional[str] = None

@dataclass
class GroupStats:
    """Group statistics for monitoring"""
    total_groups: int = 0
    active_groups: int = 0
    inactive_groups: int = 0
    custom_interval_groups: int = 0
    excluded_groups: int = 0

@dataclass 
class SystemHealth:
    """System health status"""
    status: str = "healthy"
    database_connected: bool = True
    scheduler_running: bool = True
    active_jobs: int = 0
    active_sessions: int = 0
    memory_usage_mb: float = 0.0
    uptime_seconds: int = 0
    errors_last_hour: int = 0

@dataclass
class JobMetrics:
    """Job execution metrics"""
    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    success_rate: float = 0.0
    avg_execution_time_ms: float = 0.0
