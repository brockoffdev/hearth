"""Events API endpoints — Phase 6 Task A / Phase 7 Task C / Phase 10 Task A.

Routes:
  GET    /api/events                  — list events (filterable by status, upload_id)
  GET    /api/events/pending-count    — count of pending_review events for current user
  GET    /api/events/{id}             — single event detail
  PATCH  /api/events/{id}             — update fields + publish (syncs to GCal)
  POST   /api/events/{id}/republish   — retry publish for a pending_review event
  DELETE /api/events/{id}             — soft-delete (status → rejected, best-effort GCal removal)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_user
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import Event, EventCorrection, FamilyMember, Upload, User
from backend.app.google.publish import (
    GcalError,
    InvalidGrantError,
    NoCalendarError,
    NoOauthError,
    publish_event,
    unpublish_event,
)
from backend.app.uploads.storage import read_photo

logger = logging.getLogger(__name__)

router = APIRouter()

# Fields stored in correction before_json / after_json.
_CORRECTION_FIELDS = (
    "title", "start_dt", "end_dt", "all_day", "family_member_id", "location", "notes"
)

_MAX_LIMIT = 500
_DEFAULT_LIMIT = 100

# Statuses that represent "terminal rejected" states — excluded by default.
_EXCLUDED_STATUSES = {"rejected", "superseded"}

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class EventResponse(BaseModel):
    id: int
    upload_id: int | None
    family_member_id: int | None
    family_member_name: str | None
    family_member_color_hex: str | None
    title: str
    start_dt: datetime
    end_dt: datetime | None
    all_day: bool
    location: str | None
    notes: str | None
    confidence: float
    status: str
    google_event_id: str | None
    cell_crop_path: str | None
    has_cell_crop: bool
    raw_vlm_json: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}


class PatchEventRequest(BaseModel):
    title: str | None = None
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    all_day: bool | None = None
    family_member_id: int | None = None
    location: str | None = None
    notes: str | None = None

    model_config = {"extra": "forbid"}


class PendingCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------


def _to_response(event: Event, family_member: FamilyMember | None) -> EventResponse:
    return EventResponse(
        id=event.id,
        upload_id=event.upload_id,
        family_member_id=event.family_member_id,
        family_member_name=family_member.name if family_member else None,
        family_member_color_hex=family_member.color_hex_center if family_member else None,
        title=event.title,
        start_dt=event.start_dt,
        end_dt=event.end_dt,
        all_day=event.all_day,
        location=event.location,
        notes=event.notes,
        confidence=event.confidence,
        status=event.status,
        google_event_id=event.google_event_id,
        cell_crop_path=event.cell_crop_path,
        has_cell_crop=event.cell_crop_path is not None,
        raw_vlm_json=event.raw_vlm_json,
        created_at=event.created_at,
        updated_at=event.updated_at,
        published_at=event.published_at,
    )


def _snapshot_mutable_fields(event: Event) -> dict[str, object]:
    """Return a JSON-serialisable dict of user-editable event fields."""
    return {
        "title": event.title,
        "start_dt": event.start_dt,
        "end_dt": event.end_dt,
        "all_day": event.all_day,
        "family_member_id": event.family_member_id,
        "location": event.location,
        "notes": event.notes,
    }


def _strip_publish_failure_note(notes: str | None) -> str | None:
    """Remove the auto-publish failure trailer from notes."""
    if not notes:
        return notes
    cleaned = re.sub(r"\n\n\[Auto-publish failed:[^\]]*\]\s*$", "", notes)
    return cleaned or None


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------


async def _fetch_event_or_404(event_id: int, db: AsyncSession) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def _check_event_access(event: Event, current_user: User, db: AsyncSession) -> None:
    """Raise 403 if current_user may not access this event.

    Access is determined by the parent upload's owner, mirroring the
    _check_access() pattern from uploads.py.

    Events with upload_id=None (hand-created, not yet implemented) are
    accessible to any authenticated user since there is no owner to check.
    """
    if current_user.role == "admin":
        return
    if event.upload_id is None:
        # No upload owner — accessible to any authenticated user.
        return
    upload_result = await db.execute(select(Upload).where(Upload.id == event.upload_id))
    upload = upload_result.scalar_one_or_none()
    if upload is None or upload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    status: str | None = None,
    upload_id: int | None = None,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, object]:
    """List events.

    Returns `{items: EventResponse[], total: int}` with sort order
    `created_at DESC, start_dt ASC`.
    """
    limit = min(limit, _MAX_LIMIT)

    stmt = select(Event)

    if status is not None:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        stmt = stmt.where(Event.status.in_(statuses))
    else:
        stmt = stmt.where(Event.status.not_in(list(_EXCLUDED_STATUSES)))

    if upload_id is not None:
        stmt = stmt.where(Event.upload_id == upload_id)

    # Non-admin users only see events from their own uploads.
    if current_user.role != "admin":
        user_upload_ids = select(Upload.id).where(Upload.user_id == current_user.id)
        stmt = stmt.where(
            (Event.upload_id.in_(user_upload_ids)) | (Event.upload_id.is_(None))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(Event.created_at.desc(), Event.start_dt.asc()).limit(limit).offset(offset)
    events_result = await db.execute(stmt)
    events = list(events_result.scalars().all())

    # Bulk-load family members for joined data.
    member_ids = {e.family_member_id for e in events if e.family_member_id is not None}
    members_by_id: dict[int, FamilyMember] = {}
    if member_ids:
        members_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id.in_(member_ids))
        )
        for m in members_result.scalars().all():
            members_by_id[m.id] = m

    items = [
        _to_response(e, members_by_id.get(e.family_member_id) if e.family_member_id else None)
        for e in events
    ]
    return {"items": [item.model_dump() for item in items], "total": total}


@router.get("/pending-count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> PendingCountResponse:
    """Return the count of pending_review events visible to the current user."""
    if current_user.role == "admin":
        count_stmt = select(func.count()).where(Event.status == "pending_review")
    else:
        user_upload_ids = select(Upload.id).where(Upload.user_id == current_user.id)
        count_stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.status == "pending_review")
            .where(Event.upload_id.in_(user_upload_ids))
        )

    result = await db.execute(count_stmt)
    count = result.scalar_one()
    return PendingCountResponse(count=count)


@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> dict[str, object]:
    """Return a single event by ID."""
    event = await _fetch_event_or_404(event_id, db)
    await _check_event_access(event, current_user, db)

    member: FamilyMember | None = None
    if event.family_member_id is not None:
        member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == event.family_member_id)
        )
        member = member_result.scalar_one_or_none()

    return _to_response(event, member).model_dump()


@router.patch("/{event_id}")
async def patch_event(
    event_id: int,
    body: PatchEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> dict[str, object]:
    """Update event fields, mark as published, and sync to Google Calendar.

    If any fields changed: writes an EventCorrection row capturing the before/after.
    If no fields changed (confirm-as-is path): still publishes without a correction row.

    GCal sync is synchronous — the request blocks until the GCal call completes.
    On GCal failure the local status reverts to pending_review so the user can
    retry, but any field edits are preserved (the EventCorrection row stays).

    Exception: if the event was already published (google_event_id was set before
    this PATCH), status is NOT reverted on failure — it was already 'published'.
    """
    event = await _fetch_event_or_404(event_id, db)
    await _check_event_access(event, current_user, db)

    if event.status in ("rejected", "superseded"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update an event with status '{event.status}'",
        )

    was_already_published = event.google_event_id is not None

    updates = body.model_dump(exclude_unset=True)
    before_snapshot = _snapshot_mutable_fields(event)

    for field, value in updates.items():
        setattr(event, field, value)

    after_snapshot = _snapshot_mutable_fields(event)

    # Detect whether any mutable field actually changed.
    changed = before_snapshot != after_snapshot

    if changed:
        correction = EventCorrection(
            event_id=event.id,
            before_json=json.dumps(before_snapshot, default=str),
            after_json=json.dumps(after_snapshot, default=str),
            cell_crop_path=event.cell_crop_path,
            corrected_by=current_user.id,
        )
        db.add(correction)

    event.status = "published"
    event.updated_at = datetime.now(UTC).replace(tzinfo=None)

    await db.commit()

    try:
        await publish_event(db, event.id)
    except NoOauthError as exc:
        if not was_already_published:
            event.status = "pending_review"
            await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Google Calendar not connected. Admin must complete /setup/google.",
        ) from exc
    except InvalidGrantError as exc:
        if not was_already_published:
            event.status = "pending_review"
            await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Google Calendar token expired. Admin must reconnect.",
        ) from exc
    except NoCalendarError as exc:
        if not was_already_published:
            event.status = "pending_review"
            await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Family member has no Google Calendar mapping.",
        ) from exc
    except GcalError as exc:
        if not was_already_published:
            event.status = "pending_review"
            await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Google Calendar error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error publishing event %d to Google Calendar", event_id)
        if not was_already_published:
            event.status = "pending_review"
            await db.commit()
        raise HTTPException(
            status_code=502,
            detail="Unexpected error publishing to Google Calendar",
        ) from exc

    await db.refresh(event)

    member: FamilyMember | None = None
    if event.family_member_id is not None:
        member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == event.family_member_id)
        )
        member = member_result.scalar_one_or_none()

    return _to_response(event, member).model_dump()


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> None:
    """Soft-delete an event by setting status to 'rejected'.

    If the event has a google_event_id, attempts to remove it from Google Calendar
    first.  GCal cleanup is best-effort: any failure is logged and the soft-reject
    proceeds regardless.  The caller always gets 204.

    Returns 204 No Content.
    """
    event = await _fetch_event_or_404(event_id, db)
    await _check_event_access(event, current_user, db)

    if event.status == "rejected":
        raise HTTPException(status_code=400, detail="Event is already rejected")

    if event.google_event_id is not None:
        try:
            await unpublish_event(db, event.id)
        except (NoOauthError, InvalidGrantError) as exc:
            logger.warning(
                "Could not remove GCal event for event %d during rejection (OAuth issue): %s",
                event_id,
                exc,
            )
        except GcalError as exc:
            logger.warning(
                "Could not remove GCal event for event %d during rejection (GCal error): %s",
                event_id,
                exc,
            )
        except Exception:
            logger.exception(
                "Unexpected error removing GCal event for event %d during rejection",
                event_id,
            )

    event.status = "rejected"
    event.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return None


@router.post("/{event_id}/republish")
async def republish_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> dict[str, object]:
    """Retry publishing a pending_review event to Google Calendar.

    Unlike PATCH, this path is only valid for pending_review events and clears
    the auto-publish failure breadcrumb from notes on success so the row looks
    clean without requiring an edit.
    """
    event = await _fetch_event_or_404(event_id, db)
    await _check_event_access(event, current_user, db)

    if event.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail="Event is not pending review; cannot republish",
        )

    event.status = "published"
    event.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    try:
        await publish_event(db, event.id)
    except NoOauthError as exc:
        event.status = "pending_review"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Google Calendar not connected. Admin must complete /setup/google.",
        ) from exc
    except InvalidGrantError as exc:
        event.status = "pending_review"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Google Calendar token expired. Admin must reconnect.",
        ) from exc
    except NoCalendarError as exc:
        event.status = "pending_review"
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Family member has no Google Calendar mapping.",
        ) from exc
    except GcalError as exc:
        event.status = "pending_review"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Google Calendar error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error republishing event %d to Google Calendar", event_id)
        event.status = "pending_review"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail="Unexpected error publishing to Google Calendar",
        ) from exc

    event.notes = _strip_publish_failure_note(event.notes)
    await db.commit()
    await db.refresh(event)

    member: FamilyMember | None = None
    if event.family_member_id is not None:
        member_result = await db.execute(
            select(FamilyMember).where(FamilyMember.id == event.family_member_id)
        )
        member = member_result.scalar_one_or_none()

    return _to_response(event, member).model_dump()


@router.get("/{event_id}/cell-crop")
async def get_event_cell_crop(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return the raw cell-crop image bytes for an event."""
    event = await _fetch_event_or_404(event_id, db)
    await _check_event_access(event, current_user, db)

    if event.cell_crop_path is None:
        raise HTTPException(status_code=404, detail="No cell crop for this event")

    resolved = (settings.data_dir / event.cell_crop_path).resolve()
    if not resolved.is_relative_to(settings.data_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid cell crop path")

    try:
        image_bytes = await read_photo(event.cell_crop_path, settings.data_dir)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Cell crop file not found on disk"
        ) from exc

    ext = Path(event.cell_crop_path).suffix.lower()
    media_type = _EXT_TO_MEDIA_TYPE.get(ext, "application/octet-stream")
    return Response(content=image_bytes, media_type=media_type)
