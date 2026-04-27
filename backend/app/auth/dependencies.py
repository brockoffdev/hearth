"""FastAPI dependencies for authentication and authorisation.

These are wiring-only helpers; endpoint tests cover them end-to-end.
No redirects: the API returns 401/403 and the frontend decides routing.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.sessions import read_session_cookie
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import User


async def get_current_user_or_none(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """Read the session cookie and return the corresponding User row, or None."""
    cookie_value = request.cookies.get(settings.session_cookie_name)
    session_data = read_session_cookie(cookie_value, settings)
    if session_data is None:
        return None
    result = await db.execute(select(User).where(User.id == session_data.user_id))
    return result.scalar_one_or_none()


async def require_user(
    current_user: User | None = Depends(get_current_user_or_none),
) -> User:
    """Raise 401 if the request is unauthenticated; otherwise return the User."""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user


async def require_admin(
    current_user: User = Depends(require_user),
) -> User:
    """Raise 403 if the authenticated user is not an admin; otherwise return the User."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
