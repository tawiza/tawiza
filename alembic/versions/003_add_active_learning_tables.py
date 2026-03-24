"""Add active learning tables (drift_reports and retraining_jobs)

Revision ID: 003
Revises: 002
Create Date: 2025-11-14

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create drift_reports and retraining_jobs tables."""
    # Create drift_reports table
    op.create_table(
        "drift_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("drift_type", sa.String(length=50), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("drift_score", sa.Float(), nullable=False),
        sa.Column("is_drifted", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indices for drift_reports
    op.create_index("ix_drift_reports_model_name", "drift_reports", ["model_name"])
    op.create_index("ix_drift_reports_model_version", "drift_reports", ["model_version"])
    op.create_index("ix_drift_reports_drift_type", "drift_reports", ["drift_type"])
    op.create_index("ix_drift_reports_is_drifted", "drift_reports", ["is_drifted"])
    op.create_index("ix_drift_reports_severity", "drift_reports", ["severity"])
    op.create_index("ix_drift_reports_created_at", "drift_reports", ["created_at"])

    # Create retraining_jobs table
    op.create_table(
        "retraining_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_reason", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("base_model_version", sa.String(length=50), nullable=False),
        sa.Column("new_samples_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("fine_tuning_job_id", sa.String(length=255), nullable=True),
        sa.Column("new_model_version", sa.String(length=50), nullable=True),
        sa.Column("drift_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indices for retraining_jobs
    op.create_index("ix_retraining_jobs_model_name", "retraining_jobs", ["model_name"])
    op.create_index("ix_retraining_jobs_trigger_reason", "retraining_jobs", ["trigger_reason"])
    op.create_index("ix_retraining_jobs_status", "retraining_jobs", ["status"])
    op.create_index(
        "ix_retraining_jobs_fine_tuning_job_id", "retraining_jobs", ["fine_tuning_job_id"]
    )
    op.create_index("ix_retraining_jobs_drift_report_id", "retraining_jobs", ["drift_report_id"])
    op.create_index("ix_retraining_jobs_created_at", "retraining_jobs", ["created_at"])


def downgrade() -> None:
    """Drop drift_reports and retraining_jobs tables."""
    # Drop retraining_jobs table
    op.drop_index("ix_retraining_jobs_created_at", table_name="retraining_jobs")
    op.drop_index("ix_retraining_jobs_drift_report_id", table_name="retraining_jobs")
    op.drop_index("ix_retraining_jobs_fine_tuning_job_id", table_name="retraining_jobs")
    op.drop_index("ix_retraining_jobs_status", table_name="retraining_jobs")
    op.drop_index("ix_retraining_jobs_trigger_reason", table_name="retraining_jobs")
    op.drop_index("ix_retraining_jobs_model_name", table_name="retraining_jobs")
    op.drop_table("retraining_jobs")

    # Drop drift_reports table
    op.drop_index("ix_drift_reports_created_at", table_name="drift_reports")
    op.drop_index("ix_drift_reports_severity", table_name="drift_reports")
    op.drop_index("ix_drift_reports_is_drifted", table_name="drift_reports")
    op.drop_index("ix_drift_reports_drift_type", table_name="drift_reports")
    op.drop_index("ix_drift_reports_model_version", table_name="drift_reports")
    op.drop_index("ix_drift_reports_model_name", table_name="drift_reports")
    op.drop_table("drift_reports")
