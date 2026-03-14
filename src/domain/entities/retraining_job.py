"""Retraining job entity for managing automated model retraining."""

from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from .base import Entity


class RetrainingStatus(StrEnum):
    """Status of a retraining job."""

    PENDING = "pending"  # Job created, not started
    RUNNING = "running"  # Job is currently executing
    COMPLETED = "completed"  # Job finished successfully
    FAILED = "failed"  # Job failed with error
    CANCELLED = "cancelled"  # Job was cancelled


class RetrainingTriggerReason(StrEnum):
    """Reason that triggered retraining."""

    DRIFT_DETECTED = "drift_detected"  # Concept/data drift detected
    ERROR_THRESHOLD = "error_threshold"  # Error rate exceeded threshold
    SUFFICIENT_DATA = "sufficient_data"  # Enough new labeled data collected
    MANUAL = "manual"  # Manually triggered
    SCHEDULED = "scheduled"  # Scheduled periodic retraining
    FEEDBACK_VOLUME = "feedback_volume"  # High volume of negative feedback


class RetrainingJob(Entity):
    """Entity representing an automated retraining job.

    Manages the lifecycle of model retraining triggered by various conditions
    such as drift detection, error thresholds, or sufficient new data.
    """

    def __init__(
        self,
        trigger_reason: RetrainingTriggerReason,
        model_name: str,
        base_model_version: str,
        new_samples_count: int,
        id: UUID | None = None,
        status: RetrainingStatus | None = None,
        fine_tuning_job_id: str | None = None,
        new_model_version: str | None = None,
        drift_report_id: UUID | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        config: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize retraining job entity.

        Args:
            trigger_reason: Reason for triggering retraining
            model_name: Name of the model to retrain
            base_model_version: Version of the base model
            new_samples_count: Number of new samples for retraining
            id: Optional entity ID
            status: Job status
            fine_tuning_job_id: ID of the underlying fine-tuning job
            new_model_version: Version of the newly trained model
            drift_report_id: ID of drift report that triggered this (if applicable)
            started_at: When job execution started
            completed_at: When job execution completed
            error_message: Error message if job failed
            config: Training configuration
            metrics: Training metrics/results
            metadata: Additional metadata
        """
        super().__init__(id)
        self._trigger_reason = trigger_reason
        self._model_name = model_name
        self._base_model_version = base_model_version
        self._new_samples_count = new_samples_count
        self._status = status or RetrainingStatus.PENDING
        self._fine_tuning_job_id = fine_tuning_job_id
        self._new_model_version = new_model_version
        self._drift_report_id = drift_report_id
        self._started_at = started_at
        self._completed_at = completed_at
        self._error_message = error_message
        self._config = config or {}
        self._metrics = metrics or {}
        self._metadata = metadata or {}

    @property
    def trigger_reason(self) -> RetrainingTriggerReason:
        """Get the trigger reason."""
        return self._trigger_reason

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self._model_name

    @property
    def base_model_version(self) -> str:
        """Get the base model version."""
        return self._base_model_version

    @property
    def new_samples_count(self) -> int:
        """Get the new samples count."""
        return self._new_samples_count

    @property
    def status(self) -> RetrainingStatus:
        """Get the job status."""
        return self._status

    @property
    def fine_tuning_job_id(self) -> str | None:
        """Get the fine-tuning job ID."""
        return self._fine_tuning_job_id

    @property
    def new_model_version(self) -> str | None:
        """Get the new model version."""
        return self._new_model_version

    @property
    def drift_report_id(self) -> UUID | None:
        """Get the drift report ID."""
        return self._drift_report_id

    @property
    def started_at(self) -> datetime | None:
        """Get the start time."""
        return self._started_at

    @property
    def completed_at(self) -> datetime | None:
        """Get the completion time."""
        return self._completed_at

    @property
    def error_message(self) -> str | None:
        """Get the error message."""
        return self._error_message

    @property
    def config(self) -> dict[str, Any]:
        """Get the training configuration."""
        return self._config.copy()

    @property
    def metrics(self) -> dict[str, Any]:
        """Get the training metrics."""
        return self._metrics.copy()

    @property
    def metadata(self) -> dict[str, Any]:
        """Get additional metadata."""
        return self._metadata.copy()

    def start(self, fine_tuning_job_id: str) -> None:
        """Mark job as started.

        Args:
            fine_tuning_job_id: ID of the fine-tuning job
        """
        self._status = RetrainingStatus.RUNNING
        self._fine_tuning_job_id = fine_tuning_job_id
        self._started_at = datetime.utcnow()
        self._touch()

    def complete(self, new_model_version: str, metrics: dict[str, Any] | None = None) -> None:
        """Mark job as completed.

        Args:
            new_model_version: Version of the newly trained model
            metrics: Training metrics
        """
        self._status = RetrainingStatus.COMPLETED
        self._new_model_version = new_model_version
        self._completed_at = datetime.utcnow()
        if metrics:
            self._metrics = metrics
        self._touch()

    def fail(self, error_message: str) -> None:
        """Mark job as failed.

        Args:
            error_message: Error description
        """
        self._status = RetrainingStatus.FAILED
        self._error_message = error_message
        self._completed_at = datetime.utcnow()
        self._touch()

    def cancel(self) -> None:
        """Cancel the job."""
        if self._status in [RetrainingStatus.PENDING, RetrainingStatus.RUNNING]:
            self._status = RetrainingStatus.CANCELLED
            self._completed_at = datetime.utcnow()
            self._touch()

    def update_config(self, config: dict[str, Any]) -> None:
        """Update training configuration.

        Args:
            config: New configuration to merge
        """
        self._config.update(config)
        self._touch()

    def update_metadata(self, metadata: dict[str, Any]) -> None:
        """Update metadata.

        Args:
            metadata: New metadata to merge
        """
        self._metadata.update(metadata)
        self._touch()

    def get_duration_seconds(self) -> float | None:
        """Get job duration in seconds.

        Returns:
            Duration in seconds, None if not applicable
        """
        if not self._started_at:
            return None

        end_time = self._completed_at or datetime.utcnow()
        duration = (end_time - self._started_at).total_seconds()
        return duration

    def is_terminal_state(self) -> bool:
        """Check if job is in a terminal state.

        Returns:
            True if job is completed, failed, or cancelled
        """
        return self._status in [
            RetrainingStatus.COMPLETED,
            RetrainingStatus.FAILED,
            RetrainingStatus.CANCELLED,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base = super().to_dict()
        base.update(
            {
                "trigger_reason": self._trigger_reason.value,
                "model_name": self._model_name,
                "base_model_version": self._base_model_version,
                "new_samples_count": self._new_samples_count,
                "status": self._status.value,
                "fine_tuning_job_id": self._fine_tuning_job_id,
                "new_model_version": self._new_model_version,
                "drift_report_id": str(self._drift_report_id) if self._drift_report_id else None,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "completed_at": self._completed_at.isoformat() if self._completed_at else None,
                "error_message": self._error_message,
                "config": self._config,
                "metrics": self._metrics,
                "metadata": self._metadata,
                "duration_seconds": self.get_duration_seconds(),
                "is_terminal": self.is_terminal_state(),
            }
        )
        return base
