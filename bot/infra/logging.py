"""
Logging Setup - Structured Logging Configuration

Handles:
- Structured logging with rotation
- Multiple output formats
- Performance logging
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any

import structlog
from config.settings import Settings

def setup_logging(settings: Settings):
    """Setup structured logging with rotation"""
    
    # Ensure log directory exists
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure stdlib logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.value),
        format="%(message)s",
        stream=sys.stdout,
    )
    
    # Add rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_file,
        maxBytes=settings.log_max_size,
        backupCount=settings.log_backup_count,
        encoding="utf-8"
    )
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    
    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.debug_mode else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger on first use=True,
    )
