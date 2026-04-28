"""Tests for backend/app/google/health_state.py helper functions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import OauthToken
from backend.app.google.health_state import (
    clear_oauth_broken,
    get_oauth_health,
    mark_oauth_broken,
)


async def test_mark_and_get_broken(db_session: AsyncSession) -> None:
    """mark_oauth_broken persists reason and broken_at; get_oauth_health reads them."""
    await mark_oauth_broken(db_session, "invalid_grant: token has been expired or revoked")

    health = await get_oauth_health(db_session)

    assert health["connected"] is False
    assert "invalid_grant" in str(health["broken_reason"])
    assert health["broken_at"] is not None


async def test_clear_removes_broken_flag(db_session: AsyncSession) -> None:
    """clear_oauth_broken removes both broken settings rows."""
    await mark_oauth_broken(db_session, "some reason")

    await clear_oauth_broken(db_session)
    health = await get_oauth_health(db_session)

    assert health["broken_reason"] is None
    assert health["broken_at"] is None


async def test_get_health_disconnected_with_no_token(db_session: AsyncSession) -> None:
    """connected is False when there is no oauth_tokens row, even without a broken flag."""
    health = await get_oauth_health(db_session)

    assert health["connected"] is False
    assert health["broken_reason"] is None


async def test_get_health_connected_with_token_and_no_broken_flag(
    db_session: AsyncSession,
) -> None:
    """connected is True when an oauth_tokens row exists and no broken flag is set."""
    db_session.add(
        OauthToken(id=1, refresh_token="rt", scopes="https://www.googleapis.com/auth/calendar")
    )
    await db_session.commit()

    health = await get_oauth_health(db_session)

    assert health["connected"] is True
    assert health["broken_reason"] is None


async def test_get_health_not_connected_when_token_present_but_broken(
    db_session: AsyncSession,
) -> None:
    """connected is False even when a token row exists if the broken flag is set."""
    db_session.add(
        OauthToken(id=1, refresh_token="rt", scopes="https://www.googleapis.com/auth/calendar")
    )
    await db_session.commit()

    await mark_oauth_broken(db_session, "revoked")
    health = await get_oauth_health(db_session)

    assert health["connected"] is False
    assert health["broken_reason"] == "revoked"
