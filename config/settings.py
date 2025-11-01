"""
Enhanced Settings - Configuration for Scheduler and Migrations

Additional settings:
- Scheduler configuration
- Auto-migration options
- Job retry/backoff settings
"""

import os
from enum import Enum
from typing import List, Optional, Set
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class BotMode(str, Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class EnhancedSettings(BaseSettings):
    """Enhanced application settings with scheduler configuration"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core bot settings (existing)
    bot_token: str = Field(..., description="Telegram bot token from @BotFather")
    bot_mode: BotMode = Field(default=BotMode.POLLING, description="Bot operation mode")
    admin_command_alias: str = Field(default="pusher", description="Admin panel command alias")
    
    # User management (existing)
    owner_users: Set[int] = Field(default_factory=set, description="Owner user IDs")
    admin_users: Set[int] = Field(default_factory=set, description="Admin user IDs")
    
    # Database (existing)
    database_url: str = Field(default="sqlite:///./data/bot.db", description="Database connection URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_echo: bool = Field(default=False, description="Enable SQL query logging")
    
    # NEW: Auto-migration settings
    auto_migrate: bool = Field(default=True, description="Automatically run database migrations on startup")
    
    # NEW: Enhanced scheduler settings
    scheduler_timezone: str = Field(default="Europe/Warsaw", description="Scheduler timezone")
    scheduler_max_workers: int = Field(default=5, description="Maximum scheduler worker threads")
    scheduler_job_grace_time: int = Field(default=300, description="Job misfire grace time in seconds")
    
    # NEW: Job retry/backoff settings
    job_max_retries: int = Field(default=3, description="Maximum job retry attempts")
    job_retry_backoff_min: int = Field(default=4, description="Minimum retry backoff in seconds")
    job_retry_backoff_max: int = Field(default=10, description="Maximum retry backoff in seconds")
    
    # Webhook settings (existing)  
    webhook_host: str = Field(default="0.0.0.0", description="Webhook server host")
    webhook_port: int = Field(default=8443, description="Webhook server port")
    webhook_path: str = Field(default="/webhook", description="Webhook URL path")
    webhook_url: Optional[str] = Field(default=None, description="Public webhook URL")
    webhook_cert_path: Optional[str] = Field(default=None, description="SSL certificate path")
    webhook_key_path: Optional[str] = Field(default=None, description="SSL private key path")
    
    # Logging (existing)
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_file: str = Field(default="logs/bot.log", description="Log file path")
    log_max_size: int = Field(default=10485760, description="Max log file size in bytes (10MB)")
    log_backup_count: int = Field(default=5, description="Number of backup log files")
    
    # Development (existing)
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    # Telemetry (existing)
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    sentry_environment: str = Field(default="production", description="Sentry environment")
    
    @validator("owner_users", "admin_users", pre=True)
    def parse_user_ids(cls, v):
        """Parse comma-separated user IDs"""
        if isinstance(v, str):
            if not v.strip():
                return set()
            return {int(user_id.strip()) for user_id in v.split(",") if user_id.strip()}
        return v or set()
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v:
            raise ValueError("Database URL is required")
        
        # Convert relative SQLite paths to absolute
        if v.startswith("sqlite:///./"):
            abs_path = os.path.abspath(v[10:])  # Remove sqlite:///
            return f"sqlite:///{abs_path}"
        
        return v

# Alias for backward compatibility
Settings = EnhancedSettings
