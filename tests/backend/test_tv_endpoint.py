"""Tests for GET /api/tv/snapshot — anonymous TV snapshot endpoint."""

from __future__ import annotations

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.db.base import get_session_factory
from backend.app.db.models import Event, FamilyMember
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_engine: AsyncEngine) -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def seeded_client(db_engine: AsyncEngine, client: AsyncClient) -> AsyncClient:
    """Client with seeded family members (via bootstrap migrations) and test events."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        members_result = await session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(FamilyMember)
        )
        members = list(members_result.scalars().all())
        fm_id = members[0].id if members else None

        now = datetime(2026, 4, 28, 9, 0, 0)
        later = datetime(2026, 4, 28, 15, 0, 0)
        far = datetime(2026, 5, 10, 10, 0, 0)

        session.add_all([
            Event(
                title="Morning standup",
                start_dt=now,
                end_dt=None,
                all_day=False,
                status="published",
                confidence=1.0,
                family_member_id=fm_id,
            ),
            Event(
                title="Afternoon meeting",
                start_dt=later,
                end_dt=None,
                all_day=False,
                status="auto_published",
                confidence=0.9,
                family_member_id=None,
            ),
            Event(
                title="Future event",
                start_dt=far,
                end_dt=None,
                all_day=True,
                status="pending_review",
                confidence=0.8,
                family_member_id=fm_id,
            ),
            Event(
                title="Rejected event",
                start_dt=now,
                end_dt=None,
                all_day=False,
                status="rejected",
                confidence=1.0,
                family_member_id=None,
            ),
            Event(
                title="Superseded event",
                start_dt=later,
                end_dt=None,
                all_day=False,
                status="superseded",
                confidence=1.0,
                family_member_id=None,
            ),
        ])
        await session.commit()
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tv_snapshot_returns_events_and_family(
    seeded_client: AsyncClient,
) -> None:
    """GET /api/tv/snapshot returns family_members, events, and server_time."""
    async with seeded_client as ac:
        resp = await ac.get("/api/tv/snapshot")

    assert resp.status_code == 200
    body = resp.json()

    assert "family_members" in body
    assert "events" in body
    assert "server_time" in body

    assert len(body["family_members"]) > 0
    assert len(body["events"]) == 3  # morning + afternoon + future; not rejected/superseded

    for member in body["family_members"]:
        assert "id" in member
        assert "name" in member
        assert "color_hex" in member

    for event in body["events"]:
        assert "id" in event
        assert "title" in event
        assert "start_dt" in event
        assert "all_day" in event


async def test_tv_snapshot_excludes_rejected_and_superseded(
    seeded_client: AsyncClient,
) -> None:
    """Events with status 'rejected' or 'superseded' are not included."""
    async with seeded_client as ac:
        resp = await ac.get("/api/tv/snapshot")

    assert resp.status_code == 200
    titles = [e["title"] for e in resp.json()["events"]]
    assert "Rejected event" not in titles
    assert "Superseded event" not in titles
    assert "Morning standup" in titles
    assert "Afternoon meeting" in titles
    assert "Future event" in titles


async def test_tv_snapshot_does_not_require_auth(
    client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/tv/snapshot returns 200 without any session cookie."""
    async with client as ac:
        resp = await ac.get("/api/tv/snapshot")
    assert resp.status_code == 200


async def test_tv_snapshot_omits_sensitive_fields(
    seeded_client: AsyncClient,
) -> None:
    """Response JSON must not contain internal fields never meant for the TV."""
    async with seeded_client as ac:
        resp = await ac.get("/api/tv/snapshot")

    assert resp.status_code == 200
    raw = resp.text

    for field in ("notes", "confidence", "raw_vlm_json", "cell_crop_path", "google_event_id"):
        assert field not in raw, f"Sensitive field '{field}' found in TV snapshot response"


async def test_tv_snapshot_sorts_events_by_start_dt(
    seeded_client: AsyncClient,
) -> None:
    """Events are returned sorted ascending by start_dt."""
    async with seeded_client as ac:
        resp = await ac.get("/api/tv/snapshot")

    assert resp.status_code == 200
    events = resp.json()["events"]
    start_dts = [e["start_dt"] for e in events]
    assert start_dts == sorted(start_dts)
