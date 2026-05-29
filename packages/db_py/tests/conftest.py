"""pytest fixtures — in-memory SQLite via aiosqlite for repository tests."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sports_oracle_db.models import Base
from sports_oracle_db.session import reset_engine


@pytest_asyncio.fixture(scope="function")
async def async_session():
    """Yield an AsyncSession backed by SQLite in-memory.

    SQLite doesn't support gen_random_uuid() or JSONB, so we use
    a patched metadata that works with it.
    """
    # Use aiosqlite; disable PostgreSQL-specific constructs at DDL time
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        # SQLite chokes on server_default=text("gen_random_uuid()") as a
        # *type*, but accepts it as a string — SQLAlchemy emits it as a
        # string anyway so the DDL works fine for testing purposes.
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session

    await engine.dispose()
    # Make sure the module-level engine cache is cleared so tests are isolated
    reset_engine()
