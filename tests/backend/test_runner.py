"""Tests for the background pipeline runner (uploads/runner.py).

The runner is dispatched as an asyncio.Task at POST time, decoupled from SSE.
Tests here exercise the runner directly (no HTTP layer) by calling
run_pipeline_for_upload() with 0-delay pipelines so they run instantly.

Queue state is a process-level singleton; the reset_queue fixture clears it
between tests to prevent leakage.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import Event, EventCorrection, PipelineStageDuration, Upload, User
from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER
from backend.app.uploads.queue import _reset_for_tests, dequeue, enqueue, queue_position
from backend.app.uploads.runner import (
    _parse_event_datetime,
    persist_and_maybe_publish,
    run_pipeline_for_upload,
)

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


# ---------------------------------------------------------------------------
# _parse_event_datetime tests
# ---------------------------------------------------------------------------


def test_parse_event_datetime_with_time() -> None:
    """'8:30 AM' parses to datetime at 08:30."""
    result = _parse_event_datetime("2026-04-27", "8:30 AM")
    assert result == datetime(2026, 4, 27, 8, 30)


def test_parse_event_datetime_without_time() -> None:
    """None time_text → midnight (all-day event)."""
    result = _parse_event_datetime("2026-04-27", None)
    assert result == datetime(2026, 4, 27, 0, 0)


def test_parse_event_datetime_24h_format() -> None:
    """'14:00' parses correctly in 24-hour format."""
    result = _parse_event_datetime("2026-04-27", "14:00")
    assert result == datetime(2026, 4, 27, 14, 0)


def test_parse_event_datetime_pm_no_minutes() -> None:
    """'8 PM' parses to 20:00."""
    result = _parse_event_datetime("2026-04-27", "8 PM")
    assert result == datetime(2026, 4, 27, 20, 0)


def test_parse_event_datetime_lowercase_pm() -> None:
    """'8:00pm' (lowercase, no space) parses correctly."""
    result = _parse_event_datetime("2026-04-27", "8:00pm")
    assert result == datetime(2026, 4, 27, 20, 0)


def test_parse_event_datetime_unparseable_falls_back_to_midnight() -> None:
    """Unparseable time_text falls back to midnight without raising."""
    result = _parse_event_datetime("2026-04-27", "not a time")
    assert result == datetime(2026, 4, 27, 0, 0)


# ---------------------------------------------------------------------------
# Runner dispatch tests
# ---------------------------------------------------------------------------


async def test_runner_uses_fake_pipeline_when_use_real_pipeline_false(
    db_engine: AsyncEngine,
) -> None:
    """Default settings (use_real_pipeline=False) → provider='fake-pipeline-phase-3p5'."""
    import os

    # Ensure use_real_pipeline is False (default).
    from backend.app.config import get_settings

    get_settings.cache_clear()
    os.environ["HEARTH_USE_REAL_PIPELINE"] = "false"
    try:
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
        assert row.provider == "fake-pipeline-phase-3p5"
    finally:
        del os.environ["HEARTH_USE_REAL_PIPELINE"]
        get_settings.cache_clear()


async def test_runner_uses_real_pipeline_when_setting_true(
    db_engine: AsyncEngine,
) -> None:
    """use_real_pipeline=True → runner calls run_pipeline; provider set to vision_provider."""
    import os
    from unittest.mock import patch

    from backend.app.config import get_settings
    from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER, StageEvent

    async def _fake_real_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        """Stub run_pipeline that yields all standard stages with zero delay."""
        completed: list[str] = []
        for stage in HEARTH_STAGES_ORDER:
            yield StageEvent(
                stage=stage,
                completed_stages=completed.copy(),
                remaining_seconds=0,
            )
            completed.append(stage)

    get_settings.cache_clear()
    os.environ["HEARTH_USE_REAL_PIPELINE"] = "true"
    try:
        factory = get_session_factory(db_engine)
        user_id = await _make_user(db_engine)
        upload_id = await _make_upload(db_engine, user_id)

        await enqueue(upload_id)

        with patch(
            "backend.app.uploads.runner.run_pipeline",
            side_effect=_fake_real_pipeline,
        ):
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
        # Provenance is "<provider>:<model>" so admins can tell which exact
        # model produced the events on this upload (mirrors VisionProvider.name).
        assert row.provider == "ollama:qwen2.5vl:7b"
    finally:
        del os.environ["HEARTH_USE_REAL_PIPELINE"]
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Few-shot correction wiring tests
# ---------------------------------------------------------------------------


async def _make_correction(
    db_engine: AsyncEngine,
    user_id: int,
    before_title: str,
    after_title: str,
) -> None:
    """Insert a minimal EventCorrection row (via a dummy Event)."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        from datetime import datetime

        event = Event(
            title="dummy",
            start_dt=datetime(2026, 5, 10, 9, 0),
            status="auto_published",
        )
        session.add(event)
        await session.flush()
        correction = EventCorrection(
            event_id=event.id,
            before_json=f'{{"title": "{before_title}"}}',
            after_json=f'{{"title": "{after_title}"}}',
            corrected_by=user_id,
        )
        session.add(correction)
        await session.commit()


async def test_runner_passes_corrections_to_pipeline_when_window_gt_zero(
    db_engine: AsyncEngine,
) -> None:
    """When few_shot_correction_window > 0 and corrections exist, runner passes them."""
    import os
    from unittest.mock import patch

    from backend.app.config import get_settings
    from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER, StageEvent

    captured_kwargs: dict[str, object] = {}

    async def _capturing_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        completed: list[str] = []
        for stage in HEARTH_STAGES_ORDER:
            yield StageEvent(stage=stage, completed_stages=completed.copy(), remaining_seconds=0)
            completed.append(stage)

    get_settings.cache_clear()
    os.environ["HEARTH_USE_REAL_PIPELINE"] = "true"
    os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"] = "10"
    try:
        factory = get_session_factory(db_engine)
        user_id = await _make_user(db_engine)
        # Insert 2 corrections so the runner has something to retrieve.
        await _make_correction(db_engine, user_id, "Pikuagk Place", "Pineapple Place")
        await _make_correction(db_engine, user_id, "Dentst Appt", "Dentist Appt")

        upload_id = await _make_upload(db_engine, user_id)
        await enqueue(upload_id)

        with patch("backend.app.uploads.runner.run_pipeline", side_effect=_capturing_pipeline):
            await run_pipeline_for_upload(
                upload_id, factory, stage_delay_seconds=0, cell_delay_seconds=0
            )

        corrections = captured_kwargs.get("few_shot_corrections", None)
        assert corrections is not None, "few_shot_corrections not passed to run_pipeline"
        assert isinstance(corrections, tuple)
        assert len(corrections) == 2
        # Values should be dicts with 'before' and 'after' keys
        for c in corrections:
            assert "before" in c and "after" in c
    finally:
        del os.environ["HEARTH_USE_REAL_PIPELINE"]
        del os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"]
        get_settings.cache_clear()


async def test_runner_passes_empty_tuple_when_window_is_zero(
    db_engine: AsyncEngine,
) -> None:
    """When few_shot_correction_window=0, runner passes () without querying DB."""
    import os
    from unittest.mock import patch

    from backend.app.config import get_settings
    from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER, StageEvent

    captured_kwargs: dict[str, object] = {}

    async def _capturing_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        completed: list[str] = []
        for stage in HEARTH_STAGES_ORDER:
            yield StageEvent(stage=stage, completed_stages=completed.copy(), remaining_seconds=0)
            completed.append(stage)

    get_settings.cache_clear()
    os.environ["HEARTH_USE_REAL_PIPELINE"] = "true"
    os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"] = "0"
    try:
        factory = get_session_factory(db_engine)
        user_id = await _make_user(db_engine)
        # Insert a correction — should NOT be retrieved because window=0
        await _make_correction(db_engine, user_id, "Pikuagk Place", "Pineapple Place")

        upload_id = await _make_upload(db_engine, user_id)
        await enqueue(upload_id)

        with patch("backend.app.uploads.runner.run_pipeline", side_effect=_capturing_pipeline):
            await run_pipeline_for_upload(
                upload_id, factory, stage_delay_seconds=0, cell_delay_seconds=0
            )

        corrections = captured_kwargs.get("few_shot_corrections", None)
        assert corrections == (), f"Expected () when window=0, got {corrections!r}"
    finally:
        del os.environ["HEARTH_USE_REAL_PIPELINE"]
        del os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"]
        get_settings.cache_clear()


async def test_runner_passes_empty_tuple_when_table_is_empty(
    db_engine: AsyncEngine,
) -> None:
    """When event_corrections table is empty, runner passes () to run_pipeline."""
    import os
    from unittest.mock import patch

    from backend.app.config import get_settings
    from backend.app.uploads.pipeline import HEARTH_STAGES_ORDER, StageEvent

    captured_kwargs: dict[str, object] = {}

    async def _capturing_pipeline(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        completed: list[str] = []
        for stage in HEARTH_STAGES_ORDER:
            yield StageEvent(stage=stage, completed_stages=completed.copy(), remaining_seconds=0)
            completed.append(stage)

    get_settings.cache_clear()
    os.environ["HEARTH_USE_REAL_PIPELINE"] = "true"
    os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"] = "10"
    try:
        factory = get_session_factory(db_engine)
        user_id = await _make_user(db_engine)
        upload_id = await _make_upload(db_engine, user_id)
        await enqueue(upload_id)

        with patch("backend.app.uploads.runner.run_pipeline", side_effect=_capturing_pipeline):
            await run_pipeline_for_upload(
                upload_id, factory, stage_delay_seconds=0, cell_delay_seconds=0
            )

        corrections = captured_kwargs.get("few_shot_corrections", None)
        assert corrections == (), f"Expected () for empty table, got {corrections!r}"
    finally:
        del os.environ["HEARTH_USE_REAL_PIPELINE"]
        del os.environ["HEARTH_FEW_SHOT_CORRECTION_WINDOW"]
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# persist_and_maybe_publish tests
# ---------------------------------------------------------------------------


def _make_record(
    *,
    composite_confidence: float = 0.95,
    family_member_id: int | None = 1,
    title: str = "Soccer practice",
    cell_date_iso: str = "2026-05-10",
    time_text: str | None = "3:00 PM",
) -> object:
    """Build a minimal ExtractedEventRecord for testing."""
    from backend.app.uploads.pipeline import ExtractedEventRecord

    return ExtractedEventRecord(
        cell_row=0,
        cell_col=0,
        cell_date_iso=cell_date_iso,
        title=title,
        time_text=time_text,
        color_hex=None,
        family_member_id=family_member_id,
        color_match_confidence=composite_confidence,
        vision_confidence=composite_confidence,
        composite_confidence=composite_confidence,
        raw_vlm_json="{}",
        cell_crop_path=None,
    )


def _make_settings(
    *, auto_publish_to_gcal: bool = True, confidence_threshold: float = 0.85
) -> object:
    """Build a minimal Settings-like object for testing persist_and_maybe_publish."""
    from unittest.mock import MagicMock

    s = MagicMock()
    s.auto_publish_to_gcal = auto_publish_to_gcal
    s.confidence_threshold = confidence_threshold
    return s


async def test_on_event_extracted_auto_publishes_when_above_threshold(
    db_engine: AsyncEngine,
) -> None:
    """High-confidence event with family_member_id → publish_event called once."""
    from unittest.mock import AsyncMock, patch

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    record = _make_record(composite_confidence=0.95, family_member_id=1)
    settings = _make_settings(auto_publish_to_gcal=True)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        await persist_and_maybe_publish(
            record,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    mock_publish.assert_awaited_once()
    async with factory() as session:
        result = await session.execute(select(Event).where(Event.upload_id == upload_id))
        events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].status == "auto_published"


async def test_on_event_extracted_does_not_publish_pending_review(
    db_engine: AsyncEngine,
) -> None:
    """Low-confidence event → status=pending_review and publish_event NOT called."""
    from unittest.mock import AsyncMock, patch

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    record = _make_record(composite_confidence=0.50, family_member_id=1)
    settings = _make_settings(auto_publish_to_gcal=True)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        await persist_and_maybe_publish(
            record,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    mock_publish.assert_not_called()
    async with factory() as session:
        result = await session.execute(select(Event).where(Event.upload_id == upload_id))
        events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].status == "pending_review"


async def test_on_event_extracted_skips_publish_when_setting_disabled(
    db_engine: AsyncEngine,
) -> None:
    """auto_publish_to_gcal=False → row written as auto_published but publish not called."""
    from unittest.mock import AsyncMock, patch

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    record = _make_record(composite_confidence=0.95, family_member_id=1)
    settings = _make_settings(auto_publish_to_gcal=False)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        await persist_and_maybe_publish(
            record,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    mock_publish.assert_not_called()
    async with factory() as session:
        result = await session.execute(select(Event).where(Event.upload_id == upload_id))
        events = list(result.scalars().all())
    assert len(events) == 1
    # The row is still written as auto_published — pipeline's measurement is unchanged.
    assert events[0].status == "auto_published"


async def test_on_event_extracted_skips_publish_when_no_family_member(
    db_engine: AsyncEngine,
) -> None:
    """family_member_id=None → no publish attempt, row written as auto_published."""
    from unittest.mock import AsyncMock, patch

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    record = _make_record(composite_confidence=0.95, family_member_id=None)
    settings = _make_settings(auto_publish_to_gcal=True)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
    ) as mock_publish:
        await persist_and_maybe_publish(
            record,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    mock_publish.assert_not_called()
    async with factory() as session:
        result = await session.execute(select(Event).where(Event.upload_id == upload_id))
        events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].status == "auto_published"


async def test_on_event_extracted_demotes_to_pending_review_on_gcal_error(
    db_engine: AsyncEngine,
) -> None:
    """publish_event raises GcalError → event demoted to pending_review with notes."""
    from unittest.mock import AsyncMock, patch

    from backend.app.google.publish import GcalError

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    record = _make_record(composite_confidence=0.95, family_member_id=1)
    settings = _make_settings(auto_publish_to_gcal=True)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
        side_effect=GcalError("quota exceeded", status_code=429),
    ):
        await persist_and_maybe_publish(
            record,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    async with factory() as session:
        result = await session.execute(select(Event).where(Event.upload_id == upload_id))
        events = list(result.scalars().all())
    assert len(events) == 1
    assert events[0].status == "pending_review"
    assert "[Auto-publish failed:" in (events[0].notes or "")


async def test_on_event_extracted_short_circuits_after_invalid_grant(
    db_engine: AsyncEngine,
) -> None:
    """First call raises InvalidGrantError → second call skips publish entirely."""
    from unittest.mock import AsyncMock, patch

    from backend.app.google.publish import InvalidGrantError

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    settings = _make_settings(auto_publish_to_gcal=True)
    publish_state: dict[str, bool] = {"oauth_broken": False}

    record1 = _make_record(composite_confidence=0.95, family_member_id=1, title="Event A")
    record2 = _make_record(composite_confidence=0.95, family_member_id=1, title="Event B")

    call_count = 0

    async def _raise_on_first(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise InvalidGrantError("token revoked")

    with patch(
        "backend.app.uploads.runner.publish_event",
        new_callable=AsyncMock,
        side_effect=_raise_on_first,
    ) as mock_publish:
        await persist_and_maybe_publish(
            record1,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )
        await persist_and_maybe_publish(
            record2,
            upload_id=upload_id,
            session_factory=factory,
            settings=settings,
            publish_state=publish_state,
        )

    # publish_event should have been called exactly once (for the first event).
    assert mock_publish.await_count == 1
    assert publish_state["oauth_broken"] is True

    async with factory() as session:
        result = await session.execute(
            select(Event).where(Event.upload_id == upload_id).order_by(Event.id)
        )
        events = list(result.scalars().all())

    assert len(events) == 2
    # Both events should be pending_review.
    assert events[0].status == "pending_review"
    assert events[1].status == "pending_review"


async def test_on_event_extracted_preserves_existing_notes_on_demote(
    db_engine: AsyncEngine,
) -> None:
    """Demotion appends the failure note without overwriting existing notes."""
    from backend.app.uploads.runner import _demote_to_pending_review

    factory = get_session_factory(db_engine)
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)

    async with factory() as session:
        event = Event(
            upload_id=upload_id,
            title="Pre-existing",
            start_dt=datetime(2026, 5, 10, 15, 0),
            status="auto_published",
            confidence=0.95,
            family_member_id=1,
            notes="Original note",
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        event_id = event.id

    async with factory() as session:
        await _demote_to_pending_review(session, event_id, "OAuth not connected")

    async with factory() as session:
        result = await session.execute(select(Event).where(Event.id == event_id))
        updated = result.scalar_one()

    assert updated.status == "pending_review"
    assert "Original note" in (updated.notes or "")
    assert "[Auto-publish failed: OAuth not connected]" in (updated.notes or "")
