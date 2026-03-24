"""Add enhanced columns to news table and create if not exists.

Revision ID: 20260225_2000
Revises: 20260224_0100
Create Date: 2026-02-25 20:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

# revision identifiers
revision = "e4f5a6b7c8d9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create news table if it doesn't exist
    op.create_table(
        "news",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        # Enhanced RSS fields
        sa.Column("feed_name", sa.String(100), nullable=True),
        sa.Column("feed_category", sa.String(50), nullable=True),
        sa.Column("domain", sa.String(200), nullable=True),
        sa.Column("language", sa.String(5), nullable=True, server_default="fr"),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("tags", ARRAY(sa.String()), nullable=True),
        # Entity links
        sa.Column("mentioned_sirets", ARRAY(sa.String(14)), nullable=True),
        sa.Column("sectors", ARRAY(sa.String()), nullable=True),
        sa.Column("regions", ARRAY(sa.String()), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
        if_not_exists=True,
    )

    # Create indexes
    op.create_index("ix_news_source", "news", ["source"], if_not_exists=True)
    op.create_index("ix_news_published_at", "news", ["published_at"], if_not_exists=True)
    op.create_index("ix_news_feed_name", "news", ["feed_name"], if_not_exists=True)
    op.create_index("ix_news_feed_category", "news", ["feed_category"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_news_feed_category", table_name="news")
    op.drop_index("ix_news_feed_name", table_name="news")
    op.drop_index("ix_news_published_at", table_name="news")
    op.drop_index("ix_news_source", table_name="news")
    op.drop_table("news")
