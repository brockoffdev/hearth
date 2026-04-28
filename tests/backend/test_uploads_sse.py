"""Tests for the SSE /api/uploads/{id}/events endpoint.

Phase 3.5 architectural change: the pipeline runner is now an asyncio.Task
dispatched at POST /api/uploads time (decoupled from SSE).  The SSE endpoint
polls the Upload DB row every 0.5 s and emits events when state changes.

The old model (SSE drives the pipeline) no longer exists.  Tests in this file
verify the *polling reader* behaviour:
  - Events are emitted as the runner advances stages.
  - The terminal 'done' event closes the stream.
  - Auth / access-control paths still work.
  - Already-completed uploads short-circuit immediately.

Strategy: pipeline delays are set to 0 via env vars so the asyncio.Task
dispatched at POST time completes very quickly.  The SSE poll interval remains
at its default (0.5 s) so tests may take up to ~1.5 s each; this is acceptable
for the test suite.

Queue state is a process-level singleton — reset_queue fixture clears it
between tests to avoid leakage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sse_starlette.sse import AppStatus

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.db.models import PipelineStageDuration, Upload, User
from backend.app.main import create_app
from backend.app.uploads.pipeline import FAKE_TOTAL_CELLS, HEARTH_STAGES_ORDER
from backend.app.uploads.queue import _reset_for_tests

# ---------------------------------------------------------------------------
# Minimal fake JPEG bytes (same as test_uploads_endpoints.py)
# ---------------------------------------------------------------------------

_FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"
)


# ---------------------------------------------------------------------------
# Tiny SSE parser
# ---------------------------------------------------------------------------


async def _read_sse_events(response_stream: Response) -> list[dict[str, str]]:
    """Tiny SSE parser for tests. Returns list of {event, data} dicts.

    Reads lines from the streaming response and groups them into events.
    SSE format: one or more ``key: value`` lines followed by a blank line.
    """
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}

    async for line in response_stream.aiter_lines():
        line = line.rstrip("\r")
        if line == "":
            # Blank line separates events; flush current event if non-empty.
            if current:
                events.append(current)
                current = {}
        elif ": " in line:
            key, _, value = line.partition(": ")
            current[key] = value
        elif line.startswith(":"):
            # SSE comment — ignore.
            pass

    # Flush any trailing event (stream ended without a trailing blank line).
    if current:
        events.append(current)

    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_sse_app_status() -> None:
    """Reset sse-starlette's AppStatus between tests.

    AppStatus.should_exit_event is a module-level anyio.Event that gets bound
    to the first event loop it is used with.  pytest-asyncio creates a new
    event loop per test, so without a reset the second+ SSE tests crash with
    "RuntimeError: bound to a different event loop".
    """
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None


@pytest.fixture(autouse=True)
def reset_queue() -> None:
    """Clear process-wide queue state before each test."""
    _reset_for_tests()


@pytest.fixture
async def client(
    db_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncClient:
    """AsyncClient backed by a fresh app with isolated DB, temp data dir, and
    zero pipeline delays.

    SSE tests re-enable automatic pipeline dispatch (conftest disables it by
    default so unit tests don't auto-fire runners).  Zero delays make the
    asyncio.Task complete before the SSE poll loop has to wait long.
    """
    monkeypatch.setenv("HEARTH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HEARTH_PIPELINE_STAGE_DELAY_SECONDS", "0")
    monkeypatch.setenv("HEARTH_PIPELINE_CELL_DELAY_SECONDS", "0")
    # Re-enable auto-dispatch so POST /api/uploads fires the pipeline runner.
    monkeypatch.setenv("HEARTH_DISPATCH_RUNNER_ON_CREATE_UPLOAD", "true")
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    """client with bootstrap admin inserted."""
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _create_and_login_user(
    ac: AsyncClient,
    db_engine: AsyncEngine,
    username: str = "other",
) -> User:
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

    resp = await ac.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert resp.status_code == 200
    return user


async def _post_upload(ac: AsyncClient) -> int:
    """Upload a fake photo and return the upload id."""
    resp = await ac.post(
        "/api/uploads",
        files={"photo": ("test.jpg", _FAKE_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 201
    return int(resp.json()["id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_sse_stream_emits_stages_and_done(
    bootstrapped_client: AsyncClient,
) -> None:
    """SSE polling emits stage events and closes with a 'done' event.

    Phase 3.5 polling model: each poll emits an event when state changes.
    The runner (asyncio.Task with 0-delay) completes quickly; the SSE poller
    picks up each transition and emits a 'stage_update' event ending with
    stage='done'.

    We verify:
      - At least one non-done stage event is emitted.
      - The final event has stage='done'.
      - All event names are 'stage_update'.
    """
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            events = await _read_sse_events(resp)

    assert len(events) >= 2, f"Expected at least 2 events, got {len(events)}"

    # Last event should be 'done'.
    last_payload = json.loads(events[-1]["data"])
    assert last_payload["stage"] == "done", f"Last stage was: {last_payload['stage']}"

    # All events must be stage_update.
    for ev in events:
        assert ev.get("event") == "stage_update", f"Unexpected event type: {ev}"


async def test_sse_stream_events_include_completed_stages_and_remaining_seconds(
    bootstrapped_client: AsyncClient,
) -> None:
    """Every polled event carries completed_stages list and remaining_seconds ETA."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            events = await _read_sse_events(resp)

    payloads = [json.loads(e["data"]) for e in events if "data" in e]

    for payload in payloads:
        assert "completed_stages" in payload, (
            f"missing completed_stages on stage '{payload.get('stage')}'"
        )
        assert "remaining_seconds" in payload, (
            f"missing remaining_seconds on stage '{payload.get('stage')}'"
        )
        if payload["remaining_seconds"] is not None:
            assert payload["remaining_seconds"] >= 0


async def test_sse_updates_upload_status_to_completed(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """After consuming the full SSE stream, the Upload row is completed."""
    factory = get_session_factory(db_engine)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        # Consume the full SSE stream.
        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            await _read_sse_events(resp)

    # After stream ends, row should be completed.
    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == upload_id))
        row = result.scalar_one()

    assert row.status == "completed"
    assert row.finished_at is not None
    # Phase 3.5 runner sets this provider string.
    assert row.provider == "fake-pipeline-phase-3p5"


async def test_sse_404_for_unknown_upload(
    bootstrapped_client: AsyncClient,
) -> None:
    """SSE endpoint returns 404 for a non-existent upload id."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/uploads/999999/events")
    assert resp.status_code == 404


async def test_sse_403_for_other_users_upload(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """User B cannot stream events for User A's upload."""
    async with bootstrapped_client as ac:
        # User A (admin) creates an upload.
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        # Switch to User B.
        await ac.post("/api/auth/logout")
        await _create_and_login_user(ac, db_engine)

        resp = await ac.get(f"/api/uploads/{upload_id}/events")
    assert resp.status_code == 403


async def test_sse_requires_auth(
    bootstrapped_client: AsyncClient,
) -> None:
    """No session cookie → 401."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)
        await ac.post("/api/auth/logout")

        resp = await ac.get(f"/api/uploads/{upload_id}/events")
    assert resp.status_code == 401


async def test_sse_already_completed_emits_done_immediately(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """If the upload is already completed, a single done event is emitted.

    We patch run_pipeline_for_upload to a no-op so the background runner task
    does not race with the manual status update below.
    """
    from unittest.mock import patch

    factory = get_session_factory(db_engine)

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            upload_id = await _post_upload(ac)

            # Manually mark the upload as completed.
            async with factory() as session:
                result = await session.execute(select(Upload).where(Upload.id == upload_id))
                row = result.scalar_one()
                row.status = "completed"
                await session.commit()

            async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
                assert resp.status_code == 200
                events = await _read_sse_events(resp)

    stage_sequence = [json.loads(e["data"])["stage"] for e in events if "data" in e]
    assert stage_sequence == ["done"]


async def test_sse_event_format_uses_named_event_stage_update(
    bootstrapped_client: AsyncClient,
) -> None:
    """Raw SSE stream lines include 'event: stage_update' for every event."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        raw_lines: list[str] = []
        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                raw_lines.append(line)

    # Collect all event: lines.
    event_type_lines = [ln for ln in raw_lines if ln.startswith("event:")]
    assert len(event_type_lines) > 0, "No 'event:' lines found in SSE stream"

    # Every named event must be stage_update.
    for ln in event_type_lines:
        assert ln.strip() == "event: stage_update", f"Unexpected event type line: {ln!r}"


async def test_sse_writes_current_stage_and_completed_stages_to_db(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """After SSE stream, Upload row has current_stage='done' and all stages completed."""
    factory = get_session_factory(db_engine)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        # Consume the full SSE stream.
        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            await _read_sse_events(resp)

    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == upload_id))
        row = result.scalar_one()

    # After completion, current_stage should be 'done'.
    assert row.current_stage == "done"
    # completed_stages should be a JSON array containing all non-done stages.
    completed = json.loads(row.completed_stages)
    assert isinstance(completed, list)
    for stage in HEARTH_STAGES_ORDER:
        if stage != "done":
            assert stage in completed, f"Stage '{stage}' missing from completed_stages after run"

    # cell_progress should show the last cell.
    assert row.cell_progress == FAKE_TOTAL_CELLS
    assert row.total_cells == FAKE_TOTAL_CELLS


async def test_sse_records_pipeline_stage_duration_rows(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """After SSE stream, pipeline_stage_durations table has one row per stage."""
    factory = get_session_factory(db_engine)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            await _read_sse_events(resp)

    async with factory() as session:
        result = await session.execute(
            select(PipelineStageDuration).where(
                PipelineStageDuration.upload_id == upload_id
            )
        )
        duration_rows = list(result.scalars().all())

    # One duration row per stage (cell_progress is one stage).
    recorded_stages = {r.stage for r in duration_rows}
    assert len(duration_rows) == len(HEARTH_STAGES_ORDER), (
        f"Expected {len(HEARTH_STAGES_ORDER)} duration rows, got {len(duration_rows)}: "
        f"{recorded_stages}"
    )

    for row in duration_rows:
        assert row.duration_seconds >= 0.0, (
            f"Stage '{row.stage}' has negative duration: {row.duration_seconds}"
        )
        assert row.upload_id == upload_id


# ---------------------------------------------------------------------------
# Phase 3.5: completed_stages + remaining_seconds in SSE events (kept)
# ---------------------------------------------------------------------------


async def test_sse_events_include_completed_stages_and_remaining_seconds(
    bootstrapped_client: AsyncClient,
) -> None:
    """SSE events carry completed_stages list and remaining_seconds ETA."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        upload_id = await _post_upload(ac)

        async with ac.stream("GET", f"/api/uploads/{upload_id}/events") as resp:
            assert resp.status_code == 200
            events = await _read_sse_events(resp)

    payloads = [json.loads(e["data"]) for e in events if "data" in e]

    # Every event should carry completed_stages and remaining_seconds.
    for payload in payloads:
        assert "completed_stages" in payload, (
            f"missing completed_stages on stage '{payload.get('stage')}'"
        )
        assert "remaining_seconds" in payload, (
            f"missing remaining_seconds on stage '{payload.get('stage')}'"
        )

    # remaining_seconds should be non-negative.
    for payload in payloads:
        if payload["remaining_seconds"] is not None:
            assert payload["remaining_seconds"] >= 0
