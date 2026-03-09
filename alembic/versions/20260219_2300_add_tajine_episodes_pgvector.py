"""Add tajine_episodes table with pgvector support

Revision ID: c7a3e5f12d89
Revises: b618d9cfc32d
Create Date: 2026-02-19 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a3e5f12d89"
down_revision: str | None = "b618d9cfc32d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add tajine_episodes table for episodic memory with pgvector embeddings."""
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tajine_episodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Query context
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "query_type",
            sa.String(length=50),
            nullable=False,
            server_default="general",
        ),
        # Territorial context
        sa.Column("territory", sa.String(length=10), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column(
            "keywords",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        # Analysis results
        sa.Column(
            "analysis_result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "cognitive_levels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column(
            "mode",
            sa.String(length=20),
            server_default="fast",
            nullable=False,
        ),
        # PPDSL cycle data
        sa.Column(
            "ppdsl_phases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        # User feedback
        sa.Column("user_feedback", sa.Text(), nullable=True),
        sa.Column("feedback_score", sa.Float(), nullable=True),
        sa.Column(
            "corrections",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        # Metadata
        sa.Column(
            "duration_ms",
            sa.Float(),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column(
            "sources_used",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "tools_called",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add embedding column with pgvector type (768 dims = nomic-embed-text)
    op.execute("ALTER TABLE tajine_episodes ADD COLUMN embedding vector(768)")

    # HNSW index for fast vector similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS tajine_episodes_embedding_idx "
        "ON tajine_episodes USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_tajine_episodes_territory",
        "tajine_episodes",
        ["territory"],
    )
    op.create_index(
        "ix_tajine_episodes_sector",
        "tajine_episodes",
        ["sector"],
    )
    op.create_index(
        "ix_tajine_episodes_created_at",
        "tajine_episodes",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_tajine_episodes_feedback",
        "tajine_episodes",
        ["feedback_score"],
        postgresql_where=sa.text("feedback_score IS NOT NULL"),
    )

    # GIN index for JSONB analysis results
    op.execute(
        "CREATE INDEX IF NOT EXISTS tajine_episodes_analysis_gin "
        "ON tajine_episodes USING gin (analysis_result)"
    )


def downgrade() -> None:
    """Remove tajine_episodes table."""
    op.drop_table("tajine_episodes")
    # Don't drop vector extension as other tables may use it
