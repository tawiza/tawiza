"""SQLAlchemy models for the actor-relation graph.

Defines ActorModel, RelationModel, and RelationSourceModel which represent
the economic relationship graph between actors (enterprises, territories,
institutions, sectors).
"""

import enum
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.database import Base

# ---------------------------------------------------------------------------
# Enums – values must match the PostgreSQL enum types created by migration.
# ---------------------------------------------------------------------------


class ActorType(enum.StrEnum):
    """Type of economic actor."""

    enterprise = "enterprise"
    territory = "territory"
    institution = "institution"
    sector = "sector"
    association = "association"
    formation = "formation"
    financial = "financial"


class RelationType(enum.StrEnum):
    """Confidence tier of a detected relation."""

    structural = "structural"
    inferred = "inferred"
    hypothetical = "hypothetical"


class RelationSourceType(enum.StrEnum):
    """Data source that contributed evidence for a relation."""

    bodacc = "bodacc"
    sirene = "sirene"
    insee = "insee"
    dvf = "dvf"
    infogreffe = "infogreffe"
    model = "model"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ActorModel(Base):
    """An economic actor (enterprise, territory, institution, or sector).

    Represents a node in the relationship graph.
    """

    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(
        Enum(ActorType, name="actor_type", create_type=False),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="now()")

    # Relationships
    outgoing_relations: Mapped[list["RelationModel"]] = relationship(
        "RelationModel",
        foreign_keys="RelationModel.source_actor_id",
        back_populates="source_actor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_relations: Mapped[list["RelationModel"]] = relationship(
        "RelationModel",
        foreign_keys="RelationModel.target_actor_id",
        back_populates="target_actor",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f'<ActorModel {self.type}:{self.external_id} "{self.name}">'


class RelationModel(Base):
    """A directed relation between two actors.

    Represents an edge in the relationship graph, with confidence scoring
    and supporting evidence.
    """

    __tablename__ = "relations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid4)
    source_actor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_actor_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(
        Enum(RelationType, name="relation_type", create_type=False),
        nullable=False,
        index=True,
    )
    subtype: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default="now()")
    investigation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    source_actor: Mapped["ActorModel"] = relationship(
        "ActorModel",
        foreign_keys=[source_actor_id],
        back_populates="outgoing_relations",
    )
    target_actor: Mapped["ActorModel"] = relationship(
        "ActorModel",
        foreign_keys=[target_actor_id],
        back_populates="incoming_relations",
    )
    sources: Mapped[list["RelationSourceModel"]] = relationship(
        "RelationSourceModel",
        back_populates="relation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<RelationModel {self.relation_type}:{self.subtype} "
            f"{self.source_actor_id} -> {self.target_actor_id} "
            f"conf={self.confidence:.2f}>"
        )


class RelationSourceModel(Base):
    """Evidence source backing a relation.

    Each relation can be supported by multiple data sources, each
    contributing a partial confidence score.
    """

    __tablename__ = "relation_sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=uuid4)
    relation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("relations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        Enum(RelationSourceType, name="source_type", create_type=False),
        nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    contributed_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationship
    relation: Mapped["RelationModel"] = relationship(
        "RelationModel",
        back_populates="sources",
    )

    def __repr__(self) -> str:
        return f"<RelationSourceModel {self.source_type} conf={self.contributed_confidence:.2f}>"
