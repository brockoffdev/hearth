"""Tests for /api/admin/settings endpoints — Phase 8 Task C."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.config_overrides import set_override
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
    factory = get_session_factory(db_engine)
    async with factory() as session:
        from sqlalchemy import select
        existing = await session.execute(select(User).where(User.username == "regular"))
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


# ---------------------------------------------------------------------------
# GET /api/admin/settings
# ---------------------------------------------------------------------------


async def test_get_settings_returns_effective_values(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/settings")

    assert resp.status_code == 200
    body = resp.json()

    from backend.app.config import get_settings
    env = get_settings()

    assert body["confidence_threshold"] == env.confidence_threshold
    assert body["vision_provider"] == env.vision_provider
    assert body["vision_model"] == env.vision_model
    assert body["ollama_endpoint"] == env.ollama_endpoint
    assert body["few_shot_correction_window"] == env.few_shot_correction_window
    assert "gemini_api_key_masked" in body
    assert "anthropic_api_key_masked" in body
    assert "use_real_pipeline" in body
    assert "rocm_available" in body
    assert body["rocm_available"] is False


async def test_get_settings_masks_api_keys(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        await set_override(session, "anthropic_api_key", "sk-ant-testabcd")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/settings")

    assert resp.status_code == 200
    body = resp.json()

    assert "abcd" in body["anthropic_api_key_masked"]
    assert "sk-ant-testabcd" not in body["anthropic_api_key_masked"]
    assert body["anthropic_api_key_set"] is True
    assert "•••• " in body["anthropic_api_key_masked"]


async def test_get_settings_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get("/api/admin/settings")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/admin/settings
# ---------------------------------------------------------------------------


async def test_patch_settings_updates_confidence_threshold(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        patch_resp = await ac.patch(
            "/api/admin/settings",
            json={"confidence_threshold": 0.90},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["confidence_threshold"] == 0.90

        get_resp = await ac.get("/api/admin/settings")
        assert get_resp.json()["confidence_threshold"] == 0.90


async def test_patch_settings_can_set_provider_and_model(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            "/api/admin/settings",
            json={"vision_provider": "gemini", "vision_model": "gemini-2.5-flash"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["vision_provider"] == "gemini"
    assert body["vision_model"] == "gemini-2.5-flash"


async def test_patch_settings_400_on_out_of_range_confidence(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            "/api/admin/settings",
            json={"confidence_threshold": 1.5},
        )

    assert resp.status_code == 422


async def test_patch_settings_clears_api_key_on_empty_string(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        await set_override(session, "gemini_api_key", "AIza-testkey1234")

    async with bootstrapped_client as ac:
        await _login_admin(ac)

        get_resp = await ac.get("/api/admin/settings")
        assert get_resp.json()["gemini_api_key_set"] is True

        patch_resp = await ac.patch(
            "/api/admin/settings",
            json={"gemini_api_key": ""},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["gemini_api_key_set"] is False
        assert patch_resp.json()["gemini_api_key_masked"] == ""


async def test_patch_settings_invalid_provider_422(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            "/api/admin/settings",
            json={"vision_provider": "openai"},
        )

    assert resp.status_code == 422


async def test_patch_settings_persists_across_reads(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH in one request; GET in a new request — override must persist."""
    app = create_app()
    transport = ASGITransport(app=app)
    second_client = AsyncClient(transport=transport, base_url="http://test")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            "/api/admin/settings",
            json={"few_shot_correction_window": 25},
        )
        assert resp.status_code == 200

    async with second_client as ac2:
        await _login_admin(ac2)
        resp2 = await ac2.get("/api/admin/settings")
        assert resp2.json()["few_shot_correction_window"] == 25


async def test_patch_settings_403_for_non_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.patch(
            "/api/admin/settings",
            json={"confidence_threshold": 0.80},
        )

    assert resp.status_code == 403


async def test_patch_settings_no_fields_returns_200_unchanged(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        get_resp = await ac.get("/api/admin/settings")
        original = get_resp.json()

        patch_resp = await ac.patch("/api/admin/settings", json={})
        assert patch_resp.status_code == 200
        after = patch_resp.json()

    assert after["confidence_threshold"] == original["confidence_threshold"]
    assert after["vision_provider"] == original["vision_provider"]
    assert after["few_shot_correction_window"] == original["few_shot_correction_window"]
