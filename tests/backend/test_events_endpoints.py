"""End-to-end tests for the /api/events/* endpoints.

Uses httpx.AsyncClient with ASGITransport against a real FastAPI app backed
by an isolated per-test SQLite database (via db_engine from conftest.py).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.db.models import Event, EventCorrection, FamilyMember, Upload, User
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
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


@pytest.fixture
async def client_with_data_dir(
    db_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncClient:
    """AsyncClient with a temp data_dir; settings cache cleared so the dir is visible."""
    monkeypatch.setenv("HEARTH_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client_with_data_dir(
    db_engine: AsyncEngine,
    client_with_data_dir: AsyncClient,
) -> AsyncClient:
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client_with_data_dir


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _login_regular(ac: AsyncClient, db_engine: AsyncEngine) -> User:
    """Create and log in as a non-admin user; return the User row."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username="regular",
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "regular", "password": "password123"},
    )
    assert resp.status_code == 200
    # Re-fetch outside the session to avoid detached instance issues.
    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(User).where(User.id == user_id))
        return result.scalar_one()


async def _get_admin_user(db_engine: AsyncEngine) -> User:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one()
        return user


# ---------------------------------------------------------------------------
# DB helpers — create test data
# ---------------------------------------------------------------------------


async def _create_upload(db_engine: AsyncEngine, user_id: int) -> Upload:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        upload = Upload(
            user_id=user_id,
            image_path="uploads/test.jpg",
            status="completed",
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
        upload_id = upload.id

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Upload).where(Upload.id == upload_id))
        return result.scalar_one()


async def _create_event(
    db_engine: AsyncEngine,
    *,
    upload_id: int | None = None,
    family_member_id: int | None = None,
    title: str = "Test Event",
    status: str = "pending_review",
    start_dt: datetime | None = None,
    created_at: datetime | None = None,
    cell_crop_path: str | None = None,
) -> Event:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        ev = Event(
            upload_id=upload_id,
            family_member_id=family_member_id,
            title=title,
            start_dt=start_dt or datetime(2026, 6, 15, 10, 0),
            status=status,
            cell_crop_path=cell_crop_path,
        )
        if created_at is not None:
            ev.created_at = created_at
        session.add(ev)
        await session.commit()
        await session.refresh(ev)
        event_id = ev.id

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one()


async def _get_family_member_by_name(db_engine: AsyncEngine, name: str) -> FamilyMember:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).where(FamilyMember.name == name)
        )
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Tests — Listing
# ---------------------------------------------------------------------------


async def test_list_events_returns_all_non_rejected_by_default(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events returns non-rejected/superseded events by default."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    await _create_event(db_engine, upload_id=upload.id, title="Pending", status="pending_review")
    await _create_event(db_engine, upload_id=upload.id, title="Published", status="published")
    await _create_event(db_engine, upload_id=upload.id, title="Rejected", status="rejected")
    await _create_event(db_engine, upload_id=upload.id, title="Superseded", status="superseded")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events")

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body

    titles = {item["title"] for item in body["items"]}
    assert "Pending" in titles
    assert "Published" in titles
    assert "Rejected" not in titles
    assert "Superseded" not in titles
    assert body["total"] == 2


async def test_list_events_filters_by_status_csv(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """?status=pending_review returns only pending_review events."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    await _create_event(db_engine, upload_id=upload.id, title="Pending", status="pending_review")
    await _create_event(db_engine, upload_id=upload.id, title="Published", status="published")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events?status=pending_review")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Pending"


async def test_list_events_filters_by_multiple_statuses(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """?status=pending_review,auto_published returns both status types."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    await _create_event(db_engine, upload_id=upload.id, title="Pending", status="pending_review")
    await _create_event(
        db_engine, upload_id=upload.id, title="AutoPublished", status="auto_published"
    )
    await _create_event(db_engine, upload_id=upload.id, title="Published", status="published")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events?status=pending_review,auto_published")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    titles = {item["title"] for item in body["items"]}
    assert "Pending" in titles
    assert "AutoPublished" in titles
    assert "Published" not in titles


async def test_list_events_filters_by_upload_id(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """?upload_id=N returns only events for that upload."""
    admin = await _get_admin_user(db_engine)
    upload1 = await _create_upload(db_engine, admin.id)
    upload2 = await _create_upload(db_engine, admin.id)

    await _create_event(db_engine, upload_id=upload1.id, title="Upload1 Event")
    await _create_event(db_engine, upload_id=upload2.id, title="Upload2 Event")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events?upload_id={upload1.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Upload1 Event"


async def test_list_events_pagination(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """limit and offset parameters work correctly."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    for i in range(5):
        await _create_event(db_engine, upload_id=upload.id, title=f"Event {i}")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events?limit=2&offset=0")
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1["items"]) == 2
        assert page1["total"] == 5

        resp2 = await ac.get("/api/events?limit=2&offset=2")
        assert resp2.status_code == 200
        page2 = resp2.json()
        assert len(page2["items"]) == 2
        assert page2["total"] == 5

        # Pages should not overlap.
        ids_page1 = {item["id"] for item in page1["items"]}
        ids_page2 = {item["id"] for item in page2["items"]}
        assert ids_page1.isdisjoint(ids_page2)


async def test_list_events_sort_order(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Events are sorted created_at DESC, start_dt ASC."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    earlier_created = datetime(2026, 1, 1, 10, 0)
    later_created = datetime(2026, 1, 2, 10, 0)

    # Two events created at different times.
    ev_old = await _create_event(
        db_engine,
        upload_id=upload.id,
        title="OldCreated",
        created_at=earlier_created,
        start_dt=datetime(2026, 6, 10, 9, 0),
    )
    ev_new = await _create_event(
        db_engine,
        upload_id=upload.id,
        title="NewCreated",
        created_at=later_created,
        start_dt=datetime(2026, 6, 10, 9, 0),
    )

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events?status=pending_review")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 2

    ids = [item["id"] for item in items]
    # NewCreated (later created_at) should come before OldCreated.
    assert ids.index(ev_new.id) < ids.index(ev_old.id)


async def test_list_events_includes_family_member_name_and_color(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """EventResponse includes family_member_name and family_member_color_hex."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    member = await _get_family_member_by_name(db_engine, "Bryant")

    await _create_event(
        db_engine,
        upload_id=upload.id,
        title="Family Event",
        family_member_id=member.id,
    )

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events")

    assert resp.status_code == 200
    items = resp.json()["items"]
    family_events = [e for e in items if e["title"] == "Family Event"]
    assert len(family_events) == 1
    ev = family_events[0]
    assert ev["family_member_name"] == "Bryant"
    assert ev["family_member_color_hex"] is not None
    assert ev["family_member_color_hex"].startswith("#")


async def test_list_events_requires_auth(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/events returns 401 when not authenticated."""
    async with bootstrapped_client as ac:
        resp = await ac.get("/api/events")

    assert resp.status_code == 401


async def test_list_events_excludes_other_users_events_for_non_admin(
    db_engine: AsyncEngine,
) -> None:
    """Regular user only sees their own events; admin sees all."""
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)

    admin = await _get_admin_user(db_engine)
    admin_upload = await _create_upload(db_engine, admin.id)
    await _create_event(db_engine, upload_id=admin_upload.id, title="Admin's Event")

    app = create_app()
    transport = ASGITransport(app=app)

    # Regular user session.
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        regular_user = await _login_regular(ac, db_engine)
        regular_upload = await _create_upload(db_engine, regular_user.id)
        await _create_event(db_engine, upload_id=regular_upload.id, title="Regular's Event")
        resp = await ac.get("/api/events")

    assert resp.status_code == 200
    body = resp.json()
    titles = {item["title"] for item in body["items"]}
    assert "Admin's Event" not in titles
    assert "Regular's Event" in titles

    # Admin session — sees all.
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _login_admin(ac)
        resp2 = await ac.get("/api/events")

    body2 = resp2.json()
    titles2 = {item["title"] for item in body2["items"]}
    assert "Admin's Event" in titles2
    assert "Regular's Event" in titles2


# ---------------------------------------------------------------------------
# Tests — Detail
# ---------------------------------------------------------------------------


async def test_get_event_returns_event(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events/{id} returns the event with all expected fields."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="Detail Test")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == event.id
    assert body["title"] == "Detail Test"
    assert "status" in body
    assert "start_dt" in body
    assert "has_cell_crop" in body
    assert body["has_cell_crop"] is False


async def test_get_event_404_when_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/events/99999 returns 404."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events/99999")

    assert resp.status_code == 404


async def test_get_event_403_when_other_user_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin cannot access another user's event."""
    admin = await _get_admin_user(db_engine)
    admin_upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=admin_upload.id, title="Admin's Event")

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get(f"/api/events/{event.id}")

    assert resp.status_code == 403


async def test_get_event_admin_can_see_others(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Admin can access any user's event."""
    # Create regular user and their event.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        regular = User(
            username="other_user",
            password_hash=hash_password("pass"),
            role="user",
        )
        session.add(regular)
        await session.commit()
        await session.refresh(regular)
        regular_id = regular.id

    regular_upload = await _create_upload(db_engine, regular_id)
    event = await _create_event(db_engine, upload_id=regular_upload.id, title="Regular Event")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}")

    assert resp.status_code == 200
    assert resp.json()["id"] == event.id


# ---------------------------------------------------------------------------
# Tests — Patch
# ---------------------------------------------------------------------------


async def test_patch_event_no_changes_publishes_without_correction_row(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH with no changed fields publishes the event without creating a correction row."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="No Change Event")

    original_updated_at = event.updated_at

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(f"/api/events/{event.id}", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    # updated_at should be bumped.
    assert body["updated_at"] != original_updated_at.isoformat().replace("+00:00", "")

    # No correction row written.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(EventCorrection).where(EventCorrection.event_id == event.id)
        )
        corrections = list(result.scalars().all())
    assert len(corrections) == 0


async def test_patch_event_with_title_change_writes_correction_row(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH with a title change writes one EventCorrection row with correct before/after."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="Old Title")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(f"/api/events/{event.id}", json={"title": "New Title"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "published"
    assert body["title"] == "New Title"

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(EventCorrection).where(EventCorrection.event_id == event.id)
        )
        corrections = list(result.scalars().all())

    assert len(corrections) == 1
    correction = corrections[0]
    before = json.loads(correction.before_json)
    after = json.loads(correction.after_json)
    assert before["title"] == "Old Title"
    assert after["title"] == "New Title"
    assert correction.corrected_by == admin.id


async def test_patch_event_with_multiple_field_changes_writes_one_correction_row(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Multiple changed fields produce exactly one correction row."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="Original")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/events/{event.id}",
            json={"title": "Updated", "location": "New Location", "notes": "Updated notes"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated"
    assert body["location"] == "New Location"

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(EventCorrection).where(EventCorrection.event_id == event.id)
        )
        corrections = list(result.scalars().all())

    # Exactly one correction row for the batch of changes.
    assert len(corrections) == 1


async def test_patch_event_can_change_family_member_id(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH can update family_member_id to a valid family member."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="Family Change")

    member = await _get_family_member_by_name(db_engine, "Bryant")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/events/{event.id}",
            json={"family_member_id": member.id},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["family_member_id"] == member.id
    assert body["family_member_name"] == "Bryant"


async def test_patch_event_400_when_already_rejected(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH on a rejected event returns 400."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, status="rejected")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(f"/api/events/{event.id}", json={"title": "New Title"})

    assert resp.status_code == 400


async def test_patch_event_400_when_already_superseded(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH on a superseded event returns 400."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, status="superseded")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(f"/api/events/{event.id}", json={"title": "New Title"})

    assert resp.status_code == 400


async def test_patch_event_does_not_call_google_calendar(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH does not set google_event_id or published_at (Phase 7 responsibility)."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="No GCal Event")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(f"/api/events/{event.id}", json={"title": "Updated"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["google_event_id"] is None
    assert body["published_at"] is None


async def test_patch_event_403_when_other_user_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin cannot PATCH another user's event."""
    admin = await _get_admin_user(db_engine)
    admin_upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=admin_upload.id, title="Admin's Event")

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.patch(f"/api/events/{event.id}", json={"title": "Stolen"})

    assert resp.status_code == 403


async def test_patch_event_404_when_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    """PATCH on a non-existent event returns 404."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch("/api/events/99999", json={"title": "Ghost"})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Delete (reject)
# ---------------------------------------------------------------------------


async def test_delete_event_sets_status_rejected(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """DELETE /api/events/{id} soft-deletes by setting status to 'rejected'."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, title="To Delete")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete(f"/api/events/{event.id}")

    assert resp.status_code == 204

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(Event).where(Event.id == event.id))
        fetched = result.scalar_one()

    assert fetched.status == "rejected"


async def test_delete_event_returns_204(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """DELETE returns 204 No Content."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete(f"/api/events/{event.id}")

    assert resp.status_code == 204
    assert resp.content == b""


async def test_delete_event_400_when_already_rejected(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """DELETE on an already-rejected event returns 400."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, status="rejected")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete(f"/api/events/{event.id}")

    assert resp.status_code == 400


async def test_delete_event_403_when_other_user_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin cannot DELETE another user's event."""
    admin = await _get_admin_user(db_engine)
    admin_upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=admin_upload.id, title="Admin's Event")

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.delete(f"/api/events/{event.id}")

    assert resp.status_code == 403


async def test_delete_event_404_when_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    """DELETE on a non-existent event returns 404."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete("/api/events/99999")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — Cell-crop serving
# ---------------------------------------------------------------------------


async def test_get_cell_crop_returns_image_bytes(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """GET /api/events/{id}/cell-crop returns 200 with JPEG bytes and correct content-type."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    rel_path = "uploads/ab/cdef1234/original.jpg"
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    fake_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    abs_path.write_bytes(fake_bytes)

    event = await _create_event(
        db_engine, upload_id=upload.id, cell_crop_path=rel_path
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == fake_bytes


async def test_get_cell_crop_returns_correct_media_type_for_png(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """GET /api/events/{id}/cell-crop returns image/png for a .png file."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    rel_path = "uploads/ab/cdef1234/original.png"
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    fake_bytes = b"\x89PNG\r\nfake-png"
    abs_path.write_bytes(fake_bytes)

    event = await _create_event(
        db_engine, upload_id=upload.id, cell_crop_path=rel_path
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == fake_bytes


async def test_get_cell_crop_404_when_event_missing(
    bootstrapped_client_with_data_dir: AsyncClient,
) -> None:
    """GET /api/events/99999/cell-crop returns 404 when the event doesn't exist."""
    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/events/99999/cell-crop")

    assert resp.status_code == 404


async def test_get_cell_crop_404_when_no_crop_path(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events/{id}/cell-crop returns 404 when cell_crop_path is None."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id, cell_crop_path=None)

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "No cell crop for this event"


async def test_get_cell_crop_404_when_file_missing_on_disk(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events/{id}/cell-crop returns 404 when the referenced file is absent."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(
        db_engine,
        upload_id=upload.id,
        cell_crop_path="uploads/no/file/here/original.jpg",
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Cell crop file not found on disk"


async def test_get_cell_crop_400_on_path_traversal(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events/{id}/cell-crop returns 400 when cell_crop_path escapes data_dir."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(
        db_engine,
        upload_id=upload.id,
        cell_crop_path="../../../etc/passwd",
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid cell crop path"


async def test_get_cell_crop_403_when_other_user_non_admin(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Non-admin user cannot access another user's cell crop."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)

    rel_path = "uploads/ab/cdef1234/original.jpg"
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"\xff\xd8\xff\xe0fake")

    event = await _create_event(
        db_engine, upload_id=upload.id, cell_crop_path=rel_path
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 403


async def test_get_cell_crop_admin_can_access_others_crops(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Admin can fetch the cell crop for any user's event."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        other = User(
            username="other_crop_user",
            password_hash="x",
            role="user",
        )
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = other.id

    upload = await _create_upload(db_engine, other_id)

    rel_path = "uploads/cc/ddee1234/original.jpg"
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    fake_bytes = b"\xff\xd8\xff\xe0admin-can-see"
    abs_path.write_bytes(fake_bytes)

    event = await _create_event(
        db_engine, upload_id=upload.id, cell_crop_path=rel_path
    )

    async with bootstrapped_client_with_data_dir as ac:
        await _login_admin(ac)
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 200
    assert resp.content == fake_bytes


async def test_get_cell_crop_requires_auth(
    bootstrapped_client_with_data_dir: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/events/{id}/cell-crop returns 401 when not authenticated."""
    admin = await _get_admin_user(db_engine)
    upload = await _create_upload(db_engine, admin.id)
    event = await _create_event(db_engine, upload_id=upload.id)

    async with bootstrapped_client_with_data_dir as ac:
        resp = await ac.get(f"/api/events/{event.id}/cell-crop")

    assert resp.status_code == 401
