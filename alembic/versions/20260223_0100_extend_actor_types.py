"""Extend actor_type enum with association, formation, financial.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-23 01:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 'association', 'formation', 'financial' to actor_type enum.

    PostgreSQL ALTER TYPE ... ADD VALUE cannot run inside a transaction block,
    so we commit the current transaction first and re-open it after.
    The IF NOT EXISTS clause makes this migration idempotent.
    """
    # Must run outside a transaction — PostgreSQL restriction on ADD VALUE.
    op.execute("COMMIT")
    op.execute("ALTER TYPE actor_type ADD VALUE IF NOT EXISTS 'association'")
    op.execute("ALTER TYPE actor_type ADD VALUE IF NOT EXISTS 'formation'")
    op.execute("ALTER TYPE actor_type ADD VALUE IF NOT EXISTS 'financial'")
    # Re-open a transaction so Alembic can stamp the version table.
    op.execute("BEGIN")


def downgrade() -> None:
    """No-op: PostgreSQL does not support removing values from an enum type."""
    pass
