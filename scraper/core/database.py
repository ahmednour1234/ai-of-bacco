"""
scraper/core/database.py
-------------------------
Separate SQLAlchemy engine and session factory for the scraper database.

This is completely isolated from the main app database — different engine,
different session factory, different DeclarativeBase. Scraper models must
inherit from ScraperBase, NOT from app.core.database.Base.

Usage (FastAPI / async context):
    async with ScraperSessionLocal() as session:
        ...

Usage (Celery task / sync context):
    asyncio.run(some_async_func())
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── Engine ─────────────────────────────────────────────────────────────────────
scraper_engine = create_async_engine(
    settings.SCRAPER_DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# ── Session factory ────────────────────────────────────────────────────────────
ScraperSessionLocal = async_sessionmaker(
    bind=scraper_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Declarative base (isolated from main app) ──────────────────────────────────
class ScraperBase(DeclarativeBase):
    """
    SQLAlchemy declarative base for ALL scraper ORM models.
    Completely separate from app.core.database.Base so that
    alembic autogenerate does not mix scraper tables with main tables.
    """


# ── Async session dependency ───────────────────────────────────────────────────
async def get_scraper_db() -> AsyncGenerator[AsyncSession, None]:
    """Async session dependency for FastAPI or manual use."""
    async with ScraperSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
