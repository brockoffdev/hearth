"""bcrypt password hashing helpers.

Uses the bcrypt library directly (bcrypt 5.x) with work factor 12.
passlib 1.7 is included as a dependency but is not used for hashing because
it does not yet support bcrypt 5.x's API changes; direct bcrypt usage is
simpler and equally correct here.
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
