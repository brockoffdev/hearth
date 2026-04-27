"""Sanity tests for SQLAlchemy models.

Each test uses the db_session fixture from conftest.py, which provides an
isolated per-test database built from Base.metadata.create_all.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import FamilyMember, OauthToken, Setting, User


async def test_can_create_user_with_required_fields(db_session: AsyncSession) -> None:
    """Inserting a valid user row round-trips correctly."""
    user = User(
        username="testuser",
        password_hash="$2b$12$notarealhashjustfortesting",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    result = await db_session.execute(select(User).where(User.username == "testuser"))
    fetched = result.scalar_one()
    assert fetched.username == "testuser"
    assert fetched.role == "admin"
    assert fetched.must_change_password is False
    assert fetched.must_complete_google_setup is False
    assert fetched.created_at is not None


async def test_user_role_check_constraint(db_session: AsyncSession) -> None:
    """Inserting a user with an invalid role raises IntegrityError."""
    user = User(
        username="badroluser",
        password_hash="hash",
        role="garbage",
    )
    db_session.add(user)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_oauth_tokens_single_row_constraint(db_session: AsyncSession) -> None:
    """Inserting an oauth_tokens row with id != 1 raises IntegrityError."""
    token = OauthToken(
        id=2,
        refresh_token="some-refresh-token",
        scopes="https://www.googleapis.com/auth/calendar",
    )
    db_session.add(token)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_family_member_unique_name(db_session: AsyncSession) -> None:
    """Two FamilyMember rows with the same name raise IntegrityError."""
    m1 = FamilyMember(
        name="Alice",
        color_hex_center="#AABBCC",
        hue_range_low=200,
        hue_range_high=220,
    )
    m2 = FamilyMember(
        name="Alice",
        color_hex_center="#DDEEFF",
        hue_range_low=200,
        hue_range_high=220,
    )
    db_session.add(m1)
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_settings_kv(db_session: AsyncSession) -> None:
    """A Setting row can be written and read back."""
    setting = Setting(key="timezone", value="America/New_York")
    db_session.add(setting)
    await db_session.commit()

    result = await db_session.execute(select(Setting).where(Setting.key == "timezone"))
    fetched = result.scalar_one()
    assert fetched.value == "America/New_York"
