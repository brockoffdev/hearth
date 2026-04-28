"""DB-backed overrides for runtime-configurable VLM pipeline settings.

Extends the Setting table pattern established by Phase 2 OAuth creds.
Any key in CONFIGURABLE_KEYS can be overridden at runtime without a code
rebuild.  When no DB row exists for a key the env-loaded default wins.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import Setting

CONFIGURABLE_KEYS: dict[str, type] = {
    "confidence_threshold": float,
    "vision_provider": str,
    "vision_model": str,
    "ollama_endpoint": str,
    "gemini_api_key": str,
    "anthropic_api_key": str,
    "few_shot_correction_window": int,
}


async def get_override(session: AsyncSession, key: str) -> str | None:
    """Read a single override value from the settings table."""
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row is not None else None


async def set_override(session: AsyncSession, key: str, value: str) -> None:
    """Upsert a single override value."""
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def delete_override(session: AsyncSession, key: str) -> None:
    """Remove an override (causes the env default to win again)."""
    await session.execute(delete(Setting).where(Setting.key == key))
    await session.commit()


async def get_effective_settings(session: AsyncSession) -> dict[str, Any]:
    """Return effective values for all configurable keys.

    For each key: DB Setting if present, else env value from get_settings().
    Booleans/floats/ints are coerced from string DB values.
    """
    env = get_settings()
    env_defaults: dict[str, Any] = {
        "confidence_threshold": env.confidence_threshold,
        "vision_provider": env.vision_provider,
        "vision_model": env.vision_model,
        "ollama_endpoint": env.ollama_endpoint,
        "gemini_api_key": env.gemini_api_key,
        "anthropic_api_key": env.anthropic_api_key,
        "few_shot_correction_window": env.few_shot_correction_window,
    }

    result: dict[str, Any] = {}
    for key, coerce in CONFIGURABLE_KEYS.items():
        db_value = await get_override(session, key)
        if db_value is not None:
            result[key] = coerce(db_value)
        else:
            result[key] = env_defaults[key]

    return result
