"""Tests for Phase 7 GCal event helpers: calendar_client extensions + publish.py.

All calls to googleapiclient are mocked — no real HTTP in these tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.db.base import get_session_factory
from backend.app.db.models import Event, FamilyMember, OauthToken, Setting
from backend.app.google.calendar_client import (
    delete_event,
    get_event,
    insert_event,
    patch_event,
)
from backend.app.google.publish import (
    InvalidGrantError,
    NoCalendarError,
    NoOauthError,
    publish_event,
    unpublish_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_credentials() -> MagicMock:
    """Return a minimal mock Credentials object."""
    from google.oauth2.credentials import Credentials

    return MagicMock(spec=Credentials)


def _make_http_error(status: int, reason: str = "error") -> HttpError:
    """Build a googleapiclient HttpError with the given HTTP status code."""
    resp = MagicMock()
    resp.status = status
    resp.reason = reason
    return HttpError(resp=resp, content=reason.encode())


def _make_mock_service() -> MagicMock:
    """Return a mock googleapiclient service object."""
    service = MagicMock()
    return service


_FULL_GCAL_EVENT: dict[str, Any] = {
    "id": "gcal-event-id-123",
    "htmlLink": "https://calendar.google.com/event?eid=123",
    "status": "confirmed",
    "updated": "2026-04-28T00:00:00.000Z",
    "extendedProperties": {"private": {"hearthEventId": "42"}},
    "summary": "Test Event",
    "creator": {"email": "test@example.com"},
    "created": "2026-04-28T00:00:00.000Z",
}

_PRUNED_GCAL_EVENT: dict[str, Any] = {
    "id": "gcal-event-id-123",
    "htmlLink": "https://calendar.google.com/event?eid=123",
    "status": "confirmed",
    "updated": "2026-04-28T00:00:00.000Z",
    "extendedProperties": {"private": {"hearthEventId": "42"}},
}


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


async def _get_or_create_family_member(
    engine: AsyncEngine,
    *,
    google_calendar_id: str | None = "cal@group.calendar.google.com",
) -> FamilyMember:
    """Use the seeded 'Bryant' row and set its google_calendar_id as requested."""
    from sqlalchemy import select

    factory = get_session_factory(engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).where(FamilyMember.name == "Bryant")
        )
        member = result.scalar_one()
        member.google_calendar_id = google_calendar_id
        await session.commit()
        member_id = member.id

    factory2 = get_session_factory(engine)
    async with factory2() as session2:
        result2 = await session2.execute(
            select(FamilyMember).where(FamilyMember.id == member_id)
        )
        return result2.scalar_one()


# Keep old name as alias for readability
_insert_family_member = _get_or_create_family_member


async def _insert_oauth_token(
    engine: AsyncEngine,
    *,
    access_token: str = "fake-access-token",
    refresh_token: str = "fake-refresh-token",
) -> OauthToken:
    factory = get_session_factory(engine)
    async with factory() as session:
        token = OauthToken(
            id=1,
            access_token=access_token,
            refresh_token=refresh_token,
            scopes="https://www.googleapis.com/auth/calendar",
        )
        session.add(token)
        await session.commit()
        await session.refresh(token)
    factory2 = get_session_factory(engine)
    async with factory2() as session2:
        from sqlalchemy import select

        result = await session2.execute(select(OauthToken).where(OauthToken.id == 1))
        return result.scalar_one()


async def _insert_oauth_credentials(engine: AsyncEngine) -> None:
    """Insert google_oauth_client_id and google_oauth_client_secret settings rows."""
    factory = get_session_factory(engine)
    async with factory() as session:
        session.add(Setting(key="google_oauth_client_id", value="fake-client-id"))
        session.add(Setting(key="google_oauth_client_secret", value="fake-client-secret"))
        await session.commit()


async def _insert_event(
    engine: AsyncEngine,
    *,
    family_member_id: int | None,
    all_day: bool = False,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
    google_event_id: str | None = None,
    title: str = "Test Event",
    notes: str | None = None,
    location: str | None = None,
) -> Event:
    factory = get_session_factory(engine)
    async with factory() as session:
        ev = Event(
            upload_id=None,
            family_member_id=family_member_id,
            title=title,
            start_dt=start_dt or datetime(2026, 6, 15, 10, 0),
            end_dt=end_dt,
            all_day=all_day,
            notes=notes,
            location=location,
            status="pending_review",
            google_event_id=google_event_id,
            confidence=1.0,
        )
        session.add(ev)
        await session.commit()
        await session.refresh(ev)
        event_id = ev.id

    factory2 = get_session_factory(engine)
    async with factory2() as session2:
        from sqlalchemy import select

        result = await session2.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one()


# ---------------------------------------------------------------------------
# Part 1: calendar_client extensions — insert_event
# ---------------------------------------------------------------------------


async def test_insert_event_returns_pruned_dict() -> None:
    """insert_event returns only the 5 canonical fields, not the full GCal response."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.insert.return_value.execute.return_value = _FULL_GCAL_EVENT

    with patch("backend.app.google.calendar_client.build", return_value=service):
        result = await insert_event(creds, "cal@example.com", {"summary": "Test"})

    assert result == _PRUNED_GCAL_EVENT
    assert "creator" not in result
    assert "summary" not in result


async def test_insert_event_passes_calendar_id_and_body() -> None:
    """insert_event forwards calendar_id and body to the GCal API."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.insert.return_value.execute.return_value = _FULL_GCAL_EVENT
    body = {"summary": "Birthday", "start": {"date": "2026-06-01"}}

    with patch("backend.app.google.calendar_client.build", return_value=service):
        await insert_event(creds, "my-cal-id@group.calendar.google.com", body)

    insert_call = service.events.return_value.insert
    call_kwargs = insert_call.call_args
    assert call_kwargs.kwargs["calendarId"] == "my-cal-id@group.calendar.google.com"
    assert call_kwargs.kwargs["body"] == body


# ---------------------------------------------------------------------------
# Part 1: calendar_client extensions — patch_event
# ---------------------------------------------------------------------------


async def test_patch_event_returns_pruned_dict() -> None:
    """patch_event returns only the 5 canonical fields."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.patch.return_value.execute.return_value = _FULL_GCAL_EVENT

    with patch("backend.app.google.calendar_client.build", return_value=service):
        result = await patch_event(creds, "cal@example.com", "event-id-1", {"summary": "Updated"})

    assert result == _PRUNED_GCAL_EVENT
    assert "creator" not in result


# ---------------------------------------------------------------------------
# Part 1: calendar_client extensions — delete_event
# ---------------------------------------------------------------------------


async def test_delete_event_swallows_404_and_410() -> None:
    """delete_event silently ignores 404 and 410 — the event is already gone."""
    creds = _make_credentials()

    for status_code in (404, 410):
        service = _make_mock_service()
        service.events.return_value.delete.return_value.execute.side_effect = (
            _make_http_error(status_code)
        )
        with patch("backend.app.google.calendar_client.build", return_value=service):
            # Should not raise
            await delete_event(creds, "cal@example.com", "gone-event-id")


async def test_delete_event_propagates_other_errors() -> None:
    """delete_event re-raises non-404/410 HttpError."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.delete.return_value.execute.side_effect = (
        _make_http_error(500, "Internal Server Error")
    )

    with patch("backend.app.google.calendar_client.build", return_value=service):
        with pytest.raises(HttpError) as exc_info:
            await delete_event(creds, "cal@example.com", "event-id")

    assert exc_info.value.resp.status == 500


# ---------------------------------------------------------------------------
# Part 1: calendar_client extensions — get_event
# ---------------------------------------------------------------------------


async def test_get_event_returns_none_on_404() -> None:
    """get_event returns None when the GCal API responds with 404."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.get.return_value.execute.side_effect = (
        _make_http_error(404)
    )

    with patch("backend.app.google.calendar_client.build", return_value=service):
        result = await get_event(creds, "cal@example.com", "missing-event")

    assert result is None


async def test_get_event_returns_event_dict_on_success() -> None:
    """get_event returns the full raw event dict on success."""
    creds = _make_credentials()
    service = _make_mock_service()
    service.events.return_value.get.return_value.execute.return_value = _FULL_GCAL_EVENT

    with patch("backend.app.google.calendar_client.build", return_value=service):
        result = await get_event(creds, "cal@example.com", "gcal-event-id-123")

    assert result == _FULL_GCAL_EVENT
    # get_event returns raw — no pruning
    assert "creator" in (result or {})
    assert "summary" in (result or {})


# ---------------------------------------------------------------------------
# Part 2: publish.py tests — helpers / fixtures
# ---------------------------------------------------------------------------


def _mock_credentials_for(was_refreshed: bool = False) -> AsyncMock:
    """Return an AsyncMock for credentials_for that yields fake creds."""
    fake_creds = _make_credentials()
    fake_creds.token = "new-access-token"
    return AsyncMock(return_value=(fake_creds, was_refreshed))


def _mock_insert_event(gcal_id: str = "new-gcal-id") -> AsyncMock:
    return AsyncMock(
        return_value={
            "id": gcal_id,
            "htmlLink": "https://calendar.google.com/event",
            "status": "confirmed",
            "updated": "2026-04-28T00:00:00.000Z",
            "extendedProperties": {"private": {"hearthEventId": "1"}},
        }
    )


def _mock_patch_event() -> AsyncMock:
    return AsyncMock(
        return_value={
            "id": "existing-gcal-id",
            "htmlLink": "https://calendar.google.com/event",
            "status": "confirmed",
            "updated": "2026-04-28T12:00:00.000Z",
            "extendedProperties": {"private": {"hearthEventId": "1"}},
        }
    )


# ---------------------------------------------------------------------------
# Part 2: publish_event tests
# ---------------------------------------------------------------------------


async def test_publish_event_inserts_when_no_google_event_id(
    db_engine: AsyncEngine,
) -> None:
    """publish_event calls insert_event when google_event_id is None."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    mock_insert = _mock_insert_event("inserted-gcal-id")
    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.insert_event", new=mock_insert),
        ):
            updated = await publish_event(session, event.id)

    assert updated.google_event_id == "inserted-gcal-id"
    assert updated.published_at is not None
    mock_insert.assert_awaited_once()


async def test_publish_event_patches_when_google_event_id_set(
    db_engine: AsyncEngine,
) -> None:
    """publish_event calls patch_event when google_event_id is already set."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine, family_member_id=member.id, google_event_id="existing-gcal-id"
    )

    mock_patch = _mock_patch_event()
    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.patch_event", new=mock_patch),
        ):
            updated = await publish_event(session, event.id)

    assert updated.google_event_id == "existing-gcal-id"
    assert updated.published_at is not None
    mock_patch.assert_awaited_once()


async def test_publish_event_persists_returned_id_and_published_at(
    db_engine: AsyncEngine,
) -> None:
    """After insert, google_event_id and published_at are persisted to the DB."""
    from sqlalchemy import select

    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch(
                "backend.app.google.publish.insert_event",
                new=_mock_insert_event("persisted-id"),
            ),
        ):
            await publish_event(session, event.id)

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.google_event_id == "persisted-id"
    assert row.published_at is not None


async def test_publish_event_persists_refreshed_oauth_token(
    db_engine: AsyncEngine,
) -> None:
    """When was_refreshed=True, the new access token is written back to OauthToken."""
    from sqlalchemy import select

    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine, access_token="old-token")
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    fake_creds = _make_credentials()
    fake_creds.token = "refreshed-token"
    fake_creds.expiry = None

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=AsyncMock(return_value=(fake_creds, True)),
            ),
            patch(
                "backend.app.google.publish.expiry_to_datetime",
                return_value=None,
            ),
            patch(
                "backend.app.google.publish.insert_event",
                new=_mock_insert_event(),
            ),
        ):
            await publish_event(session, event.id)

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(OauthToken).where(OauthToken.id == 1))
        token_row = result.scalar_one()

    assert token_row.access_token == "refreshed-token"


async def test_publish_event_raises_no_oauth_when_token_row_missing(
    db_engine: AsyncEngine,
) -> None:
    """publish_event raises NoOauthError when no oauth_tokens row exists."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with pytest.raises(NoOauthError):
            await publish_event(session, event.id)


async def test_publish_event_raises_invalid_grant_on_refresh_error(
    db_engine: AsyncEngine,
) -> None:
    """publish_event raises InvalidGrantError when credentials_for raises RefreshError."""
    from google.auth.exceptions import RefreshError

    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=AsyncMock(side_effect=RefreshError("invalid_grant")),
            ),
            pytest.raises(InvalidGrantError),
        ):
            await publish_event(session, event.id)


async def test_publish_event_raises_no_calendar_when_family_member_missing(
    db_engine: AsyncEngine,
) -> None:
    """publish_event raises NoCalendarError when family_member_id points to no row."""
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    # family_member_id=999 does not exist
    event = await _insert_event(db_engine, family_member_id=999)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            pytest.raises(NoCalendarError),
        ):
            await publish_event(session, event.id)


async def test_publish_event_raises_no_calendar_when_family_member_has_no_calendar_id(
    db_engine: AsyncEngine,
) -> None:
    """publish_event raises NoCalendarError when member.google_calendar_id is None."""
    member = await _insert_family_member(db_engine, google_calendar_id=None)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            pytest.raises(NoCalendarError),
        ):
            await publish_event(session, event.id)


async def test_publish_event_builds_all_day_body_correctly(
    db_engine: AsyncEngine,
) -> None:
    """All-day event body uses date fields and end.date is start.date + 1 day."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    start = datetime(2026, 6, 15)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        all_day=True,
        start_dt=start,
        end_dt=None,
    )

    captured_body: dict[str, Any] = {}

    async def _capture_insert(
        creds: Any, calendar_id: str, event_body: dict[str, Any]
    ) -> dict[str, Any]:
        captured_body.update(event_body)
        return {
            "id": "all-day-id",
            "htmlLink": "",
            "status": "confirmed",
            "updated": "",
            "extendedProperties": {},
        }

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.insert_event", side_effect=_capture_insert),
        ):
            await publish_event(session, event.id)

    assert "start" in captured_body
    assert "date" in captured_body["start"]
    assert "dateTime" not in captured_body["start"]
    assert captured_body["start"]["date"] == "2026-06-15"
    assert captured_body["end"]["date"] == "2026-06-16"  # exclusive: +1 day


async def test_publish_event_builds_timed_body_correctly(
    db_engine: AsyncEngine,
) -> None:
    """Timed event body uses dateTime fields with Z suffix; default 1h end."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    start = datetime(2026, 6, 15, 10, 0)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        all_day=False,
        start_dt=start,
        end_dt=None,  # no end_dt → default 1h
    )

    captured_body: dict[str, Any] = {}

    async def _capture_insert(
        creds: Any, calendar_id: str, event_body: dict[str, Any]
    ) -> dict[str, Any]:
        captured_body.update(event_body)
        return {
            "id": "timed-id",
            "htmlLink": "",
            "status": "confirmed",
            "updated": "",
            "extendedProperties": {},
        }

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.insert_event", side_effect=_capture_insert),
        ):
            await publish_event(session, event.id)

    assert "dateTime" in captured_body["start"]
    assert captured_body["start"]["dateTime"].endswith("Z")
    assert "dateTime" in captured_body["end"]
    assert captured_body["end"]["dateTime"].endswith("Z")
    # Default end is 1 hour after start
    assert captured_body["end"]["dateTime"] == "2026-06-15T11:00:00Z"


async def test_publish_event_includes_hearth_extended_property(
    db_engine: AsyncEngine,
) -> None:
    """The event body always includes extendedProperties.private.hearthEventId."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id)

    captured_body: dict[str, Any] = {}

    async def _capture_insert(
        creds: Any, calendar_id: str, event_body: dict[str, Any]
    ) -> dict[str, Any]:
        captured_body.update(event_body)
        return {
            "id": "ep-id",
            "htmlLink": "",
            "status": "confirmed",
            "updated": "",
            "extendedProperties": event_body.get("extendedProperties", {}),
        }

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.insert_event", side_effect=_capture_insert),
        ):
            await publish_event(session, event.id)

    assert captured_body["extendedProperties"]["private"]["hearthEventId"] == str(event.id)


async def test_publish_event_includes_description_footer(
    db_engine: AsyncEngine,
) -> None:
    """The description includes the Hearth footer with upload_id."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        notes="Birthday party",
    )

    captured_body: dict[str, Any] = {}

    async def _capture_insert(
        creds: Any, calendar_id: str, event_body: dict[str, Any]
    ) -> dict[str, Any]:
        captured_body.update(event_body)
        return {
            "id": "desc-id",
            "htmlLink": "",
            "status": "confirmed",
            "updated": "",
            "extendedProperties": {},
        }

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.insert_event", side_effect=_capture_insert),
        ):
            await publish_event(session, event.id)

    desc = captured_body["description"]
    assert "Birthday party" in desc
    assert "Auto-imported by Hearth" in desc
    assert "from upload #" in desc


async def test_publish_event_omits_footer_on_patch(
    db_engine: AsyncEngine,
) -> None:
    """Patch (re-publish) sends notes verbatim; no footer accumulation."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine,
        family_member_id=member.id,
        notes="Birthday party",
        google_event_id="existing-gcal-id",
    )

    captured_body: dict[str, Any] = {}

    async def _capture_patch(
        creds: Any,
        calendar_id: str,
        event_id: str,
        event_body: dict[str, Any],
    ) -> dict[str, Any]:
        captured_body.update(event_body)
        return {
            "id": event_id,
            "htmlLink": "",
            "status": "confirmed",
            "updated": "",
            "extendedProperties": {},
        }

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.patch_event", side_effect=_capture_patch),
        ):
            await publish_event(session, event.id)

    desc = captured_body["description"]
    assert desc == "Birthday party"
    assert "Auto-imported by Hearth" not in desc


# ---------------------------------------------------------------------------
# Part 2: unpublish_event tests
# ---------------------------------------------------------------------------


async def test_unpublish_event_calls_delete_when_google_event_id_set(
    db_engine: AsyncEngine,
) -> None:
    """unpublish_event calls delete_event when google_event_id is set."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine, family_member_id=member.id, google_event_id="to-delete-id"
    )

    mock_delete = AsyncMock(return_value=None)
    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.delete_event", new=mock_delete),
        ):
            await unpublish_event(session, event.id)

    mock_delete.assert_awaited_once()
    args = mock_delete.call_args
    assert args.args[2] == "to-delete-id"


async def test_unpublish_event_clears_google_event_id_on_success(
    db_engine: AsyncEngine,
) -> None:
    """After unpublish, google_event_id is None in the DB."""
    from sqlalchemy import select

    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine, family_member_id=member.id, google_event_id="will-be-cleared"
    )

    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.delete_event", new=AsyncMock(return_value=None)),
        ):
            await unpublish_event(session, event.id)

    factory2 = get_session_factory(db_engine)
    async with factory2() as session2:
        result = await session2.execute(select(Event).where(Event.id == event.id))
        row = result.scalar_one()

    assert row.google_event_id is None


async def test_unpublish_event_is_noop_when_google_event_id_null(
    db_engine: AsyncEngine,
) -> None:
    """unpublish_event returns the event unchanged when google_event_id is already None."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(db_engine, family_member_id=member.id, google_event_id=None)

    mock_delete = AsyncMock(return_value=None)
    factory = get_session_factory(db_engine)
    async with factory() as session:
        with patch("backend.app.google.publish.delete_event", new=mock_delete):
            result = await unpublish_event(session, event.id)

    mock_delete.assert_not_awaited()
    assert result.google_event_id is None


async def test_unpublish_event_swallows_410_gone(
    db_engine: AsyncEngine,
) -> None:
    """unpublish_event is idempotent: 410 from GCal is swallowed by delete_event."""
    member = await _insert_family_member(db_engine)
    await _insert_oauth_token(db_engine)
    await _insert_oauth_credentials(db_engine)
    event = await _insert_event(
        db_engine, family_member_id=member.id, google_event_id="already-deleted"
    )

    # delete_event itself swallows 410; simulate by making it return None (no error)
    mock_delete = AsyncMock(return_value=None)
    factory = get_session_factory(db_engine)
    async with factory() as session:
        with (
            patch(
                "backend.app.google.publish.credentials_for",
                new=_mock_credentials_for(),
            ),
            patch("backend.app.google.publish.delete_event", new=mock_delete),
        ):
            result = await unpublish_event(session, event.id)

    assert result.google_event_id is None
