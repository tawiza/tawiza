"""Initial schema with ML models, datasets, and training jobs.

Revision ID: 001
Revises:
Create Date: 2025-11-07

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial tables for ML models, datasets, and training jobs."""

    # Create ml_models table
    op.create_table(
        "ml_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("base_model", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("model_path", sa.String(512), nullable=True),
        sa.Column("mlflow_run_id", sa.String(255), nullable=True, index=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("hyperparameters", postgresql.JSONB(), nullable=True),
        sa.Column("deployment_strategy", sa.String(50), nullable=True),
        sa.Column("traffic_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
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
        sa.UniqueConstraint("name", "version", name="uq_model_name_version"),
    )

    # Create datasets table
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("storage_path", sa.String(512), nullable=True),
        sa.Column("label_studio_project_id", sa.Integer(), nullable=True, index=True),
        sa.Column("statistics", postgresql.JSONB(), nullable=True),
        sa.Column("quality_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("annotation_progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
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
    )

    # Create training_jobs table
    op.create_table(
        "training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("mlflow_run_id", sa.String(255), nullable=True, index=True),
        sa.Column("hyperparameters", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
    )

    # Create indexes for better query performance
    op.create_index("idx_ml_models_deployed_at", "ml_models", ["deployed_at"])
    op.create_index("idx_training_jobs_model_dataset", "training_jobs", ["model_id", "dataset_id"])
    op.create_index("idx_training_jobs_completed_at", "training_jobs", ["completed_at"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("idx_training_jobs_completed_at", table_name="training_jobs")
    op.drop_index("idx_training_jobs_model_dataset", table_name="training_jobs")
    op.drop_index("idx_ml_models_deployed_at", table_name="ml_models")

    op.drop_table("training_jobs")
    op.drop_table("datasets")
    op.drop_table("ml_models")
