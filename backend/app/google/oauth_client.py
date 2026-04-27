"""OAuth 2.0 client helpers wrapping google_auth_oauthlib.flow.Flow.

These helpers are deliberately thin wrappers so callers only deal with
plain Python dicts and strings — the underlying Google libraries are kept
behind this module boundary.

mypy: the Google auth libraries have partial typing; per-module overrides in
pyproject.toml suppress missing-import / untyped-call errors for those packages.
"""

from __future__ import annotations

from typing import Any

from google_auth_oauthlib.flow import Flow

CALENDAR_SCOPES: list[str] = ["https://www.googleapis.com/auth/calendar"]

_GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_flow(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    state: str | None = None,
) -> Flow:
    """Construct a google_auth_oauthlib Flow from in-memory config.

    Uses ``Flow.from_client_config`` to avoid writing a ``client_secret.json``
    file to disk.  The ``state`` parameter, when provided, is passed directly
    to the underlying OAuth library so it is round-tripped by Google's redirect.
    """
    client_config: dict[str, Any] = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": _GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
            "redirect_uris": [redirect_uri],
        }
    }
    kwargs: dict[str, Any] = {
        "client_config": client_config,
        "scopes": CALENDAR_SCOPES,
        "redirect_uri": redirect_uri,
    }
    if state is not None:
        kwargs["state"] = state
    return Flow.from_client_config(**kwargs)


def get_authorization_url(flow: Flow, state: str) -> str:
    """Return the Google OAuth 2.0 consent-page URL.

    The ``state`` value is embedded in the URL so Google echoes it back in
    the redirect, allowing us to verify it against the stored CSRF token.
    """
    url: str
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",  # Force refresh token on every authorization
    )
    return url


def fetch_token(flow: Flow, code: str) -> dict[str, Any]:
    """Exchange the authorization code for access + refresh tokens.

    Returns a plain dict with keys:
      - ``access_token``  (str)
      - ``refresh_token`` (str | None — present on first authorization)
      - ``expires_at``    (float — Unix timestamp, or None)
      - ``scopes``        (list[str])
    """
    flow.fetch_token(code=code)
    credentials = flow.credentials

    expires_at: float | None = None
    if credentials.expiry is not None:
        expires_at = credentials.expiry.timestamp()

    scopes_raw = credentials.scopes
    scopes: list[str] = list(scopes_raw) if scopes_raw else CALENDAR_SCOPES

    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": expires_at,
        "scopes": scopes,
    }
