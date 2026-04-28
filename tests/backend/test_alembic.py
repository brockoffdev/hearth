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
from pathlib import Path

import pytest
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


async def test_alembic_upgrade_downgrade_roundtrip(
    db_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full upgrade → verify → downgrade → verify cycle."""
    # Point env.py at the test DB by overriding the environment variable.
    # monkeypatch.setenv restores the original value automatically on test exit,
    # including on failure — no manual finally block needed for env restoration.
    monkeypatch.setenv("HEARTH_DATABASE_URL", db_url)
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

            # Verify Phase 4 Task A tables are present.
            phase4_tables = {"events", "event_corrections"}
            assert phase4_tables.issubset(
                set(table_names)
            ), f"Missing Phase 4 tables: {phase4_tables - set(table_names)}"

            # Spot-check events columns.
            events_cols = await conn.run_sync(
                lambda sync_conn: {
                    c["name"] for c in inspect(sync_conn).get_columns("events")
                }
            )
            required_event_cols = {
                "id",
                "upload_id",
                "family_member_id",
                "title",
                "start_dt",
                "end_dt",
                "all_day",
                "location",
                "notes",
                "confidence",
                "status",
                "google_event_id",
                "cell_crop_path",
                "raw_vlm_json",
                "created_at",
                "updated_at",
                "published_at",
            }
            assert required_event_cols.issubset(events_cols), (
                f"Missing events columns: {required_event_cols - events_cols}"
            )

            # Spot-check event_corrections columns.
            corrections_cols = await conn.run_sync(
                lambda sync_conn: {
                    c["name"]
                    for c in inspect(sync_conn).get_columns("event_corrections")
                }
            )
            required_correction_cols = {
                "id",
                "event_id",
                "before_json",
                "after_json",
                "cell_crop_path",
                "corrected_by",
                "corrected_at",
            }
            assert required_correction_cols.issubset(corrections_cols), (
                f"Missing event_corrections columns: "
                f"{required_correction_cols - corrections_cols}"
            )

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
                "Izzy",
                "Ellie",
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
        # monkeypatch handles env restoration; keep cache_clear as defensive measure.
        get_settings.cache_clear()
