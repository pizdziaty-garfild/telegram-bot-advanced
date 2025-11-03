"""
Enhanced Settings - Configuration for Scheduler and Migrations
"""

import os
from enum import Enum
from typing import Optional, Set
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
        extra="ignore",
    )

    # Core bot settings
    bot_token: str = Field(..., description="Telegram bot token from @BotFather")
    bot_mode: BotMode = Field(default=BotMode.POLLING, description="Bot operation mode")
    admin_command_alias: str = Field(default="pusher", description="Admin panel command alias")

    # User management
    owner_users: Set[int] = Field(default_factory=set, description="Owner user IDs")
    admin_users: Set[int] = Field(default_factory=set, description="Admin user IDs")

    # Database
    database_url: str = Field(default="sqlite:///./data/bot.db", description="Database connection URL")
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_echo: bool = Field(default=False, description="Enable SQL query logging")

    # Auto-migrations
    auto_migrate: bool = Field(default=True, description="Automatically run database migrations on startup")

    # Scheduler
    scheduler_timezone: str = Field(default="Europe/Warsaw", description="Scheduler timezone")
    scheduler_max_workers: int = Field(default=5, description="Maximum scheduler worker threads")
    scheduler_job_grace_time: int = Field(default=300, description="Job misfire grace time in seconds")

    # Retry/backoff
    job_max_retries: int = Field(default=3, description="Maximum job retry attempts")
    job_retry_backoff_min: int = Field(default=4, description="Minimum retry backoff in seconds")
    job_retry_backoff_max: int = Field(default=10, description="Maximum retry backoff in seconds")

    # Webhook
    webhook_host: str = Field(default="0.0.0.0", description="Webhook server host")
    webhook_port: int = Field(default=8443, description="Webhook server port")
    webhook_path: str = Field(default="/webhook", description="Webhook URL path")
    webhook_url: Optional[str] = Field(default=None, description="Public webhook URL")
    webhook_cert_path: Optional[str] = Field(default=None, description="SSL certificate path")
    webhook_key_path: Optional[str] = Field(default=None, description="SSL private key path")

    # Logging
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_file: str = Field(default="logs/bot.log", description="Log file path")
    log_max_size: int = Field(default=10485760, description="Max log file size in bytes (10MB)")
    log_backup_count: int = Field(default=5, description="Number of backup log files")

    # Dev
    debug_mode: bool = Field(default=False, description="Enable debug mode")

    # Telemetry
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    sentry_environment: str = Field(default="production", description="Sentry environment")

    @validator("owner_users", "admin_users", pre=True)
    def parse_user_ids(cls, v):
        """Accept int, list, tuple, set, or CSV string for user IDs"""
        if v is None:
            return set()
        # Already a set
        if isinstance(v, set):
            return {int(x) for x in v}
        # Single int
        if isinstance(v, int):
            return {v}
        # List or tuple of ints/strings
        if isinstance(v, (list, tuple)):
            return {int(x) for x in v}
        # CSV string or single string number
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return set()
            if "," not in s:
                return {int(s)}
            return {int(x.strip()) for x in s.split(",") if x.strip()}
        # Fallback: try to coerce iterable
        try:
            return {int(x) for x in v}
        except Exception:
            return set()

    @validator("database_url")
    def validate_database_url(cls, v):
        if not v:
            raise ValueError("Database URL is required")
        if v.startswith("sqlite:///./"):
            abs_path = os.path.abspath(v[10:])  # Remove sqlite:///
            return f"sqlite:///{abs_path}"
        return v


# Alias for backward compatibility
Settings = EnhancedSettings
