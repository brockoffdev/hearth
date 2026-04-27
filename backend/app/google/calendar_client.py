"""Google Calendar API client wrappers.

These helpers wrap ``googleapiclient.discovery.build("calendar", "v3", ...)``
and surface only the functionality Task E-F need: listing calendars and
creating a new calendar.

The underlying Google client library is synchronous, so all blocking calls
are dispatched via ``asyncio.to_thread``.  Token refresh is handled by the
``google.oauth2.credentials.Credentials`` object itself — if the access token
is expired, the library automatically uses the refresh token.

mypy: the Google auth libraries have partial typing; per-module overrides in
pyproject.toml suppress missing-import / untyped-call errors for those packages.
"""

from __future__ import annotations

import asyncio
from typing import Any

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.app.db.models import OauthToken

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def _credentials_from_token(token: OauthToken) -> Credentials:
    """Build a ``google.oauth2.credentials.Credentials`` from an OauthToken row.

    The Credentials object will handle access-token refresh automatically
    when a request is made after the token has expired.
    """
    from backend.app.google.oauth_client import _GOOGLE_TOKEN_URI  # local import avoids circular

    scopes_list: list[str] = (
        token.scopes.split() if token.scopes else [_CALENDAR_SCOPE]
    )
    creds = Credentials(  # type: ignore[no-untyped-call]
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=_GOOGLE_TOKEN_URI,
        scopes=scopes_list,
    )
    return creds


def _refresh_if_needed(creds: Credentials) -> None:
    """Refresh the access token in-place if it has expired or is about to expire."""
    if not creds.valid:
        request = google.auth.transport.requests.Request()
        creds.refresh(request)


async def list_calendars(token: OauthToken) -> list[dict[str, Any]]:
    """Return all calendars accessible by the authenticated Google account.

    Each item contains at minimum: ``id``, ``summary``, ``accessRole``, and
    optionally ``primary`` (bool, only on the primary calendar).
    """

    def _sync() -> list[dict[str, Any]]:
        creds = _credentials_from_token(token)
        _refresh_if_needed(creds)
        service = build("calendar", "v3", credentials=creds)
        result = service.calendarList().list().execute()
        items: list[dict[str, Any]] = result.get("items", [])
        return [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "accessRole": item.get("accessRole"),
            }
            for item in items
        ]

    return await asyncio.to_thread(_sync)


async def create_calendar(token: OauthToken, summary: str) -> dict[str, Any]:
    """Create a new Google Calendar and return its ``{id, summary}``.

    The new calendar is owned by the account that granted OAuth access.
    """

    def _sync() -> dict[str, Any]:
        creds = _credentials_from_token(token)
        _refresh_if_needed(creds)
        service = build("calendar", "v3", credentials=creds)
        calendar_body = {"summary": summary}
        result = service.calendars().insert(body=calendar_body).execute()
        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
        }

    return await asyncio.to_thread(_sync)
