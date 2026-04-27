"""Admin API endpoints — Phase 2 Task F.

Routes:
  GET  /api/admin/family            — list family members with calendar mappings
  PATCH /api/admin/family/{id}      — update a single family member's calendar mapping
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_admin
from backend.app.db.base import get_db
from backend.app.db.models import FamilyMember

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
