"""
Database Configuration
تنظیمات دیتابیس - SQLite با async support
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings
from pathlib import Path
import os


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


# Ensure data directory exists
db_path = Path(settings.DATABASE_PATH)
os.makedirs(db_path.parent, exist_ok=True)

# Create async engine
engine = create_async_engine(
    f"sqlite+aiosqlite:///{db_path}",
    echo=settings.DEBUG,
    future=True
)

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    """Dependency for getting database session"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
