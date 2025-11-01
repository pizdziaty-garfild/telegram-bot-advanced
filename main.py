"""
Main Application Entry Point - Enhanced with Scheduler and Migrations

Adds robust sys.path injection so running `python main.py` from project root
in venv/Windows just works without PYTHONPATH tweaks.
"""

import os
import sys

# --- Ensure project root on sys.path ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import asyncio
import logging
from pathlib import Path
from typing import Optional

from telegram.ext import Application

from config.settings import Settings
from bot.infra.logging import setup_logging
from bot.infra.database import DatabaseManager
from bot.infra.telemetry import TelemetryManager
from bot.core.enhanced_scheduler_service import EnhancedSchedulerService
from bot.core.enhanced_user_manager import EnhancedUserManager
from bot.core.enhanced_rbac_manager import EnhancedRBACManager
from bot.core.command_bus import CommandBus
from bot.handlers.user_commands import setup_user_handlers
from bot.handlers.admin_commands import setup_admin_handlers

logger = logging.getLogger(__name__)


class EnhancedTelegramBot:
    """Enhanced telegram bot with scheduler and migrations"""

    def __init__(self):
        self.settings = Settings()
        self.database: Optional[DatabaseManager] = None
        self.scheduler: Optional[EnhancedSchedulerService] = None
        self.user_manager: Optional[EnhancedUserManager] = None
        self.rbac: Optional[EnhancedRBACManager] = None
        self.command_bus: Optional[CommandBus] = None
        self.telemetry: Optional[TelemetryManager] = None
        self.application: Optional[Application] = None

        # Shutdown flag
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize all components"""
        try:
            # Setup logging
            setup_logging(self.settings)
            logger.info("Enhanced Telegram Bot starting...")

            # Setup telemetry
            if self.settings.sentry_dsn:
                self.telemetry = TelemetryManager(self.settings)
                await self.telemetry.initialize()

            # Initialize database
            self.database = DatabaseManager(self.settings.get_db_config())
            await self.database.initialize()

            # Initialize enhanced components
            self.user_manager = EnhancedUserManager(self.database, self.settings)
            await self.user_manager.initialize()

            self.rbac = EnhancedRBACManager(self.user_manager)

            self.scheduler = EnhancedSchedulerService(self.database, self.settings)
            await self.scheduler.initialize()

            # Initialize command bus
            self.command_bus = CommandBus(
                database=self.database,
                user_manager=self.user_manager,
                rbac=self.rbac,
                scheduler=self.scheduler,
            )

            # Initialize Telegram application
            self.application = Application.builder().token(self.settings.bot_token).build()

            # Setup handlers
            setup_user_handlers(self.application, self.command_bus, self.settings)
            setup_admin_handlers(self.application, self.command_bus, self.settings)

            logger.info("Enhanced bot initialization complete")

        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise

    async def start_polling(self):
        """Start bot in polling mode"""
        try:
            logger.info("Starting enhanced scheduler...")
            await self.scheduler.start()

            logger.info("Starting bot in polling mode...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                poll_interval=1.0,
                timeout=10,
                bootstrap_retries=-1,
                read_timeout=20,
                write_timeout=20,
                connect_timeout=20,
                pool_timeout=20,
            )

            logger.info("Bot is running in polling mode. Press Ctrl+C to stop.")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"Polling mode failed: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        try:
            logger.info("Shutting down enhanced telegram bot...")

            # Stop application
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

            # Shutdown scheduler
            if self.scheduler:
                await self.scheduler.shutdown()

            # Shutdown user manager
            if self.user_manager:
                await self.user_manager.shutdown()

            # Close database
            if self.database:
                await self.database.close()

            # Close telemetry
            if self.telemetry:
                await self.telemetry.shutdown()

            logger.info("Enhanced bot shutdown complete")

        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            self._shutdown_event.set()


async def main():
    """Main entry point"""
    bot = EnhancedTelegramBot()

    try:
        # Initialize bot
        await bot.initialize()

        # Start bot based on mode (polling default)
        await bot.start_polling()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        sys.exit(1)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    Path("certs").mkdir(exist_ok=True)

    # Run bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
