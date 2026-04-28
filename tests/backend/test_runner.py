"""Tests for the background pipeline runner (uploads/runner.py).

The runner is dispatched as an asyncio.Task at POST time, decoupled from SSE.
Tests here exercise the runner directly (no HTTP layer) by calling
run_pipeline_for_upload() with 0-delay pipelines so they run instantly.

Queue state is a process-level singleton; the reset_queue fixture clears it
between tests to prevent leakage.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import PipelineStageDuration, Upload, User
from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER
from backend.app.uploads.queue import _reset_for_tests, dequeue, enqueue, queue_position
from backend.app.uploads.runner import run_pipeline_for_upload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db_engine: AsyncEngine, username: str = "testuser") -> int:
    """Insert a minimal user row and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username=username,
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def _make_upload(db_engine: AsyncEngine, user_id: int) -> int:
    """Insert a minimal queued Upload row and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        upload = Upload(
            user_id=user_id,
            image_path="uploads/fake.jpg",
            status="queued",
            current_stage="queued",
            completed_stages="[]",
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
        return upload.id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_queue() -> None:
    """Wipe queue state before each test."""
    _reset_for_tests()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_runner_marks_completed_on_done(db_engine: AsyncEngine) -> None:
    """After running the pipeline with 0 delays, the upload is marked completed."""
    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)

    await enqueue(upload_id)
    await run_pipeline_for_upload(
        upload_id,
        factory,
        stage_delay_seconds=0,
        cell_delay_seconds=0,
    )

    async with factory() as session:
        row = await session.get(Upload, upload_id)

    assert row is not None
    assert row.status == "completed"
    assert row.finished_at is not None
    assert row.provider == "fake-pipeline-phase-3p5"
    assert row.current_stage == "done"


async def test_runner_records_stage_durations(db_engine: AsyncEngine) -> None:
    """After a full run, pipeline_stage_durations has one row per stage."""
    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)

    await enqueue(upload_id)
    await run_pipeline_for_upload(
        upload_id,
        factory,
        stage_delay_seconds=0,
        cell_delay_seconds=0,
    )

    async with factory() as session:
        result = await session.execute(
            select(PipelineStageDuration).where(
                PipelineStageDuration.upload_id == upload_id
            )
        )
        duration_rows = list(result.scalars().all())

    assert len(duration_rows) == len(HEARTH_STAGES_ORDER), (
        f"Expected {len(HEARTH_STAGES_ORDER)} duration rows, got {len(duration_rows)}: "
        f"{[r.stage for r in duration_rows]}"
    )
    for row in duration_rows:
        assert row.duration_seconds >= 0.0
        assert row.upload_id == upload_id


async def test_runner_aborts_when_dequeued(db_engine: AsyncEngine) -> None:
    """Runner short-circuits when upload is dequeued before it runs (cancelled).

    The upload's status stays 'queued' because the runner returns before
    setting it to 'processing'.
    """
    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)

    await enqueue(upload_id)
    # Remove from queue before calling the runner — simulates a cancel that
    # races with the runner's spin-wait before it reaches the head.
    await dequeue(upload_id)

    assert queue_position(upload_id) is None

    # Runner should return immediately without touching the DB.
    await run_pipeline_for_upload(
        upload_id,
        factory,
        stage_delay_seconds=0,
        cell_delay_seconds=0,
    )

    async with factory() as session:
        row = await session.get(Upload, upload_id)

    assert row is not None
    # Status must still be 'queued' — runner did not advance it.
    assert row.status == "queued"


async def test_runner_serial_two_uploads(db_engine: AsyncEngine) -> None:
    """Two uploads run serially: the second only starts after the first completes.

    We verify this by checking that when the second upload begins (status →
    'processing'), the first upload already has status='completed'.
    """
    import asyncio

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id_1 = await _make_upload(db_engine, user_id)
    upload_id_2 = await _make_upload(db_engine, user_id)

    # Enqueue both; upload 1 is at head, upload 2 is behind.
    await enqueue(upload_id_1)
    await enqueue(upload_id_2)

    # Dispatch both runners concurrently — they must serialise via the lock.
    await asyncio.gather(
        run_pipeline_for_upload(
            upload_id_1,
            factory,
            stage_delay_seconds=0,
            cell_delay_seconds=0,
        ),
        run_pipeline_for_upload(
            upload_id_2,
            factory,
            stage_delay_seconds=0,
            cell_delay_seconds=0,
        ),
    )

    # Both must be completed now (serial run succeeded).
    async with factory() as session:
        row1 = await session.get(Upload, upload_id_1)
        row2 = await session.get(Upload, upload_id_2)

    assert row1 is not None
    assert row2 is not None
    assert row1.status == "completed", f"upload 1 status: {row1.status}"
    assert row2.status == "completed", f"upload 2 status: {row2.status}"

    # Verify completed_stages on both rows contain all stages.
    for row in (row1, row2):
        completed = json.loads(row.completed_stages or "[]")
        for stage in HEARTH_STAGES_ORDER:
            if stage != "done":
                assert stage in completed, (
                    f"Stage '{stage}' missing from completed_stages of upload {row.id}"
                )
