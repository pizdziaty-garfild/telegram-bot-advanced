from typing import Optional

from config.settings import Settings

class TelemetryManager:
    """Minimal telemetry manager; no-op unless SENTRY_DSN provided"""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._enabled = bool(getattr(self.settings, "sentry_dsn", None))
        self._client = None

    async def initialize(self):
        if not self._enabled:
            return
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=self.settings.sentry_dsn,
                environment=getattr(self.settings, "sentry_environment", "production"),
                traces_sample_rate=0.0,
            )
            self._client = sentry_sdk
        except Exception:
            # Soft-fail: telemetry is optional
            self._enabled = False

    async def shutdown(self):
        # No explicit shutdown needed for sentry_sdk
        return
