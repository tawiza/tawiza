"""Database model for datasets."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class DatasetDB(Base):
    """Database model for datasets."""

    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Storage
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dvc_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    label_studio_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Dataset metadata
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    format: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    # Annotation tracking
    annotations_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    annotations_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Statistics and quality
    statistics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    quality_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    annotation_progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metadata
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DatasetDB(id={self.id}, name={self.name}, "
            f"type={self.dataset_type}, status={self.status})>"
        )
