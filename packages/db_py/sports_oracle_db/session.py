"""Async SQLAlchemy engine, session factory, and helpers."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sports_oracle_db.models import Base

# ---------------------------------------------------------------------------
# Engine / sessionmaker (module-level singletons, lazily initialised)
# ---------------------------------------------------------------------------

_engine: Optional[AsyncEngine] = None
_async_session: Optional[async_sessionmaker[AsyncSession]] = None


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Expected a postgresql+asyncpg://... URL."
        )
    return url


def get_engine(database_url: Optional[str] = None) -> AsyncEngine:
    """Return (and lazily create) the module-level async engine."""
    global _engine
    if _engine is None:
        url = database_url or _get_database_url()
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _engine


def get_session_factory(database_url: Optional[str] = None) -> async_sessionmaker[AsyncSession]:
    """Return (and lazily create) the module-level async session factory."""
    global _async_session
    if _async_session is None:
        engine = get_engine(database_url)
        _async_session = async_sessionmaker(engine, expire_on_commit=False)
    return _async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional async session."""
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session


async def init_models(database_url: Optional[str] = None) -> None:
    """Create all tables (useful for tests / local dev without Alembic).

    WARNING: in production prefer Alembic migrations instead.
    """
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_models(database_url: Optional[str] = None) -> None:
    """Drop all tables — intended for test teardown only."""
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def reset_engine() -> None:
    """Discard the cached engine/session-factory (for testing)."""
    global _engine, _async_session
    _engine = None
    _async_session = None
