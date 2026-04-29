"""GCal → Hearth sync: reconcile local Event rows against Google Calendar.

This module is the authoritative sync direction: GCal wins.  Events deleted
in GCal are soft-deleted here (status='superseded'); events created directly
in GCal are imported; edits in GCal update the local row.

Only events with ``google_event_id IS NOT NULL`` and
``status IN ('published', 'auto_published')`` are candidates for deletion.
The ``pending_review`` flow is never touched.

mypy: the Google auth libraries have partial typing; per-module overrides in
pyproject.toml suppress missing-import / untyped-call errors for those packages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.db.models import Event, FamilyMember
from backend.app.google.calendar_client import list_events_in_calendar
from backend.app.google.publish import NoOauthError, _resolve_credentials

logger = logging.getLogger(__name__)


def _parse_dt(dt_field: dict[str, Any]) -> tuple[datetime, bool]:
    """Parse a GCal start/end field into (datetime, all_day).

    GCal returns either ``{"date": "YYYY-MM-DD"}`` for all-day events or
    ``{"dateTime": "...", "timeZone": "..."}`` for timed events.
    Returns a naive UTC datetime to match the existing convention.
    """
    if "date" in dt_field:
        # All-day: parse the date string, return midnight UTC, mark all_day=True
        d = datetime.strptime(dt_field["date"], "%Y-%m-%d")
        return d, True
    # Timed: parse the ISO-8601 dateTime string
    dt_str: str = dt_field["dateTime"]
    # Strip trailing Z or parse as aware, then normalise to naive UTC
    if dt_str.endswith("Z"):
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
    else:
        # May have +HH:MM offset — use fromisoformat (Python 3.11+ handles Z too)
        try:
            aware = datetime.fromisoformat(dt_str)
        except ValueError:
            # Fallback: strip offset and treat as UTC
            aware = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S")
            return aware, False
        if aware.tzinfo is not None:
            dt = aware.astimezone(UTC).replace(tzinfo=None)
        else:
            dt = aware
    return dt, False


async def sync_from_gcal(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    window_days_past: int = 30,
    window_days_future: int = 180,
) -> dict[str, int]:
    """Reconcile local Event rows against Google Calendar.

    Returns a stats dict: {imported, updated, deleted, skipped, errors}.
    """
    _settings = settings or get_settings()
    stats: dict[str, int] = {
        "imported": 0,
        "updated": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": 0,
    }

    # 1. Load all FamilyMember rows with a google_calendar_id set.
    members_result = await session.execute(
        select(FamilyMember).where(FamilyMember.google_calendar_id.isnot(None))
    )
    members = list(members_result.scalars().all())

    if not members:
        logger.info("GCal sync: no family members with google_calendar_id — skipping")
        return stats

    # 2. Resolve credentials once for all calendars.
    try:
        creds, _ = await _resolve_credentials(session, _settings)
    except NoOauthError as exc:
        logger.warning("GCal sync: no OAuth token — skipping sync (%s)", exc)
        return stats
    except Exception:
        logger.exception("GCal sync: failed to resolve credentials")
        stats["errors"] += 1
        return stats

    now = datetime.now(UTC).replace(tzinfo=None)
    time_min = now - timedelta(days=window_days_past)
    time_max = now + timedelta(days=window_days_future)

    # Track all GCal event IDs we see across all calendars (for deletion sweep).
    seen_event_ids: set[str] = set()
    synced_member_ids: list[int] = []

    # 3. Process each family member's calendar.
    for member in members:
        calendar_id: str = member.google_calendar_id  # type: ignore[assignment]
        try:
            gcal_events = await list_events_in_calendar(
                creds,
                calendar_id,
                time_min=time_min,
                time_max=time_max,
            )
        except Exception:
            logger.exception(
                "GCal sync: error fetching calendar for member '%s' (%s)",
                member.name,
                calendar_id,
            )
            stats["errors"] += 1
            continue

        synced_member_ids.append(member.id)

        for gcal_event in gcal_events:
            gcal_id: str = gcal_event.get("id", "")
            if not gcal_id:
                stats["skipped"] += 1
                continue

            seen_event_ids.add(gcal_id)

            # Skip cancelled events
            if gcal_event.get("status") == "cancelled":
                stats["skipped"] += 1
                continue

            # Parse start/end times.
            start_field = gcal_event.get("start", {})
            end_field = gcal_event.get("end", {})
            if not start_field:
                stats["skipped"] += 1
                continue

            try:
                start_dt, all_day = _parse_dt(start_field)
                end_dt: datetime | None = None
                if end_field:
                    end_dt, _ = _parse_dt(end_field)
                    # For all-day events GCal end date is exclusive (+1 day);
                    # subtract it back to match Hearth's inclusive convention.
                    if all_day and end_dt is not None:
                        end_dt = end_dt - timedelta(days=1)
                        # If end == start, treat as single-day (no end_dt needed)
                        if end_dt == start_dt:
                            end_dt = None
            except Exception:
                logger.warning(
                    "GCal sync: could not parse date for event %s — skipping", gcal_id
                )
                stats["skipped"] += 1
                continue

            title: str = gcal_event.get("summary") or "(no title)"
            location: str | None = gcal_event.get("location")

            # Match priority 1: extendedProperties.private.hearthEventId
            hearth_event_id: str | None = None
            ext_props = gcal_event.get("extendedProperties") or {}
            private_props = ext_props.get("private") or {}
            hearth_event_id = private_props.get("hearthEventId")

            local_event: Event | None = None

            if hearth_event_id is not None:
                try:
                    hid = int(hearth_event_id)
                    result = await session.execute(
                        select(Event).where(Event.id == hid)
                    )
                    local_event = result.scalar_one_or_none()
                except (ValueError, TypeError):
                    pass

            # Match priority 2: google_event_id
            if local_event is None:
                result2 = await session.execute(
                    select(Event).where(Event.google_event_id == gcal_id)
                )
                local_event = result2.scalar_one_or_none()

            if local_event is not None:
                # Update existing event with GCal's authoritative data.
                local_event.title = title
                local_event.start_dt = start_dt
                local_event.end_dt = end_dt
                local_event.all_day = all_day
                local_event.location = location
                local_event.status = "published"
                local_event.google_event_id = gcal_id
                local_event.updated_at = now
                stats["updated"] += 1
            else:
                # Import: create a new local Event row.
                new_event = Event(
                    upload_id=None,
                    family_member_id=member.id,
                    title=title,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    all_day=all_day,
                    location=location,
                    confidence=1.0,
                    status="published",
                    google_event_id=gcal_id,
                    cell_crop_path=None,
                    raw_vlm_json=None,
                    published_at=now,
                )
                session.add(new_event)
                stats["imported"] += 1

    # Commit all inserts/updates so far.
    await session.commit()

    # 4. Deletion sweep: soft-delete local events whose GCal event is gone.
    if synced_member_ids and seen_event_ids:
        stale_result = await session.execute(
            select(Event).where(
                Event.google_event_id.isnot(None),
                Event.status.in_(["published", "auto_published"]),
                Event.family_member_id.in_(synced_member_ids),
                Event.google_event_id.notin_(seen_event_ids),
            )
        )
        stale_events = list(stale_result.scalars().all())
        for stale in stale_events:
            stale.status = "superseded"
            stale.updated_at = now
            stats["deleted"] += 1
        if stale_events:
            await session.commit()
    elif synced_member_ids and not seen_event_ids:
        # We processed calendars but got no events back — could be empty
        # calendars or all events were outside the window. Still run the sweep
        # since any local events with google_event_ids are now missing in GCal.
        stale_result = await session.execute(
            select(Event).where(
                Event.google_event_id.isnot(None),
                Event.status.in_(["published", "auto_published"]),
                Event.family_member_id.in_(synced_member_ids),
            )
        )
        stale_events = list(stale_result.scalars().all())
        for stale in stale_events:
            stale.status = "superseded"
            stale.updated_at = now
            stats["deleted"] += 1
        if stale_events:
            await session.commit()

    return stats
