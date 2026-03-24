"""Database model for user feedback."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class FeedbackDB(Base):
    """Database model for user feedback on model predictions."""

    __tablename__ = "feedbacks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    model_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    prediction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Feedback content
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User & session tracking
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Data captured
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    feedback_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=True)

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
            f"<FeedbackDB(id={self.id}, model_id={self.model_id}, "
            f"type={self.feedback_type}, status={self.status})>"
        )
