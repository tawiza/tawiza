"""Web snapshot model - Snapshots de sites web depuis Common Crawl.

Stocke les analyses LLM de contenu web archivé pour le suivi
temporel des entreprises (CrawlIntel pipeline).
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from src.infrastructure.persistence.database import Base


class WebSnapshotDB(Base):
    """Snapshot analysé d'un site web d'entreprise."""

    __tablename__ = "web_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Entreprise
    siret = Column(String(14), nullable=False, index=True)
    url = Column(String(500), nullable=False)

    # Crawl metadata
    crawl_date = Column(DateTime, nullable=False)
    crawl_id = Column(String(30), nullable=False)  # CC-MAIN-2025-51
    content_hash = Column(String(16), nullable=False)
    content_length = Column(Integer, default=0)

    # LLM-extracted signals
    activity_status = Column(String(20), default="unknown")
    employee_mentions = Column(Integer)
    products_services = Column(ARRAY(String), default=[])
    job_openings = Column(Integer, default=0)
    sentiment_score = Column(Float, default=0.0)
    notable_elements = Column(ARRAY(String), default=[])
    confidence = Column(Float, default=0.0)

    # Comparison with previous snapshot
    changes = Column(ARRAY(String), default=[])
    trend = Column(String(20))  # growth, stable, decline, pivot, closure

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "siret",
            "crawl_id",
            "content_hash",
            name="uq_web_snapshot_unique",
        ),
        Index("idx_ws_siret_date", "siret", "crawl_date"),
        Index("idx_ws_crawl_date", "crawl_date"),
        Index("idx_ws_activity", "activity_status"),
    )


class CrawlIntelSignalDB(Base):
    """Signal détecté par le pipeline CrawlIntel."""

    __tablename__ = "crawlintel_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Entreprise
    siret = Column(String(14), nullable=False, index=True)
    nom = Column(String(200))
    code_dept = Column(String(5))

    # Signal
    signal_type = Column(String(20), nullable=False)  # positif, negatif, neutre
    metric_name = Column(String(50), nullable=False)
    confidence = Column(Float, default=0.0)

    # Details
    description = Column(Text)
    details = Column(Text)
    source_url = Column(String(500))

    # Timeline context
    snapshots_count = Column(Integer)
    timeline_start = Column(DateTime)
    timeline_end = Column(DateTime)

    # Raw pattern data
    raw_data = Column(JSONB, default={})

    # Audit
    detected_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_cis_siret", "siret"),
        Index("idx_cis_dept", "code_dept"),
        Index("idx_cis_type", "signal_type"),
        Index("idx_cis_metric", "metric_name"),
        Index("idx_cis_detected", "detected_at"),
    )
