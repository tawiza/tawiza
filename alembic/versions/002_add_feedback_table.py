"""Add feedback table for user feedback collection.

Revision ID: 002
Revises: 001
Create Date: 2025-11-07

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create feedbacks table."""

    # Create feedbacks table
    op.create_table(
        "feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("prediction_id", sa.String(255), nullable=True, index=True),
        sa.Column("feedback_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=True, index=True),
        sa.Column("session_id", sa.String(255), nullable=True, index=True),
        sa.Column("input_data", postgresql.JSONB(), nullable=True),
        sa.Column("output_data", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["model_id"], ["ml_models.id"], ondelete="CASCADE"),
    )

    # Create indexes for better query performance
    op.create_index("idx_feedbacks_model_created", "feedbacks", ["model_id", "created_at"])
    op.create_index("idx_feedbacks_type_status", "feedbacks", ["feedback_type", "status"])
    op.create_index(
        "idx_feedbacks_negative",
        "feedbacks",
        ["model_id", "feedback_type"],
        postgresql_where=sa.text(
            "feedback_type IN ('thumbs_down', 'bug_report', 'correction') OR (feedback_type = 'rating' AND rating <= 2)"
        ),
    )


def downgrade() -> None:
    """Drop feedbacks table."""
    op.drop_index("idx_feedbacks_negative", table_name="feedbacks")
    op.drop_index("idx_feedbacks_type_status", table_name="feedbacks")
    op.drop_index("idx_feedbacks_model_created", table_name="feedbacks")
    op.drop_table("feedbacks")
