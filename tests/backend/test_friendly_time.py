"""Tests for backend.app.uploads.friendly_time helpers.

All 8 branches of format_relative_started_at and format_relative_finished_at,
plus format_thumb_label format check.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.uploads.friendly_time import (
    format_relative_finished_at,
    format_relative_started_at,
    format_thumb_label,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 4, 27, 8, 38, 0, tzinfo=UTC)


def _ts(seconds_ago: float) -> datetime:
    return _now() - timedelta(seconds=seconds_ago)


# ---------------------------------------------------------------------------
# format_thumb_label
# ---------------------------------------------------------------------------


def test_format_thumb_label_stable_format() -> None:
    """format_thumb_label returns 'Apr 27, 8:38 AM' for the test timestamp."""
    ts = datetime(2026, 4, 27, 8, 38, 0, tzinfo=UTC)
    result = format_thumb_label(ts)
    assert result == "Apr 27, 8:38 AM"


def test_format_thumb_label_pm_time() -> None:
    """PM times render correctly."""
    ts = datetime(2026, 4, 27, 15, 5, 0, tzinfo=UTC)
    result = format_thumb_label(ts)
    assert result == "Apr 27, 3:05 PM"


def test_format_thumb_label_no_leading_zero_on_hour() -> None:
    """Hour has no leading zero: '8:38 AM', not '08:38 AM'."""
    ts = datetime(2026, 4, 27, 8, 0, 0, tzinfo=UTC)
    result = format_thumb_label(ts)
    assert "08:" not in result
    assert "8:" in result


# ---------------------------------------------------------------------------
# format_relative_started_at
# ---------------------------------------------------------------------------


def test_started_at_just_now() -> None:
    """< 5 seconds → 'Just now'."""
    result = format_relative_started_at(_ts(2), _now())
    assert result == "Just now"


def test_started_at_seconds_ago() -> None:
    """5..59 seconds → 'N sec ago'."""
    result = format_relative_started_at(_ts(30), _now())
    assert result == "30 sec ago"


def test_started_at_one_minute() -> None:
    """60..119 seconds → '1 min ago'."""
    result = format_relative_started_at(_ts(90), _now())
    assert result == "1 min ago"


def test_started_at_minutes_ago() -> None:
    """2..59 minutes → 'N min ago'."""
    result = format_relative_started_at(_ts(5 * 60), _now())
    assert result == "5 min ago"


def test_started_at_one_hour() -> None:
    """60..119 minutes → '1 hr ago'."""
    result = format_relative_started_at(_ts(90 * 60), _now())
    assert result == "1 hr ago"


def test_started_at_hours_ago() -> None:
    """2..23 hours → 'N hr ago'."""
    result = format_relative_started_at(_ts(3 * 3600), _now())
    assert result == "3 hr ago"


def test_started_at_old_fallback() -> None:
    """≥ 24 hours → 'Mon DD' style date."""
    ts = datetime(2026, 4, 20, 8, 0, 0, tzinfo=UTC)  # 7 days ago
    result = format_relative_started_at(ts, _now())
    assert result == "Apr 20"


# ---------------------------------------------------------------------------
# format_relative_finished_at
# ---------------------------------------------------------------------------


def test_finished_at_just_now() -> None:
    """< 60 seconds → 'Just now'."""
    result = format_relative_finished_at(_ts(30), _now())
    assert result == "Just now"


def test_finished_at_minutes_ago() -> None:
    """1..59 minutes → 'N min ago'."""
    result = format_relative_finished_at(_ts(10 * 60), _now())
    assert result == "10 min ago"


def test_finished_at_hours_ago() -> None:
    """1..23 hours → 'N hr ago'."""
    result = format_relative_finished_at(_ts(5 * 3600), _now())
    assert result == "5 hr ago"


def test_finished_at_yesterday() -> None:
    """24..47 hours → 'Yesterday'."""
    result = format_relative_finished_at(_ts(36 * 3600), _now())
    assert result == "Yesterday"


def test_finished_at_weekday() -> None:
    """2..6 days ago → weekday name."""
    # 2026-04-25 is a Saturday — 2 days before 2026-04-27
    ts = datetime(2026, 4, 25, 8, 0, 0, tzinfo=UTC)
    result = format_relative_finished_at(ts, _now())
    assert result == "Saturday"


def test_finished_at_old_fallback() -> None:
    """≥ 7 days → 'Mon DD' style date."""
    ts = datetime(2026, 4, 20, 8, 0, 0, tzinfo=UTC)  # 7 days ago
    result = format_relative_finished_at(ts, _now())
    assert result == "Apr 20"
