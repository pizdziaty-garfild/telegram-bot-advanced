"""Alembic environment configuration (robust to module path changes)

This env.py is designed to work out of the box in venv/Windows by:
- Ensuring project root is on sys.path
- Using Settings() to get DB URL
- Falling back gracefully when Base cannot be imported (scripted migrations)
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# --- Ensure project root on PYTHONPATH ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- Try to import Base; fall back to None (scripted migrations) ---
Base = None
try:
    # Preferred locations (adjust if models are moved)
    try:
        from bot.infra.database import Base  # if Base is exported here
    except Exception:
        from bot.domain.models import Base  # legacy path
except Exception:
    Base = None

# Settings for DB URL
try:
    from config.settings import Settings
except Exception:
    Settings = None

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata (None => use fully scripted migrations only)
if Base is not None:
    target_metadata = Base.metadata
else:
    target_metadata = None


def get_database_url():
    """Get database URL from settings or environment"""
    # Prefer Settings if available
    if Settings is not None:
        try:
            settings = Settings()
            if getattr(settings, "database_url", None):
                return settings.database_url
        except Exception:
            pass
    # Fallback to env var or default sqlite
    return os.getenv("DATABASE_URL", "sqlite:///./data/bot.db")


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
