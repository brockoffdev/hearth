"""SQLAlchemy 2.0 declarative models for Phase 2+ tables.

Tables created here: users, family_members, oauth_tokens, settings, uploads,
pipeline_stage_durations, events, event_corrections.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, text
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


class Upload(Base):
    """A photo upload row — created when a user POSTs a photo for processing."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True
    )
    status: Mapped[str] = mapped_column(nullable=False)
    provider: Mapped[str | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Phase 3.5: progress tracking columns (added by migration 0005)
    current_stage: Mapped[str | None] = mapped_column(nullable=True)
    completed_stages: Mapped[str] = mapped_column(
        nullable=False, server_default=text("'[]'")
    )
    cell_progress: Mapped[int | None] = mapped_column(nullable=True)
    total_cells: Mapped[int | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','completed','failed')",
            name="uploads_status_check",
        ),
    )


class PipelineStageDuration(Base):
    """Per-stage timing measurements for pipeline runs.

    Phase 3.5 inserts these rows during SSE streaming.  Phase 4+ uses them
    to compute real ETA medians, replacing STAGE_MEDIAN_SECONDS.
    """

    __tablename__ = "pipeline_stage_durations"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(nullable=False, index=True)
    duration_seconds: Mapped[float] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class Event(Base):
    """A calendar event parsed from an uploaded photo or created by hand."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("uploads.id"), nullable=True, index=True
    )
    family_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("family_members.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(nullable=False)
    start_dt: Mapped[datetime] = mapped_column(nullable=False, index=True)
    end_dt: Mapped[datetime | None] = mapped_column(nullable=True)
    all_day: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    location: Mapped[str | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    google_event_id: Mapped[str | None] = mapped_column(nullable=True)
    cell_crop_path: Mapped[str | None] = mapped_column(nullable=True)
    raw_vlm_json: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review','auto_published','published','rejected','superseded')",
            name="events_status_check",
        ),
    )


class EventCorrection(Base):
    """A user correction to a parsed event — stored as few-shot examples for the VLM."""

    __tablename__ = "event_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"), nullable=False, index=True
    )
    before_json: Mapped[str] = mapped_column(nullable=False)
    after_json: Mapped[str] = mapped_column(nullable=False)
    cell_crop_path: Mapped[str | None] = mapped_column(nullable=True)
    corrected_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True
    )
