"""Tests for backend/app/uploads/few_shot.py — fetch_recent_corrections.

Phase 5 Task A: verify the helper correctly retrieves, orders, and filters
corrections from the event_corrections table.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Event, EventCorrection, User
from backend.app.uploads.few_shot import _extract_title, fetch_recent_corrections

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(username: str = "reviewer") -> User:
    return User(username=username, password_hash="$2b$12$x", role="admin")


def _event() -> Event:
    return Event(
        title="Test event",
        start_dt=datetime(2026, 5, 10, 9, 0),
        status="auto_published",
    )


def _correction(
    event_id: int,
    corrected_by: int,
    before_json: str,
    after_json: str,
    corrected_at: datetime | None = None,
) -> EventCorrection:
    kwargs: dict[str, object] = {
        "event_id": event_id,
        "before_json": before_json,
        "after_json": after_json,
        "corrected_by": corrected_by,
    }
    if corrected_at is not None:
        kwargs["corrected_at"] = corrected_at
    return EventCorrection(**kwargs)


# ---------------------------------------------------------------------------
# fetch_recent_corrections tests
# ---------------------------------------------------------------------------


async def test_fetch_recent_corrections_empty_table(db_session: AsyncSession) -> None:
    """Empty event_corrections table → returns empty tuple."""
    result = await fetch_recent_corrections(db_session, limit=10)
    assert result == ()


async def test_fetch_recent_corrections_returns_most_recent_first(
    db_session: AsyncSession,
) -> None:
    """Corrections are returned in DESC order by corrected_at."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    corrections = [
        _correction(
            event.id,
            user.id,
            f'{{"title": "Before{i}"}}',
            f'{{"title": "After{i}"}}',
            corrected_at=base + timedelta(minutes=i),
        )
        for i in range(3)
    ]
    for c in corrections:
        db_session.add(c)
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=10)

    # Should be newest first (index 2 is newest)
    assert len(result) == 3
    assert result[0]["before"] == "Before2"
    assert result[1]["before"] == "Before1"
    assert result[2]["before"] == "Before0"


async def test_fetch_recent_corrections_respects_limit(
    db_session: AsyncSession,
) -> None:
    """With 5 rows and limit=3, only 3 corrections are returned."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(5):
        db_session.add(
            _correction(
                event.id,
                user.id,
                f'{{"title": "Before{i}"}}',
                f'{{"title": "After{i}"}}',
                corrected_at=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=3)
    assert len(result) == 3


async def test_fetch_recent_corrections_extracts_title(
    db_session: AsyncSession,
) -> None:
    """Extracts 'title' field from before_json and after_json."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    db_session.add(
        _correction(
            event.id,
            user.id,
            before_json='{"title":"Pikuagk Place","raw_text":"Pikuagk Place"}',
            after_json='{"title":"Pineapple Place"}',
        )
    )
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=10)
    assert result == ({"before": "Pikuagk Place", "after": "Pineapple Place"},)


async def test_fetch_recent_corrections_falls_back_to_raw_text(
    db_session: AsyncSession,
) -> None:
    """Falls back to 'raw_text' when 'title' is absent from before_json."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    db_session.add(
        _correction(
            event.id,
            user.id,
            before_json='{"raw_text":"ScrawledText"}',
            after_json='{"title":"Clean Title"}',
        )
    )
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=10)
    assert result == ({"before": "ScrawledText", "after": "Clean Title"},)


async def test_fetch_recent_corrections_skips_malformed_json(
    db_session: AsyncSession,
) -> None:
    """Rows with unparseable JSON are silently skipped."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    db_session.add(
        _correction(
            event.id,
            user.id,
            before_json="not valid json {{{",
            after_json='{"title":"Fixed"}',
        )
    )
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=10)
    assert result == ()


async def test_fetch_recent_corrections_skips_when_before_equals_after(
    db_session: AsyncSession,
) -> None:
    """Rows where before == after (no real correction) are skipped."""
    user = _user()
    db_session.add(user)
    event = _event()
    db_session.add(event)
    await db_session.flush()

    db_session.add(
        _correction(
            event.id,
            user.id,
            before_json='{"title":"Same Title"}',
            after_json='{"title":"Same Title"}',
        )
    )
    await db_session.commit()

    result = await fetch_recent_corrections(db_session, limit=10)
    assert result == ()


# ---------------------------------------------------------------------------
# _extract_title unit tests
# ---------------------------------------------------------------------------


def test_extract_title_priorities_title_over_raw_text() -> None:
    """When both 'title' and 'raw_text' are present, 'title' wins."""
    raw = '{"title": "The Title", "raw_text": "Some raw text"}'
    assert _extract_title(raw) == "The Title"


def test_extract_title_handles_invalid_json() -> None:
    """Invalid JSON returns None without raising."""
    assert _extract_title("not-json{{{") is None


def test_extract_title_handles_non_dict_json() -> None:
    """JSON that is not a dict (e.g. a bare string) returns None."""
    assert _extract_title('"just a string"') is None


def test_extract_title_returns_none_when_both_fields_missing() -> None:
    """JSON with neither 'title' nor 'raw_text' returns None."""
    assert _extract_title('{"confidence": 0.9}') is None


def test_extract_title_strips_whitespace() -> None:
    """Title/raw_text values with leading/trailing whitespace are stripped."""
    assert _extract_title('{"title": "  Padded  "}') == "Padded"


def test_extract_title_empty_title_falls_back_to_raw_text() -> None:
    """Empty string title falls back to raw_text."""
    assert _extract_title('{"title": "", "raw_text": "fallback"}') == "fallback"
