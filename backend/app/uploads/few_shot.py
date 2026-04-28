"""Few-shot correction retrieval for the VLM prompt pipeline.

Phase 5 Task A: fetch the N most recent user corrections from event_corrections
and return them in the form expected by CellPromptContext.few_shot_corrections.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import EventCorrection

logger = logging.getLogger(__name__)


async def fetch_recent_corrections(
    session: AsyncSession,
    *,
    limit: int = 10,
) -> tuple[dict[str, str], ...]:
    """Return the N most recent corrections in the form expected by the VLM prompt.

    Each correction is a dict with 'before' and 'after' keys (strings).

    The before/after JSON in event_corrections is the full VLM/user record;
    we extract just the title-text-or-raw-text for the few-shot prompt to keep
    it concise. If a row's JSON doesn't parse or the title isn't extractable,
    the row is skipped.

    Args:
        session: Active async SQLAlchemy session.
        limit: Maximum number of corrections to return (most recent first).

    Returns:
        Tuple of correction dicts, each with 'before' and 'after' string keys.
    """
    stmt = (
        select(EventCorrection)
        .order_by(EventCorrection.corrected_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    corrections = result.scalars().all()

    out: list[dict[str, str]] = []
    for row in corrections:
        before = _extract_title(row.before_json)
        after = _extract_title(row.after_json)
        if before is None or after is None or before == after:
            continue  # nothing useful to include
        out.append({"before": before, "after": after})

    return tuple(out)


def _extract_title(raw_json: str) -> str | None:
    """Pull the most-likely 'title' field from a correction's JSON blob.

    The raw JSON shape comes from ExtractedEvent.asdict() (Phase 4 record):
    keys include title, time_text, color_hex, owner_guess, confidence, raw_text.

    Prefer 'title' if present and non-empty; fall back to 'raw_text'.

    Args:
        raw_json: JSON string to parse.

    Returns:
        Extracted title string (stripped), or None if not extractable.
    """
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    title = parsed.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    raw = parsed.get("raw_text")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
