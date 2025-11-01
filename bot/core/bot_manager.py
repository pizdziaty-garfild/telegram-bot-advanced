"""
Bot Manager - Main Application Lifecycle

Handles:
- Bot initialization and shutdown
- Error handling and recovery
- Health checks and monitoring
- Clean architecture coordination
"""

import asyncio
import logging
import signal
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Bot
from telegram.ext import Application, ContextTypes
from telegram.error import TelegramError

from config.settings import Settings
from bot.infra.database import DatabaseManager
from bot.infra.scheduler import SchedulerManager
from bot.infra.logging import setup_logging
from bot.infra.telemetry import TelemetryManager
from bot.core.command_bus import CommandBus
from bot.core.user_manager import UserManager
from bot.core.rbac import RBACManager
from bot.handlers.user_commands import setup_user_handlers
from bot.handlers.admin_commands import setup_admin_handlers

class BotManager:
    """Main application manager with clean shutdown and error recovery"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.start_time = datetime.utcnow()
        
        # Core components
        self.application: Optional[Application] = None
        self.database: Optional[DatabaseManager] = None
        self.scheduler: Optional[SchedulerManager] = None
        self.telemetry: Optional[TelemetryManager] = None
        self.command_bus: Optional[CommandBus] = None
        self.user_manager: Optional[UserManager] = None
        self.rbac: Optional[RBACManager] = None
        
        # Shutdown handling
        self._shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self._shutdown_event.set()
    
    async def start(self) -> None:
        """Start the bot with full initialization"""
        try:
            await self._initialize_components()
            await self._setup_handlers()
            await self._start_services()
            
            self.logger.info("Bot started successfully")
            
            # Run until shutdown signal
            await self._shutdown_event.wait()
            
        finally:
            await self._cleanup()
    
    async def _initialize_components(self) -> None:
        """Initialize all core components"""
        self.logger.info("Initializing bot components...")
        
        # Setup structured logging
        setup_logging(self.settings)
        
        # Initialize database
        self.database = DatabaseManager(self.settings.get_db_config())
        await self.database.initialize()
        
        # Initialize scheduler
        self.scheduler = SchedulerManager(self.settings)
        await self.scheduler.initialize()
        
        # Initialize telemetry
        if self.settings.enable_telemetry:
            self.telemetry = TelemetryManager(self.settings)
            await self.telemetry.initialize()
        
        # Initialize RBAC
        self.rbac = RBACManager(self.database, self.settings)
        await self.rbac.initialize()
        
        # Initialize user manager
        self.user_manager = UserManager(
            database=self.database,
            rbac=self.rbac,
            settings=self.settings
        )
        
        # Initialize command bus
        self.command_bus = CommandBus(
            user_manager=self.user_manager,
            rbac=self.rbac,
            database=self.database,
            scheduler=self.scheduler,
            settings=self.settings
        )
        
        # Initialize Telegram application
        self.application = (
            Application.builder()
            .token(self.settings.bot_token)
            .build()
        )
        
        self.logger.info("Components initialized successfully")
    
    async def _setup_handlers(self) -> None:
        """Setup command and callback handlers"""
        self.logger.info("Setting up command handlers...")
        
        # Setup user commands (public)
        setup_user_handlers(
            app=self.application,
            command_bus=self.command_bus,
            settings=self.settings
        )
        
        # Setup admin commands (protected)
        setup_admin_handlers(
            app=self.application,
            command_bus=self.command_bus,
            settings=self.settings
        )
        
        # Setup error handler
        self.application.add_error_handler(self._error_handler)
        
        self.logger.info("Handlers setup complete")
    
    async def _start_services(self) -> None:
        """Start all background services"""
        self.logger.info("Starting services...")
        
        # Start scheduler
        if self.scheduler:
            await self.scheduler.start()
        
        # Start telemetry
        if self.telemetry:
            await self.telemetry.start()
        
        # Start Telegram bot
        if self.settings.is_webhook_mode():
            await self._start_webhook()
        else:
            await self._start_polling()
        
        self.logger.info("All services started")
    
    async def _start_webhook(self) -> None:
        """Start bot in webhook mode"""
        webhook_config = self.settings.get_webhook_config()
        if not webhook_config:
            raise ValueError("Webhook configuration missing")
        
        self.logger.info(f"Starting webhook on {webhook_config['url']}")
        
        # Start webhook server
        await self.application.bot.set_webhook(
            url=webhook_config["url"] + webhook_config["path"],
            certificate=webhook_config.get("cert_path")
        )
        
        # Run webhook server
        await self.application.run_webhook(
            listen="0.0.0.0",
            port=webhook_config["port"],
            url_path=webhook_config["path"],
            cert=webhook_config.get("cert_path"),
            key=webhook_config.get("key_path"),
            webhook_url=webhook_config["url"] + webhook_config["path"]
        )
    
    async def _start_polling(self) -> None:
        """Start bot in polling mode"""
        self.logger.info("Starting polling mode")
        
        # Initialize and start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            poll_interval=1.0,
            timeout=20,
            bootstrap_retries=5,
            read_timeout=30,
            connect_timeout=30
        )
        
        self.logger.info("Polling started successfully")
    
    async def _error_handler(self, update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global error handler"""
        error = context.error
        
        # Log error with context
        error_info = {
            "error": str(error),
            "error_type": type(error).__name__,
            "update_id": update.update_id if update else None,
            "user_id": update.effective_user.id if update and update.effective_user else None,
            "chat_id": update.effective_chat.id if update and update.effective_chat else None,
        }
        
        self.logger.error(f"Error in bot: {error}", extra=error_info, exc_info=True)
        
        # Send telemetry if available
        if self.telemetry:
            await self.telemetry.record_error(error, error_info)
        
        # Try to inform user about error (if update available)
        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Wystąpił błąd podczas przetwarzania polecenia. Administrator został powiadomiony."
                )
            except Exception as e:
                self.logger.error(f"Failed to send error message to user: {e}")
    
    async def _cleanup(self) -> None:
        """Clean shutdown of all components"""
        self.logger.info("Starting cleanup...")
        
        cleanup_tasks = []
        
        # Stop Telegram application
        if self.application:
            if self.application.updater and self.application.updater.running:
                cleanup_tasks.append(self.application.updater.stop())
            if self.application.running:
                cleanup_tasks.append(self.application.stop())
        
        # Stop scheduler
        if self.scheduler:
            cleanup_tasks.append(self.scheduler.shutdown())
        
        # Stop telemetry
        if self.telemetry:
            cleanup_tasks.append(self.telemetry.shutdown())
        
        # Close database connections
        if self.database:
            cleanup_tasks.append(self.database.close())
        
        # Execute all cleanup tasks
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.logger.info("Cleanup completed")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int((datetime.utcnow() - self.start_time).total_seconds()),
            "components": {}
        }
        
        # Check database
        if self.database:
            try:
                db_healthy = await self.database.health_check()
                status["components"]["database"] = {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "connected": db_healthy
                }
            except Exception as e:
                status["components"]["database"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check scheduler
        if self.scheduler:
            scheduler_running = self.scheduler.is_running()
            status["components"]["scheduler"] = {
                "status": "healthy" if scheduler_running else "unhealthy",
                "running": scheduler_running,
                "jobs_count": len(self.scheduler.get_jobs()) if scheduler_running else 0
            }
        
        # Check Telegram API
        if self.application and self.application.bot:
            try:
                bot_info = await self.application.bot.get_me()
                status["components"]["telegram"] = {
                    "status": "healthy",
                    "bot_username": bot_info.username
                }
            except Exception as e:
                status["components"]["telegram"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall status
        component_statuses = [comp.get("status") for comp in status["components"].values()]
        if "error" in component_statuses:
            status["status"] = "error"
        elif "unhealthy" in component_statuses:
            status["status"] = "degraded"
        
        return status
