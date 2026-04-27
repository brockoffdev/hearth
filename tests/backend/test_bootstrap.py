"""Tests for the bootstrap admin user creation."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import verify_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import User


async def _run_bootstrap(db_engine: AsyncEngine) -> None:
    """Helper: call ensure_bootstrap_admin with the test engine's factory."""
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)


async def test_bootstrap_creates_admin_on_empty_db(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    """ensure_bootstrap_admin inserts one admin row when users is empty."""
    await _run_bootstrap(db_engine)

    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1
    admin = users[0]
    assert admin.username == "admin"
    assert admin.role == "admin"
    assert admin.must_change_password is True
    assert admin.must_complete_google_setup is True


async def test_bootstrap_is_no_op_when_users_exist(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    """ensure_bootstrap_admin does not add a second row when a user already exists."""
    # Pre-insert a user.
    existing = User(
        username="existing",
        password_hash="$2b$12$fakehash",
        role="user",
        must_change_password=False,
        must_complete_google_setup=False,
    )
    db_session.add(existing)
    await db_session.commit()

    await _run_bootstrap(db_engine)

    result = await db_session.execute(select(User))
    users = result.scalars().all()
    assert len(users) == 1
    assert users[0].username == "existing"


async def test_bootstrap_uses_bcrypt_hash(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    """The bootstrap admin's password hash is a valid bcrypt hash for 'admin'."""
    await _run_bootstrap(db_engine)

    result = await db_session.execute(select(User).where(User.username == "admin"))
    admin = result.scalar_one()
    assert admin.password_hash.startswith("$2b$")
    assert verify_password("admin", admin.password_hash) is True
