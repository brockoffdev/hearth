"""Shared pytest fixtures for Phase 2+ backend tests.

This conftest.py is loaded by pytest before test modules are imported, so
the environment variable override below takes effect before create_app()
is called via module-level imports in test files.
"""

import asyncio
import os

# Disable automatic migrations during tests — each test that needs a DB
# creates its own isolated SQLite database via the db_engine fixture below.
os.environ.setdefault("HEARTH_RUN_MIGRATIONS_ON_STARTUP", "false")
# Disable bootstrap admin on startup; tests that need it call ensure_bootstrap_admin
# directly so they control which tests get an admin user.
os.environ.setdefault("HEARTH_BOOTSTRAP_ADMIN_ON_STARTUP", "false")
# Fixed test secret for session cookies — NEVER use this value in production.
os.environ.setdefault("HEARTH_SESSION_SECRET", "test-secret-do-not-use-in-prod")
# Disable automatic pipeline dispatch on POST /api/uploads in tests.  Tests that
# need pipeline behaviour call run_pipeline_for_upload() directly so they can
# control timing precisely.
os.environ.setdefault("HEARTH_DISPATCH_RUNNER_ON_CREATE_UPLOAD", "false")
# Disable startup recovery sweep in tests; test_pipeline_recovery.py exercises
# recover_pending_uploads() directly without going through lifespan.
os.environ.setdefault("HEARTH_RECOVER_UPLOADS_ON_STARTUP", "false")

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.uploads.pipeline import STAGE_MEDIAN_BASELINE, _stage_medians


@pytest.fixture(autouse=True)
def reset_stage_medians_to_baseline() -> None:
    """Reset the module-level _stage_medians dict to baseline before each test.

    refresh_stage_medians_from_db() mutates _stage_medians in place; without
    this reset, tests that call refresh would leak modified values into
    subsequent tests (especially across test files in a single pytest session).
    """
    _stage_medians.clear()
    _stage_medians.update(STAGE_MEDIAN_BASELINE)


def _alembic_config_for(url: str) -> Config:
    """Return an Alembic Config pointing at the repo alembic.ini, overriding the DB URL."""
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", "backend/alembic")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="function")
def db_url(tmp_path: Path) -> str:
    """Return a per-test SQLite URL backed by a temp file.

    Using a file (not :memory:) avoids shared-cache gotchas with multiple
    async connections to the same in-memory database.
    """
    db_file = tmp_path / "hearth-test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture(scope="function")
async def db_engine(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine, run real migrations, yield, then dispose.

    Bootstraps the test schema via alembic upgrade head rather than
    Base.metadata.create_all so model tests exercise the same DDL that
    production sees on first boot.  Test DBs will also contain the seeded
    family members from migration 0002.
    """
    monkeypatch.setenv("HEARTH_DATABASE_URL", db_url)
    get_settings.cache_clear()

    # Run real migrations against the test DB rather than create_all,
    # so model tests exercise the same DDL production sees on first boot.
    cfg = _alembic_config_for(db_url)
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(db_url, future=True)
    try:
        yield engine
    finally:
        await engine.dispose()
        get_settings.cache_clear()


@pytest.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; roll back on teardown to keep tests isolated."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        yield session
        await session.rollback()
