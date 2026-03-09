"""Extend actor_type enum with 9 ecosystem actor types for Phase 7.

Revision ID: c3d4e5f6a7b8
Revises: d4e5f6a7b8c9
Create Date: 2026-02-24 01:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = [
    "competitiveness_pole",
    "cluster",
    "incubator",
    "dev_agency",
    "research_lab",
    "employment_basin",
    "collectivity",
    "economic_zone",
    "professional_network",
]


def upgrade() -> None:
    """Add 9 ecosystem actor types to actor_type enum.

    PostgreSQL ALTER TYPE ... ADD VALUE cannot run inside a transaction block,
    so we commit the current transaction first and re-open it after.
    The IF NOT EXISTS clause makes this migration idempotent.
    """
    op.execute("COMMIT")
    for t in _NEW_TYPES:
        op.execute(f"ALTER TYPE actor_type ADD VALUE IF NOT EXISTS '{t}'")
    op.execute("BEGIN")


def downgrade() -> None:
    """No-op: PostgreSQL does not support removing values from an enum type."""
    pass
