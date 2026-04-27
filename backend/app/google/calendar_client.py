"""Google Calendar API client wrappers.

These helpers wrap ``googleapiclient.discovery.build("calendar", "v3", ...)``
and surface only the functionality Task E-F need: listing calendars and
creating a new calendar.

The underlying Google client library is synchronous, so all blocking calls
are dispatched via ``asyncio.to_thread``.

``credentials_for`` handles token refresh and returns a ``was_refreshed``
flag; the caller is responsible for persisting the updated access token back
to the database if ``was_refreshed`` is True.  ``list_calendars`` and
``create_calendar`` accept a ready-to-use ``Credentials`` object so this
module has no database dependencies.

mypy: the Google auth libraries have partial typing; per-module overrides in
pyproject.toml suppress missing-import / untyped-call errors for those packages.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from backend.app.db.models import OauthToken

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


async def credentials_for(
    token: OauthToken,
    client_id: str,
    client_secret: str,
) -> tuple[Credentials, bool]:
    """Build Google Credentials from a stored OauthToken.

    Refresh the access token if expired (detected via ``creds.expired``).
    Returns ``(credentials, was_refreshed)`` so the caller can persist the
    new token back to the database when ``was_refreshed`` is True.
    """
    from backend.app.google.oauth_client import GOOGLE_TOKEN_URI  # local import avoids circular

    scopes_list: list[str] = (
        token.scopes.split() if token.scopes else [_CALENDAR_SCOPE]
    )
    creds = Credentials(  # type: ignore[no-untyped-call]
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes_list,
    )

    was_refreshed = False
    if not creds.valid:
        await asyncio.to_thread(
            creds.refresh, google.auth.transport.requests.Request()
        )
        was_refreshed = True

    return creds, was_refreshed


def expiry_to_datetime(creds: Credentials) -> datetime | None:
    """Extract the expiry from a Credentials object as a naive UTC datetime."""
    expiry: datetime | None = getattr(creds, "expiry", None)
    if expiry is None:
        return None
    # google-auth sets expiry as a naive UTC datetime; normalise just in case.
    if expiry.tzinfo is not None:
        expiry = expiry.astimezone(UTC).replace(tzinfo=None)
    return expiry


async def list_calendars(creds: Credentials) -> list[dict[str, Any]]:
    """Return all calendars accessible by the authenticated Google account.

    Each item contains at minimum: ``id``, ``summary``, ``accessRole``, and
    optionally ``primary`` (bool, only on the primary calendar).

    *creds* must already be valid (i.e. call ``credentials_for`` first and
    persist any refresh before calling this function).
    """

    def _sync() -> list[dict[str, Any]]:
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


async def create_calendar(creds: Credentials, summary: str) -> dict[str, Any]:
    """Create a new Google Calendar and return its ``{id, summary}``.

    The new calendar is owned by the account that granted OAuth access.

    *creds* must already be valid (i.e. call ``credentials_for`` first and
    persist any refresh before calling this function).
    """

    def _sync() -> dict[str, Any]:
        service = build("calendar", "v3", credentials=creds)
        calendar_body = {"summary": summary}
        result = service.calendars().insert(body=calendar_body).execute()
        return {
            "id": result.get("id"),
            "summary": result.get("summary"),
        }

    return await asyncio.to_thread(_sync)
