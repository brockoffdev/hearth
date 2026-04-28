"""Public family endpoint — returns family members for any authenticated user.

Routes:
  GET /api/family  — list all family members sorted by sort_order
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.admin import FamilyMemberResponse
from backend.app.auth.dependencies import require_user
from backend.app.db.base import get_db
from backend.app.db.models import FamilyMember, User

router = APIRouter()


@router.get("", response_model=list[FamilyMemberResponse])
async def list_family(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_user),
) -> list[FamilyMemberResponse]:
    """Return all family members sorted by sort_order for any authenticated user."""
    result = await db.execute(
        select(FamilyMember).order_by(FamilyMember.sort_order)
    )
    members = list(result.scalars().all())
    return [FamilyMemberResponse.model_validate(m) for m in members]
