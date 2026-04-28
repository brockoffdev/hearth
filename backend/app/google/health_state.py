"""GCal OAuth health-state helpers.

Three operations: mark broken (on InvalidGrantError), clear (on re-auth),
and query (for the /api/google/health endpoint and the banner).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import OauthToken, Setting

_KEY_BROKEN_REASON = "google_oauth_broken_reason"
_KEY_BROKEN_AT = "google_oauth_broken_at"


async def _upsert(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


async def mark_oauth_broken(session: AsyncSession, reason: str) -> None:
    """Persist that the Google OAuth tokens are unrecoverably broken."""
    await _upsert(session, _KEY_BROKEN_REASON, reason)
    await _upsert(session, _KEY_BROKEN_AT, datetime.now(UTC).isoformat())
    await session.commit()


async def clear_oauth_broken(session: AsyncSession) -> None:
    """Clear the broken state — called when /setup/google completes successfully."""
    await session.execute(
        delete(Setting).where(Setting.key.in_([_KEY_BROKEN_REASON, _KEY_BROKEN_AT]))
    )
    await session.commit()


async def get_oauth_health(session: AsyncSession) -> dict[str, object]:
    """Return {connected, broken_reason, broken_at}.

    connected is True iff an oauth_tokens row exists AND no broken flag is set.
    """
    token_result = await session.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = token_result.scalar_one_or_none()
    has_token = token_row is not None and bool(token_row.refresh_token)

    reason_result = await session.execute(
        select(Setting).where(Setting.key == _KEY_BROKEN_REASON)
    )
    reason_row = reason_result.scalar_one_or_none()
    broken_reason: str | None = reason_row.value if reason_row is not None else None

    broken_at: str | None = None
    if broken_reason is not None:
        at_result = await session.execute(
            select(Setting).where(Setting.key == _KEY_BROKEN_AT)
        )
        at_row = at_result.scalar_one_or_none()
        broken_at = at_row.value if at_row is not None else None

    connected = has_token and broken_reason is None
    return {
        "connected": connected,
        "broken_reason": broken_reason,
        "broken_at": broken_at,
    }
