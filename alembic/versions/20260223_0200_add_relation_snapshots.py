"""Add relation_snapshots table for timeline tracking.

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-02-23 02:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the relation_snapshots table for timeline tracking."""
    # CREATE TABLE cannot use IF NOT EXISTS inside an Alembic transaction
    # when combined with index creation, so we handle it cleanly.
    op.execute("COMMIT")
    op.execute("""
        CREATE TABLE IF NOT EXISTS relation_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            department_code VARCHAR(10) NOT NULL,
            snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            total_actors INT NOT NULL DEFAULT 0,
            total_relations INT NOT NULL DEFAULT 0,
            l1_count INT NOT NULL DEFAULT 0,
            l2_count INT NOT NULL DEFAULT 0,
            l3_count INT NOT NULL DEFAULT 0,
            coverage_score FLOAT NOT NULL DEFAULT 0.0,
            resilience_score FLOAT NOT NULL DEFAULT 0.0,
            density FLOAT NOT NULL DEFAULT 0.0,
            communities_count INT NOT NULL DEFAULT 0,
            metrics_json JSONB DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_dept_time
            ON relation_snapshots(department_code, snapshot_at DESC);
    """)
    op.execute("BEGIN")


def downgrade() -> None:
    """Drop the relation_snapshots table."""
    op.execute("DROP TABLE IF EXISTS relation_snapshots;")
