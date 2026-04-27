"""Signed-cookie session primitives using itsdangerous.

Session data is serialized as a JSON payload and signed with a per-deployment
secret key via URLSafeTimedSerializer.  The signature is verified on read, and
expired cookies are rejected automatically.

NOTE: no CSRF middleware is included in Phase 2.  We rely on SameSite=Lax to
prevent cross-site POSTs.  CSRF protection is a documented follow-up task.
"""

from __future__ import annotations

import functools
import logging
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.app.config import Settings

logger = logging.getLogger(__name__)

_SALT = "hearth-session"


@dataclass
class SessionData:
    """Deserialized session payload."""

    user_id: int
    issued_at: datetime


@functools.lru_cache(maxsize=1)
def _get_serializer(secret: str) -> URLSafeTimedSerializer:
    """Cache a serializer keyed by secret (one per process)."""
    return URLSafeTimedSerializer(secret, salt=_SALT)


def create_session_cookie(
    user_id: int, settings: Settings
) -> tuple[str, dict[str, Any]]:
    """Sign a session payload and return (cookie_value, set_cookie_kwargs).

    The caller should pass the kwargs to ``response.set_cookie(**kwargs)``,
    setting the cookie name separately via ``settings.session_cookie_name``.
    """
    serializer = _get_serializer(settings.session_secret)
    issued_at = datetime.now(tz=timezone.utc)
    value = serializer.dumps(
        {"user_id": user_id, "issued_at": issued_at.isoformat()}
    )
    kwargs: dict[str, Any] = {
        "max_age": settings.session_cookie_max_age_seconds,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }
    return str(value), kwargs


def read_session_cookie(
    cookie_value: str | None, settings: Settings
) -> SessionData | None:
    """Verify and deserialize a session cookie.

    Returns None if the cookie is missing, has a bad signature, or is expired.
    """
    if cookie_value is None:
        return None
    serializer = _get_serializer(settings.session_secret)
    try:
        data: dict[str, Any] = serializer.loads(
            cookie_value, max_age=settings.session_cookie_max_age_seconds
        )
    except SignatureExpired:
        logger.debug("Session cookie expired")
        return None
    except BadSignature:
        logger.debug("Session cookie bad signature")
        return None
    return SessionData(
        user_id=int(data["user_id"]),
        issued_at=datetime.fromisoformat(str(data["issued_at"])),
    )


def clear_session_cookie() -> dict[str, Any]:
    """Return kwargs suitable for ``response.delete_cookie(...)`` to clear the session."""
    return {"path": "/"}
