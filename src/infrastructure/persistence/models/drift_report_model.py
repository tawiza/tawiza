"""Database model for drift reports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class DriftReportDB(Base):
    """Database model for drift detection reports."""

    __tablename__ = "drift_reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    drift_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    drift_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_drifted: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Optional fields
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DriftReportDB(id={self.id}, model={self.model_name}:{self.model_version}, "
            f"type={self.drift_type}, drifted={self.is_drifted}, severity={self.severity})>"
        )
