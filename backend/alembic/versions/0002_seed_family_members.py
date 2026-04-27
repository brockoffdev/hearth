"""Seed default family members: Bryant, Danielle, Isabella, Eliana, Family.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27 00:00:01.000000

Note on hue ranges: Danielle's range wraps around 0 degrees (low=350, high=20).
Consumers of hue_range_low/hue_range_high should treat low > high as a
wrap-around range (i.e. [350..360] union [0..20]).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default family members locked in from the design system.
# color_hex_center values match frontend/src/lib/family.ts colour tokens.
_FAMILY_MEMBERS = [
    {
        "name": "Bryant",
        "color_hex_center": "#2E5BA8",  # Blue
        "hue_range_low": 200,
        "hue_range_high": 230,
        "google_calendar_id": None,
        "sort_order": 0,
    },
    {
        "name": "Danielle",
        "color_hex_center": "#C0392B",  # Red -- hue wraps: [350..360] union [0..20]
        "hue_range_low": 350,
        "hue_range_high": 20,
        "google_calendar_id": None,
        "sort_order": 1,
    },
    {
        "name": "Isabella",
        "color_hex_center": "#7B4FB8",  # Purple
        "hue_range_low": 253,
        "hue_range_high": 283,
        "google_calendar_id": None,
        "sort_order": 2,
    },
    {
        "name": "Eliana",
        "color_hex_center": "#E17AA1",  # Pink
        "hue_range_low": 320,
        "hue_range_high": 350,
        "google_calendar_id": None,
        "sort_order": 3,
    },
    {
        "name": "Family",
        "color_hex_center": "#D97A2C",  # Orange
        "hue_range_low": 11,
        "hue_range_high": 41,
        "google_calendar_id": None,
        "sort_order": 4,
    },
]

_SEEDED_NAMES = [m["name"] for m in _FAMILY_MEMBERS]


def upgrade() -> None:
    family_members = sa.table(
        "family_members",
        sa.column("name", sa.Text()),
        sa.column("color_hex_center", sa.Text()),
        sa.column("hue_range_low", sa.Integer()),
        sa.column("hue_range_high", sa.Integer()),
        sa.column("google_calendar_id", sa.Text()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(family_members, _FAMILY_MEMBERS)


def downgrade() -> None:
    # Build the IN clause with individual named parameters for SQLite compatibility.
    placeholders = ", ".join(f":name_{i}" for i in range(len(_SEEDED_NAMES)))
    params = {f"name_{i}": name for i, name in enumerate(_SEEDED_NAMES)}
    op.execute(
        sa.text(f"DELETE FROM family_members WHERE name IN ({placeholders})").bindparams(
            **params
        )
    )
