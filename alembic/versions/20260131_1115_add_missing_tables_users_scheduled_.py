"""Add missing tables (users, scheduled_analyses, conversations)

Revision ID: b618d9cfc32d
Revises: 003
Create Date: 2026-01-31 11:15:45.200099

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b618d9cfc32d"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing tables (users, scheduled_analyses, conversations)"""
    # Create users table first (other tables depend on it)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    # Create scheduled_analyses table
    op.create_table(
        "scheduled_analyses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("query", sa.String(length=2048), nullable=False),
        sa.Column("cognitive_level", sa.String(length=50), nullable=False),
        sa.Column("department_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("frequency", sa.String(length=50), nullable=False),
        sa.Column("scheduled_time", sa.String(length=5), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("notify_email", sa.Boolean(), nullable=False),
        sa.Column("notify_webhook", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("next_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduled_analyses_is_active", "scheduled_analyses", ["is_active"], unique=False
    )
    op.create_index(
        "ix_scheduled_analyses_next_run", "scheduled_analyses", ["next_run"], unique=False
    )
    op.create_index(
        op.f("ix_scheduled_analyses_user_id"), "scheduled_analyses", ["user_id"], unique=False
    )

    # Create analysis_results table
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("cognitive_level", sa.String(length=50), nullable=True),
        sa.Column("department_codes", postgresql.ARRAY(sa.String(length=3)), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_results_dept",
        "analysis_results",
        ["department_codes"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_analysis_results_user_created",
        "analysis_results",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analysis_results_user_id"), "analysis_results", ["user_id"], unique=False
    )

    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("cognitive_level", sa.String(length=50), nullable=False),
        sa.Column("department_code", sa.String(length=3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversations_department_code"), "conversations", ["department_code"], unique=False
    )
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_index(
        "ix_conversations_user_updated", "conversations", ["user_id", "updated_at"], unique=False
    )

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_index(
        "ix_refresh_tokens_user_revoked", "refresh_tokens", ["user_id", "revoked"], unique=False
    )

    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("extra_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False
    )


def downgrade() -> None:
    """Remove added tables"""
    op.drop_table("messages")
    op.drop_table("refresh_tokens")
    op.drop_table("conversations")
    op.drop_table("analysis_results")
    op.drop_table("scheduled_analyses")
    op.drop_table("users")
