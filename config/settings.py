"""
Central Configuration Management

Handles all application settings with validation,
environment variable loading, and secure defaults.
"""

import os
import secrets
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
from functools import lru_cache

from pydantic import BaseSettings, Field, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings

class BotMode(str, Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Settings(PydanticBaseSettings):
    """Application settings with validation"""
    
    # === CORE TELEGRAM BOT ===
    bot_token: str = Field(..., description="Bot token from @BotFather")
    bot_mode: BotMode = Field(BotMode.POLLING, description="Bot operation mode")
    
    # === WEBHOOK CONFIGURATION ===
    webhook_url: Optional[str] = Field(None, description="Webhook URL for production")
    webhook_port: int = Field(8443, description="Webhook port")
    webhook_path: str = Field("/webhook", description="Webhook endpoint path")
    
    # === TLS/SSL ===
    tls_cert_path: Optional[str] = Field(None, description="TLS certificate path")
    tls_key_path: Optional[str] = Field(None, description="TLS private key path")
    
    # === DATABASE ===
    db_url: str = Field(
        "sqlite+aiosqlite:///./data/bot.db", 
        description="Database connection URL"
    )
    db_echo: bool = Field(False, description="Enable SQL query logging")
    db_pool_size: int = Field(20, description="Connection pool size")
    db_max_overflow: int = Field(30, description="Max pool overflow")
    
    # === SECURITY & ENCRYPTION ===
    enc_master_key: Optional[str] = Field(None, description="Master encryption key")
    jwt_secret: Optional[str] = Field(None, description="JWT signing secret")
    session_ttl: int = Field(3600, description="Session TTL in seconds")
    
    # === ADMIN USERS ===
    admin_users: List[int] = Field(
        default_factory=list,
        description="List of admin user IDs"
    )
    owner_users: List[int] = Field(
        default_factory=list, 
        description="List of owner user IDs"
    )
    
    # === RATE LIMITING ===
    rate_limit_enabled: bool = Field(True, description="Enable rate limiting")
    rate_limit_requests: int = Field(10, description="Requests per minute")
    rate_limit_window: int = Field(60, description="Rate limit window in seconds")
    
    # === SCHEDULING ===
    scheduler_timezone: str = Field("Europe/Warsaw", description="Scheduler timezone")
    scheduler_max_workers: int = Field(10, description="Max scheduler workers")
    
    # === LOGGING ===
    log_level: LogLevel = Field(LogLevel.INFO, description="Logging level")
    log_file: str = Field("logs/bot.log", description="Log file path")
    log_max_size: int = Field(10 * 1024 * 1024, description="Max log file size")
    log_backup_count: int = Field(5, description="Number of backup log files")
    
    # === MONITORING ===
    sentry_dsn: Optional[str] = Field(None, description="Sentry DSN for error tracking")
    health_check_port: int = Field(8080, description="Health check endpoint port")
    
    # === FEATURE FLAGS ===
    enable_telemetry: bool = Field(True, description="Enable telemetry collection")
    enable_audit_log: bool = Field(True, description="Enable audit logging")
    debug_mode: bool = Field(False, description="Enable debug mode")
    
    # === CUSTOMIZATION ===
    admin_command_alias: str = Field("pusher", description="Admin panel command alias")
    bot_name: str = Field("Advanced Bot", description="Bot display name")
    bot_version: str = Field("1.0.0", description="Bot version")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("enc_master_key", pre=True, always=True)
    def generate_master_key(cls, v):
        if v is None:
            return secrets.token_urlsafe(32)
        return v
        
    @validator("jwt_secret", pre=True, always=True) 
    def generate_jwt_secret(cls, v):
        if v is None:
            return secrets.token_urlsafe(64)
        return v
        
    @validator("admin_users", pre=True)
    def parse_admin_users(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v or []
        
    @validator("owner_users", pre=True)
    def parse_owner_users(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v or []

    def get_db_config(self) -> Dict[str, Any]:
        """Get database configuration dictionary"""
        config = {
            "url": self.db_url,
            "echo": self.db_echo,
        }
        
        if "postgresql" in self.db_url:
            config.update({
                "pool_size": self.db_pool_size,
                "max_overflow": self.db_max_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            })
            
        return config
        
    def is_webhook_mode(self) -> bool:
        """Check if running in webhook mode"""
        return self.bot_mode == BotMode.WEBHOOK
        
    def get_webhook_config(self) -> Optional[Dict[str, Any]]:
        """Get webhook configuration if in webhook mode"""
        if not self.is_webhook_mode():
            return None
            
        return {
            "url": self.webhook_url,
            "port": self.webhook_port, 
            "path": self.webhook_path,
            "cert_path": self.tls_cert_path,
            "key_path": self.tls_key_path,
        }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()