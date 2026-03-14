"""Database model for ML models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class MLModelDB(Base):
    """Database model for ML models."""

    __tablename__ = "ml_models"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    base_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Model metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Training info
    model_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Metrics and hyperparameters
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hyperparameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Deployment
    deployment_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    traffic_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tags
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

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
            f"<MLModelDB(id={self.id}, name={self.name}, "
            f"version={self.version}, status={self.status})>"
        )
