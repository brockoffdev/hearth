"""SQLAlchemy 2.0 declarative models for Phase 2 tables.

Tables created here: users, family_members, oauth_tokens, settings.
Deferred to later phases: uploads, events, event_corrections.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    # Constrained to 'admin' | 'user' — see __table_args__
    role: Mapped[str] = mapped_column(nullable=False)
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    must_complete_google_setup: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin','user')", name="users_role_check"),
    )


class FamilyMember(Base):
    """A named family member with their calendar colour and hue detection range."""

    __tablename__ = "family_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    color_hex_center: Mapped[str] = mapped_column(nullable=False)
    hue_range_low: Mapped[int] = mapped_column(nullable=False)
    hue_range_high: Mapped[int] = mapped_column(nullable=False)
    # NULL until the Google OAuth setup wizard connects their calendar.
    google_calendar_id: Mapped[str | None] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)


class OauthToken(Base):
    """Google OAuth token store — enforced to be a single row (id must equal 1)."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    refresh_token: Mapped[str] = mapped_column(nullable=False)
    access_token: Mapped[str | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    scopes: Mapped[str] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("id = 1", name="oauth_tokens_single_row_check"),
    )


class Setting(Base):
    """Key/value application settings store."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)
