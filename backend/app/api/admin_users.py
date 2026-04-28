"""Admin user management API — Phase 8 Task B.

Routes:
  GET    /api/admin/users          — list all users sorted by created_at ASC
  POST   /api/admin/users          — create a new user
  PATCH  /api/admin/users/:user_id — update role or reset password
  DELETE /api/admin/users/:user_id — hard delete a user
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_db
from backend.app.db.models import User

router = APIRouter()

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,32}$")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UserResponseAdmin(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    must_change_password: bool
    must_complete_google_setup: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Literal["admin", "user"] = "user"

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-32 characters: letters, digits, underscore, or dot"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PatchUserRequest(BaseModel):
    role: Literal["admin", "user"] | None = None
    new_password: str | None = None

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=dict[str, list[UserResponseAdmin]])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> dict[str, list[UserResponseAdmin]]:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    users = list(result.scalars().all())
    return {"items": [UserResponseAdmin.model_validate(u) for u in users]}


@router.post("", response_model=UserResponseAdmin, status_code=201)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> UserResponseAdmin:
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        must_change_password=False,
        must_complete_google_setup=False,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken") from None
    await db.refresh(user)
    return UserResponseAdmin.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponseAdmin)
async def patch_user(
    user_id: int,
    body: PatchUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponseAdmin:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_unset=True)

    if "role" in updates and updates["role"] == "user" and user.id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot demote yourself; ask another admin",
        )

    if "role" in updates:
        user.role = updates["role"]

    if "new_password" in updates and updates["new_password"] is not None:
        user.password_hash = hash_password(updates["new_password"])

    await db.commit()
    await db.refresh(user)
    return UserResponseAdmin.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Response:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check last-admin before self-delete so the more specific message surfaces first
    # when the only admin tries to delete themselves.
    if user.role == "admin":
        admin_count_result = await db.execute(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        admin_count = admin_count_result.scalar_one()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    await db.delete(user)
    await db.commit()
    return Response(status_code=204)
