"""SQLAlchemy async engine, session factory, and FastAPI dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


def get_engine() -> AsyncEngine:
    """Return an async engine for the current settings.

    Called at startup and in tests (so settings can be overridden before the
    engine is first requested).
    """
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False, future=True)


def get_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return an async sessionmaker bound to *engine* (or the default engine)."""
    _engine = engine if engine is not None else get_engine()
    return async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
