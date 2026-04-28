"""Tests for /api/admin/users endpoints — Phase 8 Task B."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password, verify_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import User
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_engine: AsyncEngine) -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _login_regular(ac: AsyncClient, db_engine: AsyncEngine) -> None:
    """Create (idempotent) and log in as a non-admin user."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        existing = await session.execute(
            select(User).where(User.username == "regular")
        )
        if existing.scalar_one_or_none() is None:
            user = User(
                username="regular",
                password_hash=hash_password("password123"),
                role="user",
                must_change_password=False,
                must_complete_google_setup=False,
            )
            session.add(user)
            await session.commit()

    resp = await ac.post(
        "/api/auth/login",
        json={"username": "regular", "password": "password123"},
    )
    assert resp.status_code == 200


async def _create_extra_user(
    db_engine: AsyncEngine,
    username: str = "extrauser",
    role: str = "user",
    password: str = "password123",
) -> int:
    """Insert a user directly and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------


async def test_list_users_returns_admin_only(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/users")

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) == 1
    assert body["items"][0]["username"] == "admin"


async def test_list_users_sorted_by_created_at_asc(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    await _create_extra_user(db_engine, username="alpha")
    await _create_extra_user(db_engine, username="beta")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/users")

    items = resp.json()["items"]
    created_ats = [i["created_at"] for i in items]
    assert created_ats == sorted(created_ats)


async def test_list_users_does_not_include_password_hash(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/users")

    for item in resp.json()["items"]:
        assert "password_hash" not in item


async def test_list_users_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get("/api/admin/users")

    assert resp.status_code == 403


async def test_list_users_401_when_unauthenticated(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        resp = await ac.get("/api/admin/users")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/admin/users
# ---------------------------------------------------------------------------


async def test_create_user_creates_row_with_hashed_password(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "newuser", "password": "securepass"},
        )

    assert resp.status_code == 201
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one()
        assert verify_password("securepass", user.password_hash)
        assert user.password_hash != "securepass"


async def test_create_user_default_role_is_user(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "defaultrole", "password": "securepass"},
        )

    assert resp.status_code == 201
    assert resp.json()["role"] == "user"


async def test_create_user_can_create_another_admin(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "admin2", "password": "securepass", "role": "admin"},
        )

    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


async def test_create_user_409_on_duplicate_username(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        await ac.post(
            "/api/admin/users",
            json={"username": "dupuser", "password": "securepass"},
        )
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "dupuser", "password": "anotherpass"},
        )

    assert resp.status_code == 409


async def test_create_user_422_on_short_password(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "someuser", "password": "short"},
        )

    assert resp.status_code == 422


async def test_create_user_422_on_invalid_username_chars(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "bad user!", "password": "securepass"},
        )

    assert resp.status_code == 422


async def test_create_user_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.post(
            "/api/admin/users",
            json={"username": "sneakycreate", "password": "securepass"},
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/:user_id
# ---------------------------------------------------------------------------


async def test_patch_user_changes_role(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    uid = await _create_extra_user(db_engine, username="roletarget", role="user")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/admin/users/{uid}",
            json={"role": "admin"},
        )

    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


async def test_patch_user_resets_password(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    uid = await _create_extra_user(
        db_engine, username="pwreset", role="user", password="oldpassword"
    )

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/admin/users/{uid}",
            json={"new_password": "newpassword123"},
        )
        assert resp.status_code == 200

        await ac.post("/api/auth/logout")

        old_login = await ac.post(
            "/api/auth/login",
            json={"username": "pwreset", "password": "oldpassword"},
        )
        assert old_login.status_code == 401

        new_login = await ac.post(
            "/api/auth/login",
            json={"username": "pwreset", "password": "newpassword123"},
        )
        assert new_login.status_code == 200


async def test_patch_user_can_change_own_password(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin_id = result.scalar_one().id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/admin/users/{admin_id}",
            json={"new_password": "newadminpass"},
        )

    assert resp.status_code == 200


async def test_patch_user_400_when_demoting_self(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin_id = result.scalar_one().id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/admin/users/{admin_id}",
            json={"role": "user"},
        )

    assert resp.status_code == 400
    assert "demote" in resp.json()["detail"].lower()


async def test_patch_user_404_when_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch("/api/admin/users/99999", json={"role": "admin"})

    assert resp.status_code == 404


async def test_patch_user_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    uid = await _create_extra_user(db_engine, username="patchvictim")

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.patch(
            f"/api/admin/users/{uid}",
            json={"role": "admin"},
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/admin/users/:user_id
# ---------------------------------------------------------------------------


async def test_delete_user_hard_deletes(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    uid = await _create_extra_user(db_engine, username="deleteme")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete(f"/api/admin/users/{uid}")

    assert resp.status_code == 204

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == uid))
        assert result.scalar_one_or_none() is None


async def test_delete_user_400_when_deleting_self(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    # Create a second admin so that the last-admin check does NOT fire first.
    await _create_extra_user(db_engine, username="admin2", role="admin")

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin_id = result.scalar_one().id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete(f"/api/admin/users/{admin_id}")

    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


async def test_delete_user_400_when_deleting_last_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Bootstrap admin is the only admin; trying to delete them returns 400."""
    # Create one non-admin user as required by the spec.
    await _create_extra_user(db_engine, username="onlyregular", role="user")

    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin_id = result.scalar_one().id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        # Admin tries to delete themselves — last-admin check fires before self-check.
        resp = await ac.delete(f"/api/admin/users/{admin_id}")

    assert resp.status_code == 400
    assert "last admin" in resp.json()["detail"].lower()


async def test_delete_user_404_when_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete("/api/admin/users/99999")

    assert resp.status_code == 404


async def test_delete_user_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    uid = await _create_extra_user(db_engine, username="deletevictim")

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.delete(f"/api/admin/users/{uid}")

    assert resp.status_code == 403
