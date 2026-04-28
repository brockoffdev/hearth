"""Add ix_event_corrections_event_id (model declared it; 0006 missed creating it).

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_event_corrections_event_id",
        "event_corrections",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_corrections_event_id", table_name="event_corrections")
