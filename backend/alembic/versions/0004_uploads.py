"""Add uploads table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-27 00:00:04.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','processing','completed','failed')",
            name="uploads_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploads_user_id", "uploads", ["user_id"])
    op.create_index("ix_uploads_uploaded_at", "uploads", ["uploaded_at"])


def downgrade() -> None:
    op.drop_index("ix_uploads_uploaded_at", table_name="uploads")
    op.drop_index("ix_uploads_user_id", table_name="uploads")
    op.drop_table("uploads")
