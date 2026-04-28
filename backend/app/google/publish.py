"""GCal publish/unpublish helpers for Hearth events.

Centralises the flow of pushing an Event row to Google Calendar (insert or
patch) and pulling it back (delete).  Consumers: pipeline auto-publish
(Task B), review-queue PATCH (Task C), DELETE (Task C).

mypy: the Google auth libraries have partial typing; per-module overrides in
pyproject.toml suppress missing-import / untyped-call errors for those packages.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.db.models import Event, FamilyMember, OauthToken, Setting
from backend.app.google.calendar_client import (
    credentials_for,
    delete_event,
    expiry_to_datetime,
    insert_event,
    patch_event,
)

# Settings keys — must match api/google.py
_KEY_CLIENT_ID = "google_oauth_client_id"
_KEY_CLIENT_SECRET = "google_oauth_client_secret"


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class PublishError(Exception):
    """Base error raised when an event cannot be published/unpublished."""


class NoOauthError(PublishError):
    """oauth_tokens row is missing — OAuth has never been completed."""


class InvalidGrantError(PublishError):
    """Refresh token is revoked or expired beyond reuse (invalid_grant)."""


class NoCalendarError(PublishError):
    """Family member missing or has no google_calendar_id."""


class GcalError(PublishError):
    """Unexpected error from the Google Calendar API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_setting(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row is not None else None


def _build_event_body(event: Event) -> dict[str, Any]:
    """Build the GCal event body dict from an Event row."""
    footer = (
        f"\n\n— Auto-imported by Hearth on {datetime.now(UTC).date().isoformat()} "
        f"from upload #{event.upload_id}"
    )
    description = ((event.notes or "") + footer).strip()

    if event.all_day:
        start_date = event.start_dt.date()
        # RFC 5545 / GCal: end.date is exclusive, so add one day.
        if event.end_dt is not None:
            end_date = event.end_dt.date() + timedelta(days=1)
        else:
            end_date = start_date + timedelta(days=1)
        timing: dict[str, Any] = {
            "start": {"date": start_date.isoformat()},
            "end": {"date": end_date.isoformat()},
        }
    else:
        start_dt_str = event.start_dt.isoformat() + "Z"
        if event.end_dt is not None:
            end_dt_str = event.end_dt.isoformat() + "Z"
        else:
            end_dt_str = (event.start_dt + timedelta(hours=1)).isoformat() + "Z"
        timing = {
            "start": {"dateTime": start_dt_str},
            "end": {"dateTime": end_dt_str},
        }

    return {
        "summary": event.title,
        "description": description,
        "extendedProperties": {
            "private": {"hearthEventId": str(event.id)},
        },
        **timing,
        "location": event.location,
    }


async def _resolve_credentials(
    session: AsyncSession,
    settings: Settings,
) -> tuple[Any, OauthToken]:
    """Load and refresh credentials; return (creds, token_row).

    Persists a refreshed access token back to OauthToken when was_refreshed.
    Raises NoOauthError, InvalidGrantError, or GcalError as appropriate.
    """
    result = await session.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = result.scalar_one_or_none()
    if token_row is None or not token_row.refresh_token:
        raise NoOauthError("No OAuth token row — complete the setup wizard first")

    client_id = await _get_setting(session, _KEY_CLIENT_ID)
    client_secret = await _get_setting(session, _KEY_CLIENT_SECRET)
    if not client_id or not client_secret:
        raise NoOauthError("OAuth credentials not configured")

    try:
        creds, was_refreshed = await credentials_for(token_row, client_id, client_secret)
    except RefreshError as exc:
        raise InvalidGrantError(str(exc)) from exc

    if was_refreshed:
        token_row.access_token = creds.token
        token_row.expires_at = expiry_to_datetime(creds)
        await session.commit()

    return creds, token_row


async def _resolve_calendar_id(session: AsyncSession, event: Event) -> str:
    """Return the google_calendar_id for the event's family member.

    Raises NoCalendarError if family_member_id is None, member row is missing,
    or member has no google_calendar_id set.
    """
    if event.family_member_id is None:
        raise NoCalendarError(
            f"Event {event.id} has no family_member_id; cannot determine calendar"
        )
    result = await session.execute(
        select(FamilyMember).where(FamilyMember.id == event.family_member_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NoCalendarError(
            f"FamilyMember {event.family_member_id} not found for event {event.id}"
        )
    if not member.google_calendar_id:
        raise NoCalendarError(
            f"FamilyMember '{member.name}' has no google_calendar_id linked"
        )
    return member.google_calendar_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def publish_event(
    session: AsyncSession,
    event_id: int,
    *,
    settings: Settings | None = None,
) -> Event:
    """Push or repush an Event to Google Calendar.

    - Looks up the Event row + its FamilyMember + the singleton OauthToken.
    - Resolves credentials (refreshes access token if expired; persists refresh).
    - If event.google_event_id is None: calls insert_event, persists
      google_event_id + published_at.
    - If event.google_event_id is set: calls patch_event with current event fields.
    - Returns the refreshed Event row.

    Raises:
        PublishError when the event cannot be published.  Subtypes:
          - NoOauthError      -- oauth_tokens row missing.
          - InvalidGrantError -- refresh failed (token revoked / expired beyond reuse).
          - NoCalendarError   -- family member missing google_calendar_id.
          - GcalError         -- any other googleapiclient error; .status_code attached.
    """
    _settings = settings or get_settings()

    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise PublishError(f"Event {event_id} not found")

    creds, _ = await _resolve_credentials(session, _settings)
    calendar_id = await _resolve_calendar_id(session, event)
    event_body = _build_event_body(event)

    try:
        if event.google_event_id is None:
            gcal_result = await insert_event(creds, calendar_id, event_body)
            event.google_event_id = gcal_result["id"]
        else:
            await patch_event(creds, calendar_id, event.google_event_id, event_body)
    except HttpError as exc:
        raise GcalError(str(exc), status_code=exc.resp.status) from exc

    event.published_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(event)
    return event


async def unpublish_event(
    session: AsyncSession,
    event_id: int,
    *,
    settings: Settings | None = None,
) -> Event:
    """Delete the GCal event linked to *event_id* (if any) and clear google_event_id.

    No-op if event.google_event_id is None.
    Raises the same exceptions as publish_event for OAuth/credential issues.
    Idempotent w.r.t. GCal: 404/410 are swallowed (the GCal event may already be gone).
    """
    _settings = settings or get_settings()

    result = await session.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise PublishError(f"Event {event_id} not found")

    if event.google_event_id is None:
        return event

    creds, _ = await _resolve_credentials(session, _settings)
    calendar_id = await _resolve_calendar_id(session, event)

    try:
        await delete_event(creds, calendar_id, event.google_event_id)
    except HttpError as exc:
        raise GcalError(str(exc), status_code=exc.resp.status) from exc

    event.google_event_id = None
    await session.commit()
    await session.refresh(event)
    return event
