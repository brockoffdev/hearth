"""Tests for backend/app/google/sync.py.

All Google API calls are mocked — no real HTTP in these tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.db.base import get_session_factory
from backend.app.db.models import Event, FamilyMember, OauthToken, Setting
from backend.app.google.sync import sync_from_gcal

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_gcal_event(
    gcal_id: str = "gcal-abc123",
    summary: str = "Test Event",
    *,
    all_day: bool = False,
    hearth_event_id: str | None = None,
) -> dict[str, Any]:
    if all_day:
        start: dict[str, Any] = {"date": "2026-06-15"}
        end: dict[str, Any] = {"date": "2026-06-16"}
    else:
        start = {"dateTime": "2026-06-15T10:00:00Z"}
        end = {"dateTime": "2026-06-15T11:00:00Z"}

    ext_props: dict[str, Any] = {}
    if hearth_event_id is not None:
        ext_props = {"private": {"hearthEventId": hearth_event_id}}

    return {
        "id": gcal_id,
        "summary": summary,
        "start": start,
        "end": end,
        "status": "confirmed",
        "updated": "2026-04-28T00:00:00.000Z",
        "extendedProperties": ext_props,
    }


def _mock_creds() -> MagicMock:
    from google.oauth2.credentials import Credentials
    return MagicMock(spec=Credentials)


async def _setup_oauth(engine: AsyncEngine) -> None:
    """Insert a valid OauthToken + OAuth credentials in the DB."""
    factory = get_session_factory(engine)
    async with factory() as session:
        token = OauthToken(
            id=1,
            access_token="fake-access",
            refresh_token="fake-refresh",
            scopes="https://www.googleapis.com/auth/calendar",
        )
        session.add(token)
        session.add(Setting(key="google_oauth_client_id", value="fake-id"))
        session.add(Setting(key="google_oauth_client_secret", value="fake-secret"))
        await session.commit()


async def _set_calendar_id(
    engine: AsyncEngine,
    calendar_id: str = "cal@group.calendar.google.com",
) -> FamilyMember:
    factory = get_session_factory(engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).where(FamilyMember.name == "Bryant")
        )
        member = result.scalar_one()
        member.google_calendar_id = calendar_id
        await session.commit()
        member_id = member.id

    factory2 = get_session_factory(engine)
    async with factory2() as session2:
        result2 = await session2.execute(
            select(FamilyMember).where(FamilyMember.id == member_id)
        )
        return result2.scalar_one()


async def _insert_event(
    engine: AsyncEngine,
    *,
    family_member_id: int,
    google_event_id: str | None = None,
    status: str = "published",
    title: str = "Existing Event",
) -> Event:
    factory = get_session_factory(engine)
    async with factory() as session:
        ev = Event(
            upload_id=None,
            family_member_id=family_member_id,
            title=title,
            start_dt=datetime(2026, 6, 15, 10, 0),
            end_dt=None,
            all_day=False,
            status=status,
            google_event_id=google_event_id,
            confidence=1.0,
        )
        session.add(ev)
        await session.commit()
        await session.refresh(ev)
        ev_id = ev.id

    factory2 = get_session_factory(engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == ev_id))
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_sync_imports_new_gcal_event(db_engine: AsyncEngine) -> None:
    """GCal event with no local match → inserted as new row."""
    member = await _set_calendar_id(db_engine)
    await _setup_oauth(db_engine)

    gcal_event = _make_gcal_event("abc123", "New From GCal")

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[gcal_event])),
        ):
            stats = await sync_from_gcal(session)

    assert stats["imported"] == 1
    assert stats["updated"] == 0

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(
            select(Event).where(Event.google_event_id == "abc123")
        )
        row = result.scalar_one_or_none()

    assert row is not None
    assert row.status == "published"
    assert row.upload_id is None
    assert row.google_event_id == "abc123"
    assert row.title == "New From GCal"
    assert row.family_member_id == member.id


async def test_sync_updates_existing_event_by_hearth_event_id(
    db_engine: AsyncEngine,
) -> None:
    """GCal event with hearthEventId → updates the matching local row."""
    member = await _set_calendar_id(db_engine)
    await _setup_oauth(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        google_event_id=None,
        status="auto_published",
        title="Old Title",
    )

    gcal_event = _make_gcal_event(
        "gcal-xyz",
        "Updated Title",
        hearth_event_id=str(event.id),
    )

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[gcal_event])),
        ):
            stats = await sync_from_gcal(session)

    assert stats["updated"] == 1
    assert stats["imported"] == 0

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.title == "Updated Title"
    assert row.google_event_id == "gcal-xyz"


async def test_sync_updates_existing_event_by_google_event_id(
    db_engine: AsyncEngine,
) -> None:
    """GCal event matched via google_event_id → updates the local row."""
    member = await _set_calendar_id(db_engine)
    await _setup_oauth(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        google_event_id="existing-gcal-id",
        status="published",
        title="Before Update",
    )

    gcal_event = _make_gcal_event("existing-gcal-id", "After Update")

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[gcal_event])),
        ):
            stats = await sync_from_gcal(session)

    assert stats["updated"] == 1
    assert stats["imported"] == 0

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.title == "After Update"


async def test_sync_supersedes_local_event_missing_from_gcal(
    db_engine: AsyncEngine,
) -> None:
    """Local published event with google_event_id not in GCal → status='superseded'."""
    member = await _set_calendar_id(db_engine)
    await _setup_oauth(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        google_event_id="ghost-id",
        status="published",
    )

    factory = get_session_factory(db_engine)
    async with factory() as session:
        # GCal returns a completely different event — "ghost-id" is absent.
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[_make_gcal_event("other-id")])),
        ):
            stats = await sync_from_gcal(session)

    assert stats["deleted"] == 1

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.status == "superseded"


async def test_sync_does_not_supersede_pending_review_events(
    db_engine: AsyncEngine,
) -> None:
    """pending_review events are never touched by sync, even if google_event_id is None."""
    member = await _set_calendar_id(db_engine)
    await _setup_oauth(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        google_event_id=None,
        status="pending_review",
    )

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[])),
        ):
            stats = await sync_from_gcal(session)

    assert stats["deleted"] == 0

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.status == "pending_review"


async def test_sync_skips_family_members_without_calendar_id(
    db_engine: AsyncEngine,
) -> None:
    """FamilyMember with google_calendar_id=None is skipped without error."""
    # Don't call _set_calendar_id — leave the seeded Bryant with google_calendar_id=None
    await _setup_oauth(db_engine)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        mock_list = AsyncMock(return_value=[])
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar", new=mock_list),
        ):
            stats = await sync_from_gcal(session)

    # Credentials never needed — skipped before even attempting auth
    mock_list.assert_not_awaited()
    assert stats["errors"] == 0
    assert stats["imported"] == 0


async def test_sync_continues_on_per_calendar_error(db_engine: AsyncEngine) -> None:
    """Error on first calendar doesn't abort sync of remaining calendars."""
    # Give Bryant a calendar
    await _set_calendar_id(db_engine, "cal-a@group.calendar.google.com")
    await _setup_oauth(db_engine)

    # Insert a second family member with a different calendar
    factory = get_session_factory(db_engine)
    async with factory() as session:
        other_member = FamilyMember(
            name="Danya",
            color_hex_center="#FF0000",
            hue_range_low=0,
            hue_range_high=30,
            google_calendar_id="cal-b@group.calendar.google.com",
            sort_order=1,
        )
        session.add(other_member)
        await session.commit()

    gcal_event = _make_gcal_event("success-id", "From Danya's Cal")

    call_count = 0

    async def _mock_list(creds: Any, calendar_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        if "cal-a" in calendar_id:
            raise RuntimeError("API failure for cal-a")
        return [gcal_event]

    factory2 = get_session_factory(db_engine)
    async with factory2() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  side_effect=_mock_list),
        ):
            stats = await sync_from_gcal(session)

    assert stats["errors"] == 1
    assert stats["imported"] == 1  # second calendar succeeded
    assert call_count == 2


async def test_sync_returns_stats(db_engine: AsyncEngine) -> None:
    """sync_from_gcal always returns a dict with all expected keys."""
    await _setup_oauth(db_engine)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch("backend.app.google.sync._resolve_credentials",
                  new=AsyncMock(return_value=(_mock_creds(), None))),
            patch("backend.app.google.sync.list_events_in_calendar",
                  new=AsyncMock(return_value=[])),
        ):
            stats = await sync_from_gcal(session)

    assert set(stats.keys()) == {"imported", "updated", "deleted", "skipped", "errors"}
    for v in stats.values():
        assert isinstance(v, int)
