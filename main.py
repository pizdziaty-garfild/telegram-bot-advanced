"""
Main Application Entry Point - Enhanced with Scheduler and Migrations
"""

import os
import sys

# Ensure project root on sys.path
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
    def __init__(self):
        self.settings = Settings()
        self.database: Optional[DatabaseManager] = None
        self.scheduler: Optional[EnhancedSchedulerService] = None
        self.user_manager: Optional[EnhancedUserManager] = None
        self.rbac: Optional[EnhancedRBACManager] = None
        self.command_bus: Optional[CommandBus] = None
        self.telemetry: Optional[TelemetryManager] = None
        self.application: Optional[Application] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        try:
            setup_logging(self.settings)
            logger.info("Enhanced Telegram Bot starting...")

            if self.settings.sentry_dsn:
                self.telemetry = TelemetryManager(self.settings)
                await self.telemetry.initialize()

            # Initialize database (DatabaseManager reads Settings internally)
            self.database = DatabaseManager()
            await self.database.initialize()

            self.user_manager = EnhancedUserManager(self.database, self.settings)
            await self.user_manager.initialize()

            self.rbac = EnhancedRBACManager(self.user_manager)

            self.scheduler = EnhancedSchedulerService(self.database, self.settings)
            await self.scheduler.initialize()

            self.command_bus = CommandBus(
                database=self.database,
                user_manager=self.user_manager,
                rbac=self.rbac,
                scheduler=self.scheduler,
            )

            self.application = Application.builder().token(self.settings.bot_token).build()

            setup_user_handlers(self.application, self.command_bus, self.settings)
            setup_admin_handlers(self.application, self.command_bus, self.settings)

            logger.info("Enhanced bot initialization complete")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise

    async def start_polling(self):
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
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error(f"Polling mode failed: {e}")
            raise

    async def shutdown(self):
        try:
            logger.info("Shutting down enhanced telegram bot...")
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            if self.scheduler:
                await self.scheduler.shutdown()
            if self.user_manager:
                await self.user_manager.shutdown()
            if self.database:
                await self.database.close()
            if self.telemetry:
                await self.telemetry.shutdown()
            logger.info("Enhanced bot shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            self._shutdown_event.set()


async def main():
    bot = EnhancedTelegramBot()
    try:
        await bot.initialize()
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        sys.exit(1)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    Path("certs").mkdir(exist_ok=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
