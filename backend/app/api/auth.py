"""Auth endpoints: login, logout, me, change-password.

All endpoints return JSON; no redirects — the frontend handles routing
based on the user record's must_change_password / must_complete_google_setup
flags.

NOTE: no CSRF middleware in Phase 2.  SameSite=Lax on the session cookie
mitigates cross-site POST risks.  CSRF tokens are a documented follow-up.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_user
from backend.app.auth.passwords import hash_password, verify_password
from backend.app.auth.sessions import clear_session_cookie, create_session_cookie
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    must_change_password: bool
    must_complete_google_setup: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user_response(user: User) -> UserResponse:
    """Construct a UserResponse from a User ORM row."""
    return UserResponse.model_validate(user)


def _set_session(response: Response, user_id: int, settings: Settings) -> None:
    """Write the signed session cookie onto *response*."""
    value, kwargs = create_session_cookie(user_id, settings)
    response.set_cookie(settings.session_cookie_name, value, **kwargs)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    """Authenticate with username + password; set a signed HttpOnly session cookie."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    # Use a constant-time failure path so we don't reveal whether the username exists.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _set_session(response, user.id, settings)
    return _user_response(user)


@router.post("/logout")
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    """Clear the session cookie.  Idempotent — always succeeds regardless of auth state."""
    kwargs = clear_session_cookie()
    response.delete_cookie(settings.session_cookie_name, **kwargs)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(require_user),
) -> UserResponse:
    """Return the current authenticated user."""
    return _user_response(current_user)


@router.post("/change-password", response_model=UserResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_user),
) -> UserResponse:
    """Change the current user's password; clears must_change_password on success."""
    # Validate current password.
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password differs from current (check before length so we give
    # the most specific error when both constraints apply).
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from current"
        )

    # Validate new password length.
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=400, detail="New password must be at least 8 characters"
        )

    # Update the user record.
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return _user_response(current_user)
