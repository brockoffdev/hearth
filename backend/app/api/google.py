"""Google OAuth and Calendar API endpoints.

Routes:
  POST /api/google/oauth/credentials  — save client_id + client_secret to settings
  POST /api/google/oauth/init         — generate and return the Google consent URL
  GET  /api/google/oauth/callback     — Google redirects here after consent
  GET  /api/google/oauth/state        — query the current OAuth connection status
  GET  /api/google/calendars          — list calendars from the connected Google account
  POST /api/google/calendars          — create a new Google calendar
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import require_admin, require_user
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import FamilyMember, OauthToken, Setting, User
from backend.app.google.calendar_client import (
    create_calendar,
    credentials_for,
    expiry_to_datetime,
    list_calendars,
)
from backend.app.google.health_state import clear_oauth_broken, get_oauth_health
from backend.app.google.oauth_client import build_flow, fetch_token, get_authorization_url

logger = logging.getLogger(__name__)

router = APIRouter()

# Settings keys used in the `settings` table.
_KEY_CLIENT_ID = "google_oauth_client_id"
_KEY_CLIENT_SECRET = "google_oauth_client_secret"
_KEY_PENDING_STATE = "google_oauth_pending_state"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class OauthCredentialsRequest(BaseModel):
    client_id: str
    client_secret: str


class OauthInitResponse(BaseModel):
    authorization_url: str


class OauthStateResponse(BaseModel):
    connected: bool
    calendars_mapped: bool
    refresh_token_present: bool
    scopes: list[str] | None


class GoogleCalendarResponse(BaseModel):
    id: str
    summary: str
    primary: bool | None = None
    access_role: str | None = None


class CreateCalendarRequest(BaseModel):
    summary: str

    model_config = {"str_min_length": 1}


class GoogleHealthResponse(BaseModel):
    connected: bool
    broken_reason: str | None = None
    broken_at: str | None = None


# ---------------------------------------------------------------------------
# Helper: upsert a single settings key/value
# ---------------------------------------------------------------------------


async def _upsert_setting(db: AsyncSession, key: str, value: str) -> None:
    """Insert or update a row in the `settings` table."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    # No explicit commit — callers commit after all mutations.


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    """Return the value for a settings key, or None if not set."""
    result = await db.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row is not None else None


async def get_active_credentials(db: AsyncSession) -> Credentials:
    """Load tokens from the DB, refresh if needed, persist the refreshed access token.

    Returns ready-to-use ``google.oauth2.credentials.Credentials``.
    Raises ``HTTPException(400)`` if no OAuth connection has been completed yet.
    """
    token_result = await db.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = token_result.scalar_one_or_none()
    if token_row is None or not token_row.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth not connected — complete the setup wizard first",
        )

    client_id = await _get_setting(db, _KEY_CLIENT_ID)
    client_secret = await _get_setting(db, _KEY_CLIENT_SECRET)
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail=(
                "OAuth credentials not configured — "
                "call /api/google/oauth/credentials first"
            ),
        )

    creds, was_refreshed = await credentials_for(token_row, client_id, client_secret)

    if was_refreshed:
        token_row.access_token = creds.token
        token_row.expires_at = expiry_to_datetime(creds)
        await db.commit()

    return creds


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/oauth/credentials")
async def save_oauth_credentials(
    body: OauthCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> dict[str, bool]:
    """Persist Google OAuth client_id + client_secret to the settings table.

    Only admins may call this.  Values are stored as plaintext in the local
    SQLite database — this is acceptable for a home-server product where the
    database file is on a trusted host.
    """
    await _upsert_setting(db, _KEY_CLIENT_ID, body.client_id)
    await _upsert_setting(db, _KEY_CLIENT_SECRET, body.client_secret)
    await db.commit()
    return {"ok": True}


@router.post("/oauth/init", response_model=OauthInitResponse)
async def oauth_init(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: object = Depends(require_admin),
) -> OauthInitResponse:
    """Generate a Google OAuth 2.0 consent URL and store the CSRF state token.

    Reads client_id + client_secret from the settings table (saved by
    ``save_oauth_credentials``).  Returns the ``authorization_url`` — the
    frontend should navigate the browser to this URL.
    """
    client_id = await _get_setting(db, _KEY_CLIENT_ID)
    client_secret = await _get_setting(db, _KEY_CLIENT_SECRET)
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail=(
                "OAuth credentials not configured — "
                "call /api/google/oauth/credentials first"
            ),
        )

    state = secrets.token_urlsafe(32)
    await _upsert_setting(db, _KEY_PENDING_STATE, state)
    await db.commit()

    redirect_uri = f"{settings.public_base_url}/api/google/oauth/callback"
    flow = build_flow(client_id, client_secret, redirect_uri, state=state)
    authorization_url = get_authorization_url(flow, state)
    return OauthInitResponse(authorization_url=authorization_url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Google redirects the browser here after the user grants (or denies) consent.

    This endpoint is intentionally public — it is reached via a browser
    redirect from Google.  The ``state`` parameter doubles as a CSRF token:
    it was generated by ``/oauth/init`` and stored in the settings table.
    We compare the inbound ``state`` against the stored value before proceeding.

    On success:   redirect to /setup/google?status=ok
    On any error: redirect to /setup/google?status=error&detail=<message>
    """
    frontend_base = "/setup/google"

    # Google may send error= if the user denied consent.
    if error:
        params = urlencode({"status": "error", "detail": error})
        return RedirectResponse(url=f"{frontend_base}?{params}", status_code=302)

    if not code or not state:
        params = urlencode({"status": "error", "detail": "Missing code or state parameter"})
        return RedirectResponse(url=f"{frontend_base}?{params}", status_code=302)

    # CSRF state check.
    expected_state = await _get_setting(db, _KEY_PENDING_STATE)
    if expected_state is None or state != expected_state:
        params = urlencode({"status": "error", "detail": "OAuth state mismatch"})
        return RedirectResponse(url=f"{frontend_base}?{params}", status_code=302)

    # Retrieve stored credentials.
    client_id = await _get_setting(db, _KEY_CLIENT_ID)
    client_secret = await _get_setting(db, _KEY_CLIENT_SECRET)
    if not client_id or not client_secret:
        params = urlencode({"status": "error", "detail": "OAuth credentials not configured"})
        return RedirectResponse(url=f"{frontend_base}?{params}", status_code=302)

    # Exchange authorization code for tokens.
    redirect_uri = f"{settings.public_base_url}/api/google/oauth/callback"
    try:
        flow = build_flow(client_id, client_secret, redirect_uri, state=state)
        token_data = fetch_token(flow, code)
    except Exception as exc:
        logger.exception("Google token exchange failed: %s", exc)
        params = urlencode({"status": "error", "detail": str(exc)})
        return RedirectResponse(url=f"{frontend_base}?{params}", status_code=302)

    # Persist tokens to the oauth_tokens table (single row, id=1).
    expires_at: datetime | None = None
    if token_data.get("expires_at") is not None:
        expires_at = datetime.fromtimestamp(
            float(token_data["expires_at"]), tz=UTC
        ).replace(tzinfo=None)

    scopes_value: str = " ".join(token_data.get("scopes") or [])
    refresh_token: str = token_data.get("refresh_token") or ""
    access_token: str | None = token_data.get("access_token")

    result = await db.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = result.scalar_one_or_none()
    if token_row is None:
        token_row = OauthToken(
            id=1,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=expires_at,
            scopes=scopes_value,
        )
        db.add(token_row)
    else:
        token_row.refresh_token = refresh_token
        token_row.access_token = access_token
        token_row.expires_at = expires_at
        token_row.scopes = scopes_value

    # Clear the pending state so the token cannot be replayed.
    await _upsert_setting(db, _KEY_PENDING_STATE, "")
    await db.commit()

    # Successful re-auth clears any prior broken-token flag.
    await clear_oauth_broken(db)

    return RedirectResponse(url=f"{frontend_base}?status=ok", status_code=302)


@router.get("/oauth/state", response_model=OauthStateResponse)
async def oauth_state(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> OauthStateResponse:
    """Return the current OAuth connection status for the UI.

    ``connected``        — True iff a refresh token is stored in oauth_tokens.
    ``calendars_mapped`` — True iff every family_members row has a non-null
                           google_calendar_id.  (Task F populates this field.)
    ``refresh_token_present`` — Same as ``connected``; exposed separately
                           for clarity in the frontend.
    ``scopes``           — The scopes granted by the stored token, or None.
    """
    token_result = await db.execute(select(OauthToken).where(OauthToken.id == 1))
    token_row = token_result.scalar_one_or_none()

    connected = token_row is not None and bool(token_row.refresh_token)
    scopes: list[str] | None = None
    if token_row is not None and token_row.scopes:
        scopes = token_row.scopes.split()

    # Check whether all family members have a calendar mapped.
    members_result = await db.execute(select(FamilyMember))
    members = list(members_result.scalars().all())
    calendars_mapped = all(m.google_calendar_id is not None for m in members)

    return OauthStateResponse(
        connected=connected,
        calendars_mapped=calendars_mapped,
        refresh_token_present=connected,
        scopes=scopes,
    )


@router.get("/calendars", response_model=list[GoogleCalendarResponse])
async def list_google_calendars(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> list[GoogleCalendarResponse]:
    """List all calendars accessible by the connected Google account."""
    creds = await get_active_credentials(db)
    calendars = await list_calendars(creds)
    return [
        GoogleCalendarResponse(
            id=c["id"],
            summary=c["summary"],
            primary=c.get("primary"),
            access_role=c.get("accessRole"),
        )
        for c in calendars
    ]


@router.post("/calendars", response_model=GoogleCalendarResponse)
async def create_google_calendar(
    body: CreateCalendarRequest,
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_admin),
) -> GoogleCalendarResponse:
    """Create a new Google Calendar on the connected account."""
    creds = await get_active_credentials(db)
    result = await create_calendar(creds, body.summary)
    return GoogleCalendarResponse(
        id=result["id"],
        summary=result["summary"],
    )


@router.get("/health", response_model=GoogleHealthResponse)
async def google_health(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_user),
) -> GoogleHealthResponse:
    """Return the current Google OAuth health state.

    Authenticated but not admin-gated — all users need to know when
    auto-publish is broken.
    """
    health = await get_oauth_health(db)
    return GoogleHealthResponse(
        connected=bool(health["connected"]),
        broken_reason=health["broken_reason"] if isinstance(health["broken_reason"], str) else None,
        broken_at=health["broken_at"] if isinstance(health["broken_at"], str) else None,
    )
