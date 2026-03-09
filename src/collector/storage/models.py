"""SQLAlchemy models for the signals database."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Date,
    Double,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Signal(Base):
    """Unified table for collected signals from all sources."""

    __tablename__ = "signals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # 'sirene', 'dvf', 'presse', etc.
    source_url = Column(Text)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    event_date = Column(Date)

    # Location
    code_commune = Column(String(5))
    code_epci = Column(String(9))
    code_dept = Column(String(3))
    latitude = Column(Double)
    longitude = Column(Double)

    # Signal
    metric_name = Column(String(100), nullable=False)  # 'creation_entreprise', 'prix_m2', etc.
    metric_value = Column(Double)
    signal_type = Column(String(20))  # 'positif', 'negatif', 'neutre'
    confidence = Column(Double, default=0.5)

    # Raw data
    raw_data = Column(JSONB)
    extracted_text = Column(Text)
    entities = Column(JSONB)

    __table_args__ = (
        UniqueConstraint("source", "source_url", "event_date", name="uq_source_url_date"),
        Index("idx_signals_commune", "code_commune", "event_date"),
        Index("idx_signals_metric", "metric_name", "event_date"),
        Index("idx_signals_dept", "code_dept", "event_date"),
    )


class Anomaly(Base):
    """Detected anomalies from cross-source analysis."""

    __tablename__ = "anomalies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    code_commune = Column(String(5))

    # Anomaly
    anomaly_type = Column(String(50))  # 'spike', 'drop', 'trend_change'
    metrics = Column(JSONB)
    sources = Column(ARRAY(Text))
    score = Column(Double)

    # Context
    description = Column(Text)  # LLM-generated description
    related_signals = Column(ARRAY(BigInteger))

    # Status
    status = Column(String(20), default="new")  # 'new', 'confirmed', 'dismissed'
    reviewed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_anomalies_commune", "code_commune", "detected_at"),
        Index("idx_anomalies_status", "status"),
    )
