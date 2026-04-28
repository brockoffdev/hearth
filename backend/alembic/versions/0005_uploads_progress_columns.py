"""Add upload progress columns and pipeline_stage_durations table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27 00:00:05.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add progress tracking columns to uploads table.
    op.add_column("uploads", sa.Column("current_stage", sa.Text(), nullable=True))
    op.add_column(
        "uploads",
        sa.Column(
            "completed_stages",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column("uploads", sa.Column("cell_progress", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("total_cells", sa.Integer(), nullable=True))

    # Create pipeline_stage_durations table for per-stage timing measurements.
    op.create_table(
        "pipeline_stage_durations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["uploads.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_stage_durations_upload_id",
        "pipeline_stage_durations",
        ["upload_id"],
    )
    op.create_index(
        "ix_pipeline_stage_durations_stage",
        "pipeline_stage_durations",
        ["stage"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_stage_durations_stage", table_name="pipeline_stage_durations"
    )
    op.drop_index(
        "ix_pipeline_stage_durations_upload_id",
        table_name="pipeline_stage_durations",
    )
    op.drop_table("pipeline_stage_durations")

    op.drop_column("uploads", "total_cells")
    op.drop_column("uploads", "cell_progress")
    op.drop_column("uploads", "completed_stages")
    op.drop_column("uploads", "current_stage")
