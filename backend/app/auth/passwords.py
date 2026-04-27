"""Password hashing helpers.

Uses the `bcrypt` library directly. Default work factor 12, per spec §7.
"""

import bcrypt

_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* (work factor 12)."""
    salt = bcrypt.gensalt(_ROUNDS)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*, False otherwise."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# Dummy hash used by the login flow's user-not-found path so the bcrypt cost
# is paid regardless of whether the username exists. Constant-time enumeration
# defense.
DUMMY_PASSWORD_HASH: str = hash_password("hearth-dummy-password-never-matched")
