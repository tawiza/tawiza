"""SQLAlchemy models for the Decisions module (stakeholders, relations, decisions)."""

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.database import Base

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StakeholderType(enum.StrEnum):
    collectivite = "collectivite"
    entreprise = "entreprise"
    institution = "institution"
    association = "association"


class TerritoryScope(enum.StrEnum):
    commune = "commune"
    departement = "departement"
    region = "region"
    national = "national"


class StakeholderRelationType(enum.StrEnum):
    collaboration = "collaboration"
    hierarchie = "hierarchie"
    financement = "financement"
    opposition = "opposition"
    consultation = "consultation"


class DecisionStatus(enum.StrEnum):
    draft = "draft"
    en_consultation = "en_consultation"
    validee = "validee"
    en_cours = "en_cours"
    terminee = "terminee"


class DecisionPriority(enum.StrEnum):
    basse = "basse"
    moyenne = "moyenne"
    haute = "haute"
    urgente = "urgente"


class DecisionRole(enum.StrEnum):
    decideur = "decideur"
    consulte = "consulte"
    informe = "informe"
    executant = "executant"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class StakeholderDB(Base):
    """A human stakeholder (decision-maker, institution rep, etc.)."""

    __tablename__ = "stakeholders"

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(
        Enum(StakeholderType, name="stakeholder_type", create_type=True),
        nullable=False,
        index=True,
    )
    domains: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    territory_dept: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    territory_scope: Mapped[str] = mapped_column(
        Enum(TerritoryScope, name="territory_scope", create_type=True),
        nullable=False,
        server_default="departement",
    )
    influence_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    outgoing_relations: Mapped[list["StakeholderRelationDB"]] = relationship(
        "StakeholderRelationDB",
        foreign_keys="StakeholderRelationDB.from_id",
        back_populates="from_stakeholder",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list["StakeholderRelationDB"]] = relationship(
        "StakeholderRelationDB",
        foreign_keys="StakeholderRelationDB.to_id",
        back_populates="to_stakeholder",
        cascade="all, delete-orphan",
    )
    decision_links: Mapped[list["DecisionStakeholderDB"]] = relationship(
        "DecisionStakeholderDB",
        back_populates="stakeholder",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_stakeholders_dept_type", "territory_dept", "type"),)

    def __repr__(self) -> str:
        return f'<StakeholderDB "{self.name}" ({self.role} @ {self.organization})>'


class StakeholderRelationDB(Base):
    """A relation between two stakeholders."""

    __tablename__ = "stakeholder_relations"

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=uuid4)
    from_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("stakeholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("stakeholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        Enum(
            StakeholderRelationType,
            name="stakeholder_relation_type",
            create_type=True,
        ),
        nullable=False,
    )
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bidirectional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    from_stakeholder: Mapped["StakeholderDB"] = relationship(
        "StakeholderDB",
        foreign_keys=[from_id],
        back_populates="outgoing_relations",
    )
    to_stakeholder: Mapped["StakeholderDB"] = relationship(
        "StakeholderDB",
        foreign_keys=[to_id],
        back_populates="incoming_relations",
    )

    def __repr__(self) -> str:
        return f"<StakeholderRelationDB {self.type} {self.from_id} -> {self.to_id}>"


class DecisionDB(Base):
    """A decision linked to territorial analyses."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Enum(DecisionStatus, name="decision_status", create_type=True),
        nullable=False,
        default=DecisionStatus.draft,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        Enum(DecisionPriority, name="decision_priority", create_type=True),
        nullable=False,
        default=DecisionPriority.moyenne,
    )
    dept: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    stakeholder_links: Mapped[list["DecisionStakeholderDB"]] = relationship(
        "DecisionStakeholderDB",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    recommendations: Mapped[list["DecisionRecommendationDB"]] = relationship(
        "DecisionRecommendationDB",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_decisions_dept_status", "dept", "status"),)

    def __repr__(self) -> str:
        return f'<DecisionDB "{self.title}" ({self.status})>'


class DecisionStakeholderDB(Base):
    """Link between a decision and a stakeholder with RACI role."""

    __tablename__ = "decision_stakeholders"

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=uuid4)
    decision_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stakeholder_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("stakeholders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_in_decision: Mapped[str] = mapped_column(
        Enum(DecisionRole, name="decision_role", create_type=True),
        nullable=False,
    )
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    decision: Mapped["DecisionDB"] = relationship("DecisionDB", back_populates="stakeholder_links")
    stakeholder: Mapped["StakeholderDB"] = relationship(
        "StakeholderDB", back_populates="decision_links", lazy="selectin"
    )

    __table_args__ = (
        Index(
            "ix_decision_stakeholders_unique",
            "decision_id",
            "stakeholder_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<DecisionStakeholderDB {self.role_in_decision} decision={self.decision_id}>"


class DecisionRecommendationDB(Base):
    """An AI-generated recommendation for a decision."""

    __tablename__ = "decision_recommendations"

    id: Mapped[str] = mapped_column(PGUUID(as_uuid=False), primary_key=True, default=uuid4)
    decision_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_role: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_points: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Relationship
    decision: Mapped["DecisionDB"] = relationship("DecisionDB", back_populates="recommendations")

    def __repr__(self) -> str:
        return f'<DecisionRecommendationDB "{self.target_role}" conf={self.confidence:.2f}>'
