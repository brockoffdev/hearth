"""Setup wizard API endpoints — Phase 2 Task F.

Routes:
  POST /api/setup/complete-google  — mark admin's must_complete_google_setup as False
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.auth import UserResponse, to_user_response
from backend.app.auth.dependencies import require_admin
from backend.app.db.base import get_db
from backend.app.db.models import FamilyMember, OauthToken, User
from backend.app.google.health_state import clear_oauth_broken

router = APIRouter()


@router.post("/complete-google", response_model=UserResponse)
async def complete_google_setup(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserResponse:
    """Clear must_complete_google_setup for the current admin.

    Validates:
    - All family members have a non-null google_calendar_id.
    - An OauthToken row exists with a non-empty refresh_token.
    """
    # Validate: all family members mapped.
    members_result = await db.execute(select(FamilyMember))
    members = list(members_result.scalars().all())
    unmapped = [m for m in members if not m.google_calendar_id]
    if unmapped:
        raise HTTPException(
            status_code=400,
            detail=(
                "All family members must have a Google calendar mapped "
                "before completing setup"
            ),
        )

    # Validate: OAuth tokens present.
    token_result = await db.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = token_result.scalar_one_or_none()
    if token_row is None or not token_row.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth not yet connected",
        )

    # Clear the flag and persist.
    current_admin.must_complete_google_setup = False
    db.add(current_admin)
    await db.commit()
    await db.refresh(current_admin)

    # A completed setup means credentials are good; remove any stale broken flag.
    await clear_oauth_broken(db)

    return to_user_response(current_admin)
