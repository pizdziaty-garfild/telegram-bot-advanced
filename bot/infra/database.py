import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from config.settings import Settings

Base = declarative_base()
logger = logging.getLogger(__name__)


@dataclass
class DBConfig:
    url: str
    echo: bool = False
    pool_size: int = 10


class DatabaseManager:
    """Async SQLAlchemy database manager with session factory and lifecycle hooks"""

    def __init__(self, config: DBConfig | dict | None = None):
        if config is None:
            settings = Settings()
            self.config = DBConfig(
                url=settings.database_url,
                echo=bool(getattr(settings, "database_echo", False)),
                pool_size=int(getattr(settings, "database_pool_size", 10)),
            )
        elif isinstance(config, dict):
            self.config = DBConfig(**config)
        else:
            self.config = config

        self.engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def get_db_config(self) -> DBConfig:
        return self.config

    async def initialize(self) -> None:
        """Create async engine and session factory"""
        if self.engine is not None:
            return

        # Normalize SQLite URL to async+aiosqlite when needed
        db_url = self.config.url
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite+aiosqlite:///"):
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

        self.engine = create_async_engine(
            db_url,
            echo=self.config.echo,
            pool_size=self.config.pool_size if not db_url.startswith("sqlite+") else None,
        )
        self._session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        logger.info("Database initialized: %s", db_url)

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self._session_factory = None
            logger.info("Database engine disposed")
