"""Friendly timestamp formatters for the Uploads API response.

Used by _to_response() in api/uploads.py to produce human-readable strings
for thumbLabel, startedAt, and finishedAt fields.
"""

from __future__ import annotations

from datetime import datetime


def format_thumb_label(ts: datetime) -> str:
    """Format as 'Apr 27, 8:38 AM' (no leading zero on day or hour).

    Example: datetime(2026, 4, 27, 8, 38) → "Apr 27, 8:38 AM"
    """
    return ts.strftime("%b %-d, %-I:%M %p")


def format_relative_started_at(start: datetime, now: datetime) -> str:
    """Friendly relative time for in-progress uploads.

    Buckets:
      < 5 seconds  → "Just now"
      5..59 sec    → "N sec ago"
      60..119 sec  → "1 min ago"
      2..59 min    → "N min ago"
      60..119 min  → "1 hr ago"
      2..23 hr     → "N hr ago"
      ≥ 24 hr      → "Apr 27" (month + day, no leading zero)
    """
    delta = (now - start).total_seconds()
    if delta < 5:
        return "Just now"
    if delta < 60:
        return f"{int(delta)} sec ago"
    if delta < 120:
        return "1 min ago"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 7200:
        return "1 hr ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hr ago"
    return start.strftime("%b %-d")


def format_relative_finished_at(end: datetime, now: datetime) -> str:
    """Friendly relative time for completed/failed uploads.

    Buckets:
      < 60 sec     → "Just now"
      1..59 min    → "N min ago"
      1..23 hr     → "N hr ago"
      24..47 hr    → "Yesterday"
      2..6 days    → weekday name (e.g. "Saturday")
      ≥ 7 days     → "Apr 27" (month + day, no leading zero)
    """
    delta = (now - end).total_seconds()
    if delta < 60:
        return "Just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hr ago"
    if delta < 172800:
        return "Yesterday"
    if delta < 604800:
        return end.strftime("%A")  # full weekday name
    return end.strftime("%b %-d")
