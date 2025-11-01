"""
Telemetry Manager - Monitoring and Metrics

Handles:
- Error tracking with Sentry
- Performance metrics
- Health monitoring
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

from config.settings import Settings

class TelemetryManager:
    """Telemetry and monitoring manager"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.start_time = datetime.utcnow()
        
    async def initialize(self):
        """Initialize telemetry services"""
        if self.settings.sentry_dsn and SENTRY_AVAILABLE:
            sentry_sdk.init(
                dsn=self.settings.sentry_dsn,
                integrations=[
                    AsyncioIntegration(auto_enabling_integrations=False),
                    SqlalchemyIntegration(),
                ],
                traces_sample_rate=0.1,
                environment="production" if not self.settings.debug_mode else "development",
                release=self.settings.bot_version,
            )
            self.logger.info("Sentry telemetry initialized")
        
    async def start(self):
        """Start telemetry collection"""
        self.logger.info("Telemetry started")
    
    async def record_error(self, error: Exception, context: Dict[str, Any]):
        """Record error with context"""
        if SENTRY_AVAILABLE:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(error)
    
    async def shutdown(self):
        """Shutdown telemetry"""
        if SENTRY_AVAILABLE:
            sentry_sdk.flush(timeout=5.0)
        self.logger.info("Telemetry shutdown complete")
