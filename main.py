#!/usr/bin/env python3
"""
Telegram Bot Advanced - Main Entry Point

Production-grade Telegram bot with:
- DST-safe scheduling 
- Multi-user FSM state management
- RBAC security system
- Admin panel with inline menus
- Encrypted data storage
- Comprehensive error handling
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.core.bot_manager import BotManager
from config.settings import get_settings

def setup_logging():
    """Configure basic logging before full system init"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/startup.log')
        ]
    )

async def main():
    """Main application entry point"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        settings = get_settings()
        logger.info(f"Starting Telegram Bot Advanced in {settings.bot_mode} mode")
        
        # Create and configure bot manager
        bot_manager = BotManager(settings)
        
        # Start the bot
        await bot_manager.start()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")