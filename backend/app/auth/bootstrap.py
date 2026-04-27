"""First-run bootstrap: create the default admin user if no users exist.

Runs at startup (gated by HEARTH_BOOTSTRAP_ADMIN_ON_STARTUP) after migrations
complete.  Idempotent — does nothing if any user row already exists.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.auth.passwords import hash_password
from backend.app.db.models import User

logger = logging.getLogger(__name__)


async def ensure_bootstrap_admin(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Create the bootstrap admin if the users table is empty.

    Inserts a single admin row (username=admin, password=admin) with
    must_change_password=True and must_complete_google_setup=True.

    Logs a warning when it creates the user so the operator can see it in
    container logs and know to change the password immediately.
    """
    async with session_factory() as session:
        count_result = await session.execute(select(func.count()).select_from(User))
        count = count_result.scalar_one()
        if count > 0:
            logger.debug("Bootstrap: users table is non-empty, skipping.")
            return

        logger.warning(
            "Bootstrap admin created with default password — "
            "log in and change it immediately."
        )
        admin = User(
            username="admin",
            password_hash=hash_password("admin"),
            role="admin",
            must_change_password=True,
            must_complete_google_setup=True,
        )
        session.add(admin)
        await session.commit()
