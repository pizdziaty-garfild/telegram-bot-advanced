"""
Database Manager - Async SQLAlchemy Management

Handles:
- Database connections and sessions
- Migration management
- Health checks
"""

import logging
from typing import AsyncGenerator, Dict, Any
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from bot.domain.models import Base

class DatabaseManager:
    """Async database manager with connection pooling"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize database engine and session factory"""
        try:
            self.engine = create_async_engine(
                self.config["url"],
                echo=self.config.get("echo", False),
                **{k: v for k, v in self.config.items() if k not in ["url", "echo"]}
            )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup"""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")
