"""
Database configuration and connection management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.models.database import Base
import os
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialized = False

    def initialize(self, database_url: str = None):
        """Initialize database connection."""
        if self._initialized:
            return

        if not database_url:
            # Default database URL - modify as needed
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://user:password@localhost:5432/multichain_proxy"
            )

        try:
            self.engine = create_async_engine(
                database_url,
                echo=False,  # Set to True for SQL logging
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            self._initialized = True
            logger.info("Database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def create_tables(self):
        """Create all tables."""
        if not self.engine:
            raise RuntimeError("Database not initialized")

        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")

        return self.session_factory()

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncSession:
    """Dependency for FastAPI to get database session."""
    async with db_manager.get_session() as session:
        try:
            yield session
        finally:
            await session.close()