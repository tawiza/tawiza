"""Territorial historical data model.

Stores time-series data for territorial indicators to replace synthetic trends.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class TerritorialSnapshot(Base):
    """Historical snapshot of territorial indicators.

    Captures point-in-time data for a territory, enabling real trend analysis.
    """

    __tablename__ = "territorial_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Territory identification
    territory_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    territory_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamp
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    # Core indicators (nullable for partial snapshots)
    entreprises_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entreprises_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entreprises_closed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_density: Mapped[float | None] = mapped_column(Float, nullable=True)

    unemployment_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_income: Mapped[float | None] = mapped_column(Float, nullable=True)

    real_estate_price_m2: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Attractiveness scores (computed)
    attractiveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    infrastructure_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    capital_humain_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    environnement_eco_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualite_vie_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accessibilite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    innovation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Extended data (JSON for flexibility)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Data source tracking
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Composite index for efficient time-range queries
    __table_args__ = (Index("idx_territory_date", "territory_code", "snapshot_date"),)

    def __repr__(self) -> str:
        return f"<TerritorialSnapshot {self.territory_code} @ {self.snapshot_date}>"


class TerritorialTrend(Base):
    """Pre-computed trends for faster access.

    Aggregates snapshots into trend summaries.
    """

    __tablename__ = "territorial_trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    territory_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # 3m, 6m, 12m, 24m

    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Trend data
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_direction: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # up, down, stable

    # Time series data points (JSON array)
    data_points: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("idx_trend_lookup", "territory_code", "indicator", "period"),)
