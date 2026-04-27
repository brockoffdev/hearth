"""Tests for signed-cookie session helpers."""

import time

import pytest

from backend.app.auth.sessions import (
    SessionData,
    clear_session_cookie,
    create_session_cookie,
    read_session_cookie,
)
from backend.app.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance with known values for session tests."""
    return Settings(
        session_secret="test-secret-do-not-use-in-prod",
        session_cookie_name="hearth_session",
        session_cookie_secure=False,
        session_cookie_max_age_seconds=3600,
    )


def test_create_then_read_round_trips(test_settings: Settings) -> None:
    """Creating a cookie and reading it back returns the original user_id."""
    cookie_value, _kwargs = create_session_cookie(42, test_settings)
    session = read_session_cookie(cookie_value, test_settings)
    assert session is not None
    assert isinstance(session, SessionData)
    assert session.user_id == 42


def test_read_returns_none_for_bad_signature(test_settings: Settings) -> None:
    """A tampered cookie value returns None."""
    cookie_value, _kwargs = create_session_cookie(1, test_settings)
    # Corrupt the signature by appending garbage.
    corrupted = cookie_value + "CORRUPTED"
    assert read_session_cookie(corrupted, test_settings) is None


def test_read_returns_none_for_expired_cookie(test_settings: Settings) -> None:
    """A cookie signed with a very small max_age in the past returns None."""
    cookie_value, _kwargs = create_session_cookie(1, test_settings)
    # Wait 0 seconds but use a settings copy with max_age_seconds=0 to force expiry.
    expired_settings = Settings(
        session_secret=test_settings.session_secret,
        session_cookie_name=test_settings.session_cookie_name,
        session_cookie_secure=test_settings.session_cookie_secure,
        session_cookie_max_age_seconds=0,
    )
    # Sleep 1 second so the cookie is definitely older than max_age=0.
    time.sleep(1)
    assert read_session_cookie(cookie_value, expired_settings) is None


def test_read_returns_none_for_none_input(test_settings: Settings) -> None:
    """None input returns None without raising."""
    assert read_session_cookie(None, test_settings) is None


def test_create_cookie_kwargs_are_correct(test_settings: Settings) -> None:
    """create_session_cookie returns the expected set_cookie kwargs."""
    _value, kwargs = create_session_cookie(1, test_settings)
    assert kwargs["httponly"] is True
    assert kwargs["samesite"] == "lax"
    assert kwargs["path"] == "/"
    assert "max_age" in kwargs


def test_clear_returns_delete_kwargs() -> None:
    """clear_session_cookie returns kwargs suitable for delete_cookie."""
    kwargs = clear_session_cookie()
    # Must include path so delete_cookie matches the original cookie path.
    assert "path" in kwargs
    assert kwargs["path"] == "/"
