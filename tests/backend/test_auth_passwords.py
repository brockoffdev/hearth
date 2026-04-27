"""Tests for bcrypt password hashing helpers."""

from backend.app.auth.passwords import hash_password, verify_password


def test_hash_then_verify_round_trips() -> None:
    """Hashing a password and verifying the same plain text returns True."""
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    """verify_password returns False when the plain text does not match."""
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


def test_two_hashes_of_same_password_differ() -> None:
    """bcrypt produces a unique salt each call, so two hashes differ."""
    hashed_a = hash_password("same-password")
    hashed_b = hash_password("same-password")
    assert hashed_a != hashed_b
    # Both still verify correctly.
    assert verify_password("same-password", hashed_a) is True
    assert verify_password("same-password", hashed_b) is True
