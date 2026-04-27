"""Regression test: alembic upgrade head / downgrade base round-trip.

Verifies that:
- upgrade head creates all 4 expected tables
- the seed migration inserts exactly 5 family member rows
- downgrade base removes all tables

Uses Alembic's programmatic API against a fresh per-test SQLite file.

NOTE: alembic command.upgrade/downgrade are synchronous and call
asyncio.run() internally (via env.py). They must NOT be called from
within a running event loop — use asyncio.to_thread to offload them.
"""

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.config import get_settings


def _alembic_cfg() -> Config:
    """Return an Alembic Config pointing at the repo alembic.ini."""
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", "backend/alembic")
    return cfg


async def test_alembic_upgrade_downgrade_roundtrip(db_url: str) -> None:
    """Full upgrade → verify → downgrade → verify cycle."""
    # Point env.py at the test DB by overriding the environment variable.
    os.environ["HEARTH_DATABASE_URL"] = db_url
    # Clear the lru_cache so Settings picks up the overridden env var.
    get_settings.cache_clear()

    try:
        cfg = _alembic_cfg()

        # --- upgrade head ---
        # Must run in a thread — alembic calls asyncio.run() internally.
        await asyncio.to_thread(command.upgrade, cfg, "head")

        engine = create_async_engine(db_url, echo=False, future=True)
        async with engine.connect() as conn:
            # Verify tables exist via sync inspection.
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            expected_tables = {"users", "family_members", "oauth_tokens", "settings"}
            assert expected_tables.issubset(
                set(table_names)
            ), f"Missing tables: {expected_tables - set(table_names)}"

            # Verify seed data: exactly 5 family members in correct order.
            rows = (
                await conn.execute(
                    text("SELECT name, sort_order FROM family_members ORDER BY sort_order")
                )
            ).fetchall()
            assert len(rows) == 5, f"Expected 5 family members, got {len(rows)}"
            names = [r[0] for r in rows]
            assert names == [
                "Bryant",
                "Danielle",
                "Isabella",
                "Eliana",
                "Family",
            ], f"Unexpected family member names/order: {names}"

        await engine.dispose()

        # --- downgrade base ---
        await asyncio.to_thread(command.downgrade, cfg, "base")

        engine2 = create_async_engine(db_url, echo=False, future=True)
        async with engine2.connect() as conn:
            remaining = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            # The alembic_version table may still exist; exclude it.
            data_tables = {t for t in remaining if t != "alembic_version"}
            assert data_tables == set(), f"Tables remain after downgrade: {data_tables}"

        await engine2.dispose()

    finally:
        # Restore settings state so other tests are unaffected.
        os.environ.pop("HEARTH_DATABASE_URL", None)
        get_settings.cache_clear()
