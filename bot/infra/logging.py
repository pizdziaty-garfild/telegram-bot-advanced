import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from config.settings import Settings


def setup_logging(settings: Optional[Settings] = None) -> None:
    """Configure application logging with console + rotating file handler.

    - Reads level/path from Settings when provided
    - Creates logs directory if missing
    """
    if settings is None:
        settings = Settings()

    level = getattr(logging, str(settings.log_level), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates on hot-reload
    logger.handlers.clear()

    # Ensure logs directory
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler
    fh = RotatingFileHandler(
        log_path,
        maxBytes=int(settings.log_max_size),
        backupCount=int(settings.log_backup_count),
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logging.getLogger(__name__).info("Logging configured: level=%s, file=%s", level, log_path)
