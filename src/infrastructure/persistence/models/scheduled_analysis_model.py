"""SQLAlchemy model for scheduled TAJINE analyses.

Stores configuration for recurring or one-time TAJINE analysis jobs.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.database import Base


class ScheduleFrequency(StrEnum):
    """Frequency options for scheduled analyses."""

    ONCE = "once"  # One-time execution
    HOURLY = "hourly"  # Every hour
    DAILY = "daily"  # Every day at specified time
    WEEKLY = "weekly"  # Every week on specified day
    MONTHLY = "monthly"  # Every month on specified day


class ScheduledAnalysisDB(Base):
    """Scheduled TAJINE analysis job.

    Stores the configuration for a scheduled analysis including:
    - Query to execute
    - Cognitive level to use
    - Schedule configuration (frequency, time, day)
    - Target department(s)
    - Notification settings
    """

    __tablename__ = "scheduled_analyses"
    __table_args__ = (
        Index("ix_scheduled_analyses_user_id", "user_id"),
        Index("ix_scheduled_analyses_is_active", "is_active"),
        Index("ix_scheduled_analyses_next_run", "next_run"),
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User who created this schedule
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Analysis configuration
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    query: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    cognitive_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="analytical",
    )

    # Target departments (null = all departments)
    department_codes: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Schedule configuration
    frequency: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ScheduleFrequency.DAILY.value,
    )

    # Time of day to run (HH:MM format, 24h)
    scheduled_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        default="08:00",
    )

    # Day of week (0=Monday, 6=Sunday) for weekly schedules
    day_of_week: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Day of month (1-31) for monthly schedules
    day_of_month: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Timezone for scheduling
    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Europe/Paris",
    )

    # Notification settings
    notify_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    notify_webhook: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Tracking
    next_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_run: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    run_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    error_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<ScheduledAnalysis(id={self.id}, name='{self.name}', frequency={self.frequency})>"
