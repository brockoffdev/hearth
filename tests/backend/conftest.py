"""Shared pytest fixtures for Phase 2+ backend tests.

This conftest.py is loaded by pytest before test modules are imported, so
the environment variable override below takes effect before create_app()
is called via module-level imports in test files.
"""

import os

# Disable automatic migrations during tests — each test that needs a DB
# creates its own isolated SQLite database via the db_engine fixture below.
os.environ.setdefault("HEARTH_RUN_MIGRATIONS_ON_STARTUP", "false")

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from backend.app.db.base import Base, get_session_factory


@pytest.fixture(scope="function")
def db_url(tmp_path: Path) -> str:
    """Return a per-test SQLite URL backed by a temp file.

    Using a file (not :memory:) avoids shared-cache gotchas with multiple
    async connections to the same in-memory database.
    """
    db_file = tmp_path / "hearth-test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture(scope="function")
async def db_engine(db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine, apply all model DDL, yield, then dispose."""
    engine = create_async_engine(db_url, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; roll back on teardown to keep tests isolated."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        yield session
        await session.rollback()
