"""Tests for the Google Calendar API client wrappers.

All calls to googleapiclient are mocked — no real HTTP in these tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from backend.app.db.models import OauthToken
from backend.app.google.calendar_client import create_calendar, list_calendars


class _FakeToken:
    """Minimal stand-in for an OauthToken ORM row used in unit tests.

    We cannot instantiate OauthToken outside of a SQLAlchemy session context
    using __new__ without triggering instrumentation errors, so we use a simple
    object that exposes the same attributes the calendar_client module reads.
    """

    id: int = 1
    refresh_token: str = "fake-refresh"
    access_token: str | None = "fake-access"
    expires_at: object = None
    scopes: str = "https://www.googleapis.com/auth/calendar"


def _make_token() -> OauthToken:
    """Return a fake token object compatible with the calendar_client API."""
    return _FakeToken()  # type: ignore[return-value]


def _make_service_mock(calendar_list_items: list[dict[str, Any]]) -> MagicMock:
    """Return a mock ``build(...)`` return value with calendarList.list().execute()."""
    mock_service = MagicMock()
    mock_service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": calendar_list_items
    }
    return mock_service


# ---------------------------------------------------------------------------
# list_calendars
# ---------------------------------------------------------------------------


async def test_list_calendars_returns_mapped_items() -> None:
    """list_calendars returns a list of dicts with id/summary/primary/accessRole."""
    raw_items: list[dict[str, Any]] = [
        {"id": "primary@gmail.com", "summary": "Bryant", "primary": True, "accessRole": "owner"},
        {"id": "cal2@group.calendar.google.com", "summary": "Family", "accessRole": "owner"},
        {"id": "cal3@group.calendar.google.com", "summary": "Work", "accessRole": "reader"},
    ]
    mock_service = _make_service_mock(raw_items)
    token = _make_token()

    with (
        patch("backend.app.google.calendar_client.build", return_value=mock_service),
        patch("backend.app.google.calendar_client._refresh_if_needed"),
    ):
        result = await list_calendars(token)

    assert len(result) == 3
    assert result[0]["id"] == "primary@gmail.com"
    assert result[0]["summary"] == "Bryant"
    assert result[0]["primary"] is True
    assert result[1]["id"] == "cal2@group.calendar.google.com"
    assert result[2]["accessRole"] == "reader"


async def test_list_calendars_empty_list() -> None:
    """list_calendars returns an empty list when the API returns no items."""
    mock_service = _make_service_mock([])
    token = _make_token()

    with (
        patch("backend.app.google.calendar_client.build", return_value=mock_service),
        patch("backend.app.google.calendar_client._refresh_if_needed"),
    ):
        result = await list_calendars(token)

    assert result == []


# ---------------------------------------------------------------------------
# create_calendar
# ---------------------------------------------------------------------------


async def test_create_calendar_returns_id_and_summary() -> None:
    """create_calendar calls the API and returns id + summary of the new calendar."""
    new_cal = {"id": "new-cal@group.calendar.google.com", "summary": "Izzy"}
    mock_service = MagicMock()
    mock_service.calendars.return_value.insert.return_value.execute.return_value = new_cal
    token = _make_token()

    with (
        patch("backend.app.google.calendar_client.build", return_value=mock_service),
        patch("backend.app.google.calendar_client._refresh_if_needed"),
    ):
        result = await create_calendar(token, "Izzy")

    assert result["id"] == "new-cal@group.calendar.google.com"
    assert result["summary"] == "Izzy"

    # Confirm the body passed to insert contained the right summary.
    call_kwargs = mock_service.calendars.return_value.insert.call_args
    assert call_kwargs.kwargs["body"]["summary"] == "Izzy"
