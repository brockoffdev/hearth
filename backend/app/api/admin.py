"""Admin API endpoints — Phase 2 Task F / Phase 5 Task C.

Routes:
  GET  /api/admin/family            — list family members with calendar mappings
  PATCH /api/admin/family/{id}      — update a single family member's calendar mapping
  GET  /api/admin/vision/health     — one-shot VisionProvider liveness probe
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_admin
from backend.app.config_overrides import get_effective_settings
from backend.app.db.base import get_db
from backend.app.db.models import FamilyMember
from backend.app.vision import get_effective_vision_provider

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class FamilyMemberResponse(BaseModel):
    id: int
    name: str
    color_hex_center: str
    google_calendar_id: str | None

    model_config = {"from_attributes": True}


class PatchFamilyMemberRequest(BaseModel):
    google_calendar_id: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/family", response_model=list[FamilyMemberResponse])
async def list_family_members(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> list[FamilyMemberResponse]:
    """Return all family members sorted by sort_order."""
    result = await db.execute(
        select(FamilyMember).order_by(FamilyMember.sort_order)
    )
    members = list(result.scalars().all())
    return [FamilyMemberResponse.model_validate(m) for m in members]


@router.patch("/family/{member_id}", response_model=FamilyMemberResponse)
async def patch_family_member(
    member_id: int,
    body: PatchFamilyMemberRequest,
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> FamilyMemberResponse:
    """Update the google_calendar_id for a single family member."""
    result = await db.execute(
        select(FamilyMember).where(FamilyMember.id == member_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Family member not found")

    member.google_calendar_id = body.google_calendar_id
    await db.commit()
    await db.refresh(member)
    return FamilyMemberResponse.model_validate(member)


# ---------------------------------------------------------------------------
# Vision health
# ---------------------------------------------------------------------------


class VisionHealthResponse(BaseModel):
    provider: str
    model: str
    name: str
    healthy: bool
    error: str | None


@router.get("/vision/health", response_model=VisionHealthResponse)
async def vision_health(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> VisionHealthResponse:
    """Probe the configured VisionProvider and report liveness.

    Returns 200 in all cases (including failures) so the caller can inspect
    the ``healthy`` flag and ``error`` field without catching HTTP errors.

    Resolves provider/model from DB overrides (admin /admin/settings) so the
    probe reflects the *currently effective* configuration, not the env defaults.
    """
    effective = await get_effective_settings(db)
    provider_key = effective["vision_provider"]
    model = effective["vision_model"]

    try:
        provider = await get_effective_vision_provider(db)
    except (ValueError, NotImplementedError) as exc:
        return VisionHealthResponse(
            provider=provider_key,
            model=model,
            name=provider_key,
            healthy=False,
            error=str(exc),
        )

    try:
        healthy = await provider.health_check()
        error = None if healthy else "provider unreachable"
    except Exception as exc:
        # health_check should never raise per the Protocol contract, but
        # honor the docstring's "Returns 200 in all cases" promise even
        # when a provider misbehaves.
        healthy = False
        error = f"health check raised: {exc}"

    return VisionHealthResponse(
        provider=provider_key,
        model=model,
        name=provider.name,
        healthy=healthy,
        error=error,
    )
