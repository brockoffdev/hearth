"""Add events and event_corrections tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27 00:00:06.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create events table first — event_corrections references it.
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=True),
        sa.Column("family_member_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_dt", sa.TIMESTAMP(), nullable=False),
        sa.Column("end_dt", sa.TIMESTAMP(), nullable=True),
        sa.Column("all_day", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("google_event_id", sa.Text(), nullable=True),
        sa.Column("cell_crop_path", sa.Text(), nullable=True),
        sa.Column("raw_vlm_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("published_at", sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending_review','auto_published','published','rejected','superseded')",
            name="events_status_check",
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["uploads.id"]),
        sa.ForeignKeyConstraint(["family_member_id"], ["family_members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_upload_id", "events", ["upload_id"])
    op.create_index("ix_events_family_member_id", "events", ["family_member_id"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_start_dt", "events", ["start_dt"])

    # Create event_corrections table (references events).
    op.create_table(
        "event_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("cell_crop_path", sa.Text(), nullable=True),
        sa.Column("corrected_by", sa.Integer(), nullable=False),
        sa.Column(
            "corrected_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["corrected_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_corrections_corrected_at",
        "event_corrections",
        ["corrected_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_corrections_corrected_at", table_name="event_corrections")
    op.drop_table("event_corrections")

    op.drop_index("ix_events_start_dt", table_name="events")
    op.drop_index("ix_events_status", table_name="events")
    op.drop_index("ix_events_family_member_id", table_name="events")
    op.drop_index("ix_events_upload_id", table_name="events")
    op.drop_table("events")
