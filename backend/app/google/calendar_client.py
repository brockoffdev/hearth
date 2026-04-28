"""Google Calendar API client wrappers.

These helpers wrap ``googleapiclient.discovery.build("calendar", "v3", ...)``
and surface only the functionality Phases 2-7 need: listing calendars,
creating a new calendar, and CRUD operations on calendar events.

The underlying Google client library is synchronous, so all blocking calls
are dispatched via ``asyncio.to_thread``.

``credentials_for`` handles token refresh and returns a ``was_refreshed``
flag; the caller is responsible for persisting the updated access token back
to the database if ``was_refreshed`` is True.  All other helpers accept a
ready-to-use ``Credentials`` object so this module has no database dependencies.

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
from googleapiclient.errors import HttpError

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


# ---------------------------------------------------------------------------
# Event CRUD helpers (Phase 7)
# ---------------------------------------------------------------------------

_EVENT_FIELDS = {"id", "htmlLink", "status", "updated", "extendedProperties"}


def _prune_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only the fields callers need; GCal returns many more."""
    return {k: raw[k] for k in _EVENT_FIELDS if k in raw}


async def insert_event(
    creds: Credentials,
    calendar_id: str,
    event_body: dict[str, Any],
) -> dict[str, Any]:
    """Insert a new event into *calendar_id* and return the pruned event dict."""

    def _sync() -> dict[str, Any]:
        service = build("calendar", "v3", credentials=creds)
        result: dict[str, Any] = (
            service.events()
            .insert(calendarId=calendar_id, body=event_body)
            .execute()
        )
        return _prune_event(result)

    return await asyncio.to_thread(_sync)


async def patch_event(
    creds: Credentials,
    calendar_id: str,
    event_id: str,
    event_body: dict[str, Any],
) -> dict[str, Any]:
    """Partially update *event_id* in *calendar_id* and return the pruned event dict."""

    def _sync() -> dict[str, Any]:
        service = build("calendar", "v3", credentials=creds)
        result: dict[str, Any] = (
            service.events()
            .patch(calendarId=calendar_id, eventId=event_id, body=event_body)
            .execute()
        )
        return _prune_event(result)

    return await asyncio.to_thread(_sync)


async def delete_event(
    creds: Credentials,
    calendar_id: str,
    event_id: str,
) -> None:
    """Delete *event_id* from *calendar_id*.

    Idempotent: 404 and 410 responses are silently swallowed so callers can
    treat the GCal event as already gone without special-casing.
    """

    def _sync() -> None:
        service = build("calendar", "v3", credentials=creds)
        try:
            service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
        except HttpError as exc:
            if exc.resp.status in (404, 410):
                return
            raise

    await asyncio.to_thread(_sync)


async def get_event(
    creds: Credentials,
    calendar_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    """Return the full event dict for *event_id*, or ``None`` on 404/410."""

    def _sync() -> dict[str, Any] | None:
        service = build("calendar", "v3", credentials=creds)
        try:
            result: dict[str, Any] = (
                service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            return result
        except HttpError as exc:
            if exc.resp.status in (404, 410):
                return None
            raise

    return await asyncio.to_thread(_sync)
