"""Admin settings API — Phase 8 Task C.

Routes:
  GET   /api/admin/settings  — return effective values (API keys masked)
  PATCH /api/admin/settings  — partial update; validates ranges; upserts DB rows
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_admin
from backend.app.config import get_settings
from backend.app.config_overrides import (
    delete_override,
    get_effective_settings,
    set_override,
)
from backend.app.db.base import get_db

router = APIRouter()

_ALLOWED_PROVIDERS = {"ollama", "gemini", "anthropic"}


def _mask_api_key(raw: str) -> str:
    """Return a masked version of an API key, or empty string if unset."""
    if not raw:
        return ""
    last4 = raw[-4:]
    return f"•••• {last4}"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class AdminSettingsResponse(BaseModel):
    confidence_threshold: float
    vision_provider: Literal["ollama", "gemini", "anthropic"]
    vision_model: str
    ollama_endpoint: str
    gemini_api_key_masked: str
    anthropic_api_key_masked: str
    gemini_api_key_set: bool
    anthropic_api_key_set: bool
    few_shot_correction_window: int
    use_real_pipeline: bool
    rocm_available: bool


class PatchAdminSettingsRequest(BaseModel):
    confidence_threshold: float | None = None
    vision_provider: Literal["ollama", "gemini", "anthropic"] | None = None
    vision_model: str | None = None
    ollama_endpoint: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    few_shot_correction_window: int | None = None

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_response(
    session: AsyncSession,
) -> AdminSettingsResponse:
    effective = await get_effective_settings(session)
    env = get_settings()

    gemini_key: str = effective["gemini_api_key"]
    anthropic_key: str = effective["anthropic_api_key"]

    return AdminSettingsResponse(
        confidence_threshold=effective["confidence_threshold"],
        vision_provider=effective["vision_provider"],
        vision_model=effective["vision_model"],
        ollama_endpoint=effective["ollama_endpoint"],
        gemini_api_key_masked=_mask_api_key(gemini_key),
        anthropic_api_key_masked=_mask_api_key(anthropic_key),
        gemini_api_key_set=bool(gemini_key),
        anthropic_api_key_set=bool(anthropic_key),
        few_shot_correction_window=effective["few_shot_correction_window"],
        use_real_pipeline=env.use_real_pipeline,
        rocm_available=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AdminSettingsResponse)
async def get_admin_settings(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> AdminSettingsResponse:
    return await _build_response(db)


@router.patch("", response_model=AdminSettingsResponse)
async def patch_admin_settings(
    body: PatchAdminSettingsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> AdminSettingsResponse:
    updates = body.model_dump(exclude_unset=True)

    if "confidence_threshold" in updates:
        val = updates["confidence_threshold"]
        if not (0.50 <= val <= 0.95):
            raise HTTPException(
                status_code=422,
                detail="confidence_threshold must be between 0.50 and 0.95",
            )

    if "few_shot_correction_window" in updates:
        val = updates["few_shot_correction_window"]
        if not (0 <= val <= 50):
            raise HTTPException(
                status_code=422,
                detail="few_shot_correction_window must be between 0 and 50",
            )

    if "vision_provider" in updates and updates["vision_provider"] not in _ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"vision_provider must be one of {sorted(_ALLOWED_PROVIDERS)}",
        )

    if "vision_model" in updates and not updates["vision_model"]:
        raise HTTPException(status_code=422, detail="vision_model must not be empty")

    if "ollama_endpoint" in updates and not updates["ollama_endpoint"]:
        raise HTTPException(status_code=422, detail="ollama_endpoint must not be empty")

    for key, value in updates.items():
        if key in ("gemini_api_key", "anthropic_api_key"):
            if value == "":
                await delete_override(db, key)
            else:
                await set_override(db, key, str(value))
        else:
            await set_override(db, key, str(value))

    return await _build_response(db)
