"""Tests for the Google Calendar API client wrappers.

All calls to googleapiclient are mocked — no real HTTP in these tests.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from google.oauth2.credentials import Credentials

from backend.app.google.calendar_client import create_calendar, list_calendars


def _make_credentials() -> Credentials:
    """Return a minimal Credentials object suitable for unit tests.

    We pass dummy values for all fields; the actual Google transport is mocked
    out in every test so the credentials are never used to make real HTTP calls.
    """
    return Credentials(  # type: ignore[no-untyped-call]
        token="fake-access-token",
        refresh_token="fake-refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="fake-client-id",
        client_secret="fake-client-secret",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )


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
    creds = _make_credentials()

    with patch("backend.app.google.calendar_client.build", return_value=mock_service):
        result = await list_calendars(creds)

    assert len(result) == 3
    assert result[0]["id"] == "primary@gmail.com"
    assert result[0]["summary"] == "Bryant"
    assert result[0]["primary"] is True
    assert result[1]["id"] == "cal2@group.calendar.google.com"
    assert result[2]["accessRole"] == "reader"


async def test_list_calendars_empty_list() -> None:
    """list_calendars returns an empty list when the API returns no items."""
    mock_service = _make_service_mock([])
    creds = _make_credentials()

    with patch("backend.app.google.calendar_client.build", return_value=mock_service):
        result = await list_calendars(creds)

    assert result == []


# ---------------------------------------------------------------------------
# create_calendar
# ---------------------------------------------------------------------------


async def test_create_calendar_returns_id_and_summary() -> None:
    """create_calendar calls the API and returns id + summary of the new calendar."""
    new_cal = {"id": "new-cal@group.calendar.google.com", "summary": "Izzy"}
    mock_service = MagicMock()
    mock_service.calendars.return_value.insert.return_value.execute.return_value = new_cal
    creds = _make_credentials()

    with patch("backend.app.google.calendar_client.build", return_value=mock_service):
        result = await create_calendar(creds, "Izzy")

    assert result["id"] == "new-cal@group.calendar.google.com"
    assert result["summary"] == "Izzy"

    # Confirm the body passed to insert contained the right summary.
    call_kwargs = mock_service.calendars.return_value.insert.call_args
    assert call_kwargs.kwargs["body"]["summary"] == "Izzy"
