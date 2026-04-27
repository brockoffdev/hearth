"""Update family member names to match design tokens (Izzy / Ellie).

Revises: 0002
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE family_members SET name = 'Izzy' WHERE name = 'Isabella'")
    op.execute("UPDATE family_members SET name = 'Ellie' WHERE name = 'Eliana'")


def downgrade() -> None:
    op.execute("UPDATE family_members SET name = 'Isabella' WHERE name = 'Izzy'")
    op.execute("UPDATE family_members SET name = 'Eliana' WHERE name = 'Ellie'")
