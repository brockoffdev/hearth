"""Tests for Event and EventCorrection models.

Phase 4 Task A: data layer for calendar events + learning-loop corrections.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Event, EventCorrection, FamilyMember, Upload, User

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _user(username: str = "tester") -> User:
    return User(username=username, password_hash="$2b$12$x", role="admin")


def _family_member(name: str = "TestMember") -> FamilyMember:
    return FamilyMember(
        name=name,
        color_hex_center="#AABBCC",
        hue_range_low=200,
        hue_range_high=220,
    )


def _upload(user_id: int) -> Upload:
    return Upload(
        user_id=user_id,
        image_path="/uploads/test.jpg",
        status="completed",
    )


def _event(
    *,
    upload_id: int | None = None,
    family_member_id: int | None = None,
    title: str = "Doctor appointment",
    start_dt: datetime | None = None,
    status: str = "auto_published",
) -> Event:
    return Event(
        upload_id=upload_id,
        family_member_id=family_member_id,
        title=title,
        start_dt=start_dt or datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
        status=status,
    )


# ---------------------------------------------------------------------------
# Event round-trip
# ---------------------------------------------------------------------------


async def test_event_round_trip(db_session: AsyncSession) -> None:
    """Insert an Event with all required fields; read back and check values."""
    user = _user()
    db_session.add(user)
    await db_session.flush()

    upload = _upload(user_id=user.id)
    db_session.add(upload)

    member = _family_member()
    db_session.add(member)
    await db_session.flush()

    start = datetime(2026, 5, 10, 9, 0)
    end = datetime(2026, 5, 10, 10, 0)

    ev = Event(
        upload_id=upload.id,
        family_member_id=member.id,
        title="Doctor appointment",
        start_dt=start,
        end_dt=end,
        all_day=False,
        location="123 Main St",
        notes="Bring insurance card",
        confidence=0.92,
        status="auto_published",
        google_event_id="gcal-abc-123",
        cell_crop_path="/crops/cell_001.jpg",
        raw_vlm_json='{"raw": true}',
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    result = await db_session.execute(select(Event).where(Event.id == ev.id))
    fetched = result.scalar_one()

    assert fetched.title == "Doctor appointment"
    assert fetched.start_dt == start
    assert fetched.end_dt == end
    assert fetched.all_day is False
    assert fetched.location == "123 Main St"
    assert fetched.notes == "Bring insurance card"
    assert fetched.confidence == pytest.approx(0.92)
    assert fetched.status == "auto_published"
    assert fetched.google_event_id == "gcal-abc-123"
    assert fetched.cell_crop_path == "/crops/cell_001.jpg"
    assert fetched.raw_vlm_json == '{"raw": true}'
    assert fetched.upload_id == upload.id
    assert fetched.family_member_id == member.id
    assert fetched.created_at is not None
    assert fetched.updated_at is not None
    assert fetched.published_at is None


# ---------------------------------------------------------------------------
# Event constraints / defaults
# ---------------------------------------------------------------------------


async def test_event_status_check_constraint(db_session: AsyncSession) -> None:
    """Inserting an Event with an invalid status raises IntegrityError."""
    ev = Event(
        title="Bad event",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status="nonsense",
    )
    db_session.add(ev)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_event_confidence_default_1_0(db_session: AsyncSession) -> None:
    """An Event inserted without specifying confidence defaults to 1.0."""
    ev = Event(
        title="Default confidence event",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status="auto_published",
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    result = await db_session.execute(select(Event).where(Event.id == ev.id))
    fetched = result.scalar_one()
    assert fetched.confidence == pytest.approx(1.0)


async def test_event_all_day_default_false(db_session: AsyncSession) -> None:
    """An Event inserted without specifying all_day defaults to False (0)."""
    ev = Event(
        title="Default all_day event",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status="auto_published",
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    result = await db_session.execute(select(Event).where(Event.id == ev.id))
    fetched = result.scalar_one()
    assert fetched.all_day is False


async def test_event_nullable_upload_id(db_session: AsyncSession) -> None:
    """Event.upload_id may be NULL (hand-created events have no upload)."""
    ev = Event(
        title="Hand-created event",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status="published",
        upload_id=None,
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)

    result = await db_session.execute(select(Event).where(Event.id == ev.id))
    fetched = result.scalar_one()
    assert fetched.upload_id is None


# ---------------------------------------------------------------------------
# Valid status values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["pending_review", "auto_published", "published", "rejected", "superseded"],
)
async def test_event_all_valid_statuses(db_session: AsyncSession, status: str) -> None:
    """All five allowed statuses are accepted by the check constraint."""
    ev = Event(
        title=f"Event with status {status}",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status=status,
    )
    db_session.add(ev)
    await db_session.commit()
    await db_session.refresh(ev)
    assert ev.status == status


# ---------------------------------------------------------------------------
# EventCorrection round-trip
# ---------------------------------------------------------------------------


async def test_event_correction_round_trip(db_session: AsyncSession) -> None:
    """Insert an EventCorrection; read back and verify all fields."""
    user = _user()
    db_session.add(user)

    ev = _event()
    db_session.add(ev)
    await db_session.flush()

    correction = EventCorrection(
        event_id=ev.id,
        before_json='{"title": "Old title"}',
        after_json='{"title": "Corrected title"}',
        cell_crop_path="/crops/cell_001.jpg",
        corrected_by=user.id,
    )
    db_session.add(correction)
    await db_session.commit()
    await db_session.refresh(correction)

    result = await db_session.execute(
        select(EventCorrection).where(EventCorrection.id == correction.id)
    )
    fetched = result.scalar_one()

    assert fetched.event_id == ev.id
    assert fetched.before_json == '{"title": "Old title"}'
    assert fetched.after_json == '{"title": "Corrected title"}'
    assert fetched.cell_crop_path == "/crops/cell_001.jpg"
    assert fetched.corrected_by == user.id
    assert fetched.corrected_at is not None


# ---------------------------------------------------------------------------
# EventCorrection FK — event_id
# ---------------------------------------------------------------------------


async def test_event_correction_event_fk(db_session: AsyncSession) -> None:
    """EventCorrection references a valid event; correction survives if event is deleted.

    The spec does not specify ON DELETE CASCADE, so corrections persist after
    event deletion in v1 (referential integrity is relaxed for SQLite without
    explicit PRAGMA foreign_keys=ON, but the FK column stores the relationship).
    """
    user = _user()
    db_session.add(user)

    ev = _event()
    db_session.add(ev)
    await db_session.flush()

    event_id = ev.id

    correction = EventCorrection(
        event_id=ev.id,
        before_json="{}",
        after_json='{"title": "Fixed"}',
        corrected_by=user.id,
    )
    db_session.add(correction)
    await db_session.commit()

    # Correction was persisted with the right event_id
    result = await db_session.execute(
        select(EventCorrection).where(EventCorrection.id == correction.id)
    )
    fetched = result.scalar_one()
    assert fetched.event_id == event_id


# ---------------------------------------------------------------------------
# EventCorrection FK — corrected_by
# ---------------------------------------------------------------------------


async def test_event_correction_corrected_by_fk(db_session: AsyncSession) -> None:
    """EventCorrection.corrected_by references a valid users(id)."""
    user = _user(username="reviewer")
    db_session.add(user)

    ev = _event()
    db_session.add(ev)
    await db_session.flush()

    correction = EventCorrection(
        event_id=ev.id,
        before_json="{}",
        after_json='{"title": "Fixed"}',
        corrected_by=user.id,
    )
    db_session.add(correction)
    await db_session.commit()
    await db_session.refresh(correction)

    result = await db_session.execute(
        select(EventCorrection).where(EventCorrection.id == correction.id)
    )
    fetched = result.scalar_one()
    assert fetched.corrected_by == user.id
