"""Tests for recover_pending_uploads (startup recovery sweep).

Phase 4 Task H: when the server boots, uploads stranded in 'queued' or
'processing' status (from a prior crash) are reset and re-enqueued.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import Upload, User
from backend.app.uploads.queue import _reset_for_tests
from backend.app.uploads.runner import recover_pending_uploads

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


async def _make_upload(
    db_engine: AsyncEngine,
    user_id: int,
    *,
    status: str = "queued",
    current_stage: str = "queued",
    completed_stages: str = "[]",
    cell_progress: int | None = None,
    total_cells: int | None = None,
    error: str | None = None,
) -> int:
    """Insert an Upload row with the given state and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        upload = Upload(
            user_id=user_id,
            image_path="uploads/fake.jpg",
            status=status,
            current_stage=current_stage,
            completed_stages=completed_stages,
            cell_progress=cell_progress,
            total_cells=total_cells,
            error=error,
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
        return upload.id


async def _fetch_upload(db_engine: AsyncEngine, upload_id: int) -> Upload:
    """Return a fresh Upload row from the DB."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        row = await session.get(Upload, upload_id)
        assert row is not None, f"Upload {upload_id} not found"
        return row


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


@pytest.mark.asyncio
async def test_recover_pending_uploads_resets_processing_to_queued(
    db_engine: AsyncEngine,
) -> None:
    """A row with status='processing' is reset to status='queued', current_stage='queued'."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(
        db_engine,
        user_id,
        status="processing",
        current_stage="preprocessing",
        completed_stages='["received"]',
    )

    factory = get_session_factory(db_engine)

    with (
        patch("backend.app.uploads.runner.enqueue", new_callable=AsyncMock) as mock_enqueue,
        patch(
            "backend.app.uploads.runner.run_pipeline_for_upload", new_callable=AsyncMock
        ) as mock_runner,
    ):
        count = await recover_pending_uploads(factory)

    assert count == 1
    mock_enqueue.assert_awaited_once_with(upload_id)
    mock_runner.assert_called_once()

    row = await _fetch_upload(db_engine, upload_id)
    assert row.status == "queued"
    assert row.current_stage == "queued"
    assert row.completed_stages == "[]"


@pytest.mark.asyncio
async def test_recover_pending_uploads_resets_queued_too(
    db_engine: AsyncEngine,
) -> None:
    """A row already in status='queued' stays 'queued' but the runner is dispatched."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id, status="queued")

    factory = get_session_factory(db_engine)

    with (
        patch("backend.app.uploads.runner.enqueue", new_callable=AsyncMock) as mock_enqueue,
        patch(
            "backend.app.uploads.runner.run_pipeline_for_upload", new_callable=AsyncMock
        ) as mock_runner,
    ):
        count = await recover_pending_uploads(factory)

    assert count == 1
    mock_enqueue.assert_awaited_once_with(upload_id)
    mock_runner.assert_called_once()

    row = await _fetch_upload(db_engine, upload_id)
    assert row.status == "queued"
    assert row.current_stage == "queued"


@pytest.mark.asyncio
async def test_recover_pending_uploads_ignores_terminal_states(
    db_engine: AsyncEngine,
) -> None:
    """Rows with status='completed' or 'failed' are not touched."""
    user_id = await _make_user(db_engine)
    completed_id = await _make_upload(db_engine, user_id, status="completed", current_stage="done")
    failed_id = await _make_upload(
        db_engine,
        user_id,
        status="failed",
        current_stage="preprocessing",
        error="oops",
    )

    factory = get_session_factory(db_engine)

    with (
        patch("backend.app.uploads.runner.enqueue", new_callable=AsyncMock) as mock_enqueue,
        patch(
            "backend.app.uploads.runner.run_pipeline_for_upload", new_callable=AsyncMock
        ),
    ):
        count = await recover_pending_uploads(factory)

    assert count == 0
    mock_enqueue.assert_not_awaited()

    completed_row = await _fetch_upload(db_engine, completed_id)
    assert completed_row.status == "completed"

    failed_row = await _fetch_upload(db_engine, failed_id)
    assert failed_row.status == "failed"
    assert failed_row.error == "oops"


@pytest.mark.asyncio
async def test_recover_pending_uploads_returns_count(
    db_engine: AsyncEngine,
) -> None:
    """Returns the exact number of uploads re-enqueued."""
    user_id = await _make_user(db_engine)
    await _make_upload(db_engine, user_id, status="queued")
    await _make_upload(db_engine, user_id, status="processing", current_stage="model_loading")
    await _make_upload(db_engine, user_id, status="completed", current_stage="done")

    factory = get_session_factory(db_engine)

    with (
        patch("backend.app.uploads.runner.enqueue", new_callable=AsyncMock),
        patch("backend.app.uploads.runner.run_pipeline_for_upload", new_callable=AsyncMock),
    ):
        count = await recover_pending_uploads(factory)

    assert count == 2


@pytest.mark.asyncio
async def test_recover_pending_uploads_clears_partial_progress(
    db_engine: AsyncEngine,
) -> None:
    """A row mid-pipeline (cell_progress=12) is fully reset on recovery."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(
        db_engine,
        user_id,
        status="processing",
        current_stage="cell_progress",
        completed_stages='["received","preprocessing","grid_detected","model_loading"]',
        cell_progress=12,
        total_cells=35,
        error="partial note",
    )

    factory = get_session_factory(db_engine)

    with (
        patch("backend.app.uploads.runner.enqueue", new_callable=AsyncMock),
        patch("backend.app.uploads.runner.run_pipeline_for_upload", new_callable=AsyncMock),
    ):
        await recover_pending_uploads(factory)

    row = await _fetch_upload(db_engine, upload_id)
    assert row.status == "queued"
    assert row.current_stage == "queued"
    assert row.completed_stages == "[]"
    assert row.cell_progress is None
    assert row.total_cells is None
    assert row.error is None
    assert row.finished_at is None
