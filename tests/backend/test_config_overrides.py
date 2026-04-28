"""Tests for backend/app/config_overrides.py."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config_overrides import (
    delete_override,
    get_effective_settings,
    get_override,
    set_override,
)


async def test_get_override_returns_none_when_missing(db_session: AsyncSession) -> None:
    result = await get_override(db_session, "confidence_threshold")
    assert result is None


async def test_set_override_inserts_then_updates(db_session: AsyncSession) -> None:
    await set_override(db_session, "confidence_threshold", "0.75")
    first = await get_override(db_session, "confidence_threshold")
    assert first == "0.75"

    await set_override(db_session, "confidence_threshold", "0.80")
    second = await get_override(db_session, "confidence_threshold")
    assert second == "0.80"


async def test_delete_override_removes_row(db_session: AsyncSession) -> None:
    await set_override(db_session, "vision_provider", "gemini")
    assert await get_override(db_session, "vision_provider") == "gemini"

    await delete_override(db_session, "vision_provider")
    assert await get_override(db_session, "vision_provider") is None


async def test_get_effective_settings_falls_back_to_env(db_session: AsyncSession) -> None:
    result = await get_effective_settings(db_session)

    from backend.app.config import get_settings
    env = get_settings()

    assert result["confidence_threshold"] == env.confidence_threshold
    assert result["vision_provider"] == env.vision_provider
    assert result["vision_model"] == env.vision_model
    assert result["ollama_endpoint"] == env.ollama_endpoint
    assert result["gemini_api_key"] == env.gemini_api_key
    assert result["anthropic_api_key"] == env.anthropic_api_key
    assert result["few_shot_correction_window"] == env.few_shot_correction_window


async def test_get_effective_settings_uses_db_override_when_present(
    db_session: AsyncSession,
) -> None:
    await set_override(db_session, "confidence_threshold", "0.70")
    await set_override(db_session, "vision_provider", "gemini")

    result = await get_effective_settings(db_session)
    assert result["confidence_threshold"] == 0.70
    assert result["vision_provider"] == "gemini"


async def test_get_effective_settings_coerces_types_correctly(
    db_session: AsyncSession,
) -> None:
    await set_override(db_session, "confidence_threshold", "0.90")
    await set_override(db_session, "few_shot_correction_window", "5")
    await set_override(db_session, "vision_provider", "anthropic")

    result = await get_effective_settings(db_session)

    assert isinstance(result["confidence_threshold"], float)
    assert result["confidence_threshold"] == 0.90

    assert isinstance(result["few_shot_correction_window"], int)
    assert result["few_shot_correction_window"] == 5

    assert isinstance(result["vision_provider"], str)
    assert result["vision_provider"] == "anthropic"
