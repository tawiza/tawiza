"""Add actors, relations, and relation_sources tables

Revision ID: a1b2c3d4e5f6
Revises: c7a3e5f12d89
Create Date: 2026-02-21 22:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "c7a3e5f12d89"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create actors, relations, and relation_sources tables with enum types."""

    # --- Enum types ---
    op.execute("""
        CREATE TYPE actor_type AS ENUM (
            'enterprise', 'territory', 'institution', 'sector'
        )
    """)

    op.execute("""
        CREATE TYPE relation_type AS ENUM (
            'structural', 'inferred', 'hypothetical'
        )
    """)

    op.execute("""
        CREATE TYPE source_type AS ENUM (
            'bodacc', 'sirene', 'insee', 'dvf', 'infogreffe', 'model'
        )
    """)

    # --- Table: actors ---
    op.execute("""
        CREATE TABLE actors (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type        actor_type NOT NULL,
            external_id VARCHAR(50) NOT NULL,
            name        VARCHAR(255) NOT NULL,
            department_code VARCHAR(10),
            metadata    JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMP NOT NULL DEFAULT now(),
            updated_at  TIMESTAMP NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_actors_external_id ON actors (external_id)
    """)

    op.execute("""
        CREATE INDEX ix_actors_department_code ON actors (department_code)
    """)

    op.execute("""
        CREATE INDEX ix_actors_type ON actors (type)
    """)

    # --- Table: relations ---
    op.execute("""
        CREATE TABLE relations (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_actor_id   UUID NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
            target_actor_id   UUID NOT NULL REFERENCES actors(id) ON DELETE CASCADE,
            relation_type     relation_type NOT NULL,
            subtype           VARCHAR(100) NOT NULL,
            confidence        FLOAT NOT NULL DEFAULT 0.0,
            weight            FLOAT DEFAULT 1.0,
            evidence          JSONB NOT NULL DEFAULT '{}',
            detected_at       TIMESTAMP NOT NULL DEFAULT now(),
            investigation_id  VARCHAR(100)
        )
    """)

    op.execute("""
        CREATE INDEX ix_relations_source_actor_id ON relations (source_actor_id)
    """)

    op.execute("""
        CREATE INDEX ix_relations_target_actor_id ON relations (target_actor_id)
    """)

    op.execute("""
        CREATE INDEX ix_relations_relation_type ON relations (relation_type)
    """)

    op.execute("""
        CREATE INDEX ix_relations_investigation_id ON relations (investigation_id)
            WHERE investigation_id IS NOT NULL
    """)

    # --- Table: relation_sources ---
    op.execute("""
        CREATE TABLE relation_sources (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            relation_id             UUID NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
            source_type             source_type NOT NULL,
            source_ref              TEXT,
            contributed_confidence  FLOAT NOT NULL DEFAULT 0.0
        )
    """)

    op.execute("""
        CREATE INDEX ix_relation_sources_relation_id ON relation_sources (relation_id)
    """)


def downgrade() -> None:
    """Drop relation_sources, relations, actors tables and their enum types."""
    op.execute("DROP TABLE IF EXISTS relation_sources CASCADE")
    op.execute("DROP TABLE IF EXISTS relations CASCADE")
    op.execute("DROP TABLE IF EXISTS actors CASCADE")
    op.execute("DROP TYPE IF EXISTS source_type")
    op.execute("DROP TYPE IF EXISTS relation_type")
    op.execute("DROP TYPE IF EXISTS actor_type")
