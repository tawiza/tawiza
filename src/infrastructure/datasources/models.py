"""SQLAlchemy models for data sources."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.database import Base


class Enterprise(Base):
    """Enterprise entity - central table for company data."""

    __tablename__ = "enterprises"

    # Primary key
    siret: Mapped[str] = mapped_column(String(14), primary_key=True)
    siren: Mapped[str] = mapped_column(String(9), nullable=False, index=True)

    # Identity
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    nom_commercial: Mapped[str | None] = mapped_column(String(255))

    # Address
    adresse: Mapped[str | None] = mapped_column(Text)
    code_postal: Mapped[str | None] = mapped_column(String(5), index=True)
    commune: Mapped[str | None] = mapped_column(String(100), index=True)
    departement: Mapped[str | None] = mapped_column(String(3), index=True)
    region: Mapped[str | None] = mapped_column(String(2), index=True)

    # Geolocation (stored separately, PostGIS geography computed)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))

    # Activity
    naf_code: Mapped[str | None] = mapped_column(String(6), index=True)
    naf_libelle: Mapped[str | None] = mapped_column(String(255))
    effectif: Mapped[str | None] = mapped_column(String(10))

    # Metadata
    date_creation: Mapped[date | None] = mapped_column(Date)
    forme_juridique: Mapped[str | None] = mapped_column(String(100))

    # Enrichment
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Sync metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    source_versions: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    bodacc_events: Mapped[list["BodaccEvent"]] = relationship(
        back_populates="enterprise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Enterprise {self.siret} {self.nom[:30]}>"


class BodaccEvent(Base):
    """BODACC legal announcements (creations, modifications, procedures)."""

    __tablename__ = "bodacc_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    siret: Mapped[str | None] = mapped_column(
        String(14), ForeignKey("enterprises.siret", ondelete="CASCADE")
    )
    siren: Mapped[str | None] = mapped_column(String(9), index=True)

    # Event data
    type: Mapped[str] = mapped_column(String(50), index=True)
    # Types: 'creation', 'modification', 'radiation', 'procedure_collective'
    date_publication: Mapped[date] = mapped_column(Date, index=True)
    numero_annonce: Mapped[str | None] = mapped_column(String(50), unique=True)
    contenu: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    enterprise: Mapped[Optional["Enterprise"]] = relationship(back_populates="bodacc_events")

    def __repr__(self) -> str:
        return f"<BodaccEvent {self.type} {self.date_publication}>"


class BoampMarket(Base):
    """BOAMP public procurement announcements."""

    __tablename__ = "boamp_markets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(100), unique=True)

    # Market info
    titre: Mapped[str] = mapped_column(Text)
    acheteur: Mapped[str | None] = mapped_column(String(255))
    acheteur_siret: Mapped[str | None] = mapped_column(String(14), index=True)

    type: Mapped[str] = mapped_column(String(50), index=True)
    # Types: 'appel_offres', 'attribution', 'avis_rectificatif'
    montant_estime: Mapped[float | None] = mapped_column(Numeric(15, 2))

    date_publication: Mapped[date] = mapped_column(Date, index=True)
    date_limite: Mapped[date | None] = mapped_column(Date)

    departement: Mapped[str | None] = mapped_column(String(3), index=True)
    secteur: Mapped[str | None] = mapped_column(String(100))
    cpv_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<BoampMarket {self.reference} {self.titre[:30]}>"


class News(Base):
    """News articles from RSS feeds."""

    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    # Sources: 'rss', 'gdelt', 'google_news'

    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    summary: Mapped[str | None] = mapped_column(Text)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    # Enhanced RSS fields
    feed_name: Mapped[str | None] = mapped_column(String(100), index=True)
    feed_category: Mapped[str | None] = mapped_column(String(50), index=True)
    domain: Mapped[str | None] = mapped_column(String(200))
    language: Mapped[str | None] = mapped_column(String(5), default="fr")
    author: Mapped[str | None] = mapped_column(String(200))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # AI enrichment
    ai_summary: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(10))  # positif, negatif, neutre

    # Links to entities
    mentioned_sirets: Mapped[list[str] | None] = mapped_column(ARRAY(String(14)))
    sectors: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    regions: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<News {self.source} {self.title[:30]}>"


# Indexes for full-text search (created via Alembic migration)
# CREATE INDEX idx_enterprises_nom_trgm ON enterprises USING GIN(nom gin_trgm_ops);
