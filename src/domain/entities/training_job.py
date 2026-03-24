"""Training Job domain entity."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.domain.entities.base import AggregateRoot, utc_now
from src.domain.events.ml_events import RetrainingTriggeredEvent


class TrainingJobStatus(StrEnum):
    """Status of a training job."""

    PENDING = "pending"
    PREPARING_DATA = "preparing_data"
    TRAINING = "training"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingTrigger(StrEnum):
    """Trigger that initiated the training."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATA_DRIFT = "data_drift"
    NEW_DATA_THRESHOLD = "new_data_threshold"


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration for a training job."""

    base_model: str
    dataset_id: UUID
    batch_size: int = 4
    learning_rate: float = 2e-5
    num_epochs: int = 3
    max_seq_length: int = 2048
    lora_rank: int = 8
    lora_alpha: int = 16
    use_rlhf: bool = False
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 100
    eval_steps: int = 500
    save_steps: int = 1000
    fp16: bool = True
    bf16: bool = False


class TrainingJob(AggregateRoot):
    """Training Job aggregate root.

    Represents a training job that fine-tunes a model on a dataset.
    """

    def __init__(
        self,
        id: UUID | None = None,
        name: str = "",
        trigger: TrainingTrigger = TrainingTrigger.MANUAL,
        status: TrainingJobStatus = TrainingJobStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._name = name
        self._trigger = trigger
        self._status = status
        self._config: TrainingConfig | None = None
        self._current_model_id: UUID | None = None
        self._output_model_id: UUID | None = None
        self._mlflow_run_id: str | None = None
        self._prefect_flow_run_id: str | None = None
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._duration_seconds: float | None = None
        self._metrics: dict[str, float] = {}
        self._error_message: str | None = None
        self._logs_path: str | None = None

    @property
    def name(self) -> str:
        """Get job name."""
        return self._name

    @property
    def trigger(self) -> TrainingTrigger:
        """Get training trigger."""
        return self._trigger

    @property
    def status(self) -> TrainingJobStatus:
        """Get job status."""
        return self._status

    @property
    def config(self) -> TrainingConfig | None:
        """Get training configuration."""
        return self._config

    @property
    def current_model_id(self) -> UUID | None:
        """Get current model ID (model being replaced)."""
        return self._current_model_id

    @property
    def output_model_id(self) -> UUID | None:
        """Get output model ID (newly trained model)."""
        return self._output_model_id

    @property
    def mlflow_run_id(self) -> str | None:
        """Get MLflow run ID."""
        return self._mlflow_run_id

    @property
    def duration_seconds(self) -> float | None:
        """Get job duration in seconds."""
        return self._duration_seconds

    @property
    def metrics(self) -> dict[str, float]:
        """Get training metrics."""
        return self._metrics.copy()

    @property
    def is_completed(self) -> bool:
        """Check if job is completed."""
        return self._status == TrainingJobStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if job failed."""
        return self._status == TrainingJobStatus.FAILED

    def configure(
        self,
        config: TrainingConfig,
        current_model_id: UUID | None = None,
    ) -> None:
        """Configure the training job."""
        if self._status != TrainingJobStatus.PENDING:
            raise ValueError("Can only configure pending jobs")

        self._config = config
        self._current_model_id = current_model_id
        self._touch()

    def start(
        self,
        mlflow_run_id: str,
        prefect_flow_run_id: str | None = None,
    ) -> None:
        """Start the training job."""
        if self._status != TrainingJobStatus.PENDING:
            raise ValueError("Can only start pending jobs")

        if not self._config:
            raise ValueError("Training job must be configured before starting")

        self._status = TrainingJobStatus.PREPARING_DATA
        self._mlflow_run_id = mlflow_run_id
        self._prefect_flow_run_id = prefect_flow_run_id
        self._started_at = utc_now()
        self._touch()

        # Emit domain event for automatic retraining
        if self._trigger != TrainingTrigger.MANUAL and self._current_model_id:
            self.add_domain_event(
                RetrainingTriggeredEvent(
                    training_job_id=self.id,
                    trigger_reason=self._trigger.value,
                    current_model_id=self._current_model_id,
                    metrics=self._metrics,
                )
            )

    def start_training_phase(self) -> None:
        """Move to training phase."""
        if self._status != TrainingJobStatus.PREPARING_DATA:
            raise ValueError("Job must be in preparing_data status")

        self._status = TrainingJobStatus.TRAINING
        self._touch()

    def start_evaluation_phase(self) -> None:
        """Move to evaluation phase."""
        if self._status != TrainingJobStatus.TRAINING:
            raise ValueError("Job must be in training status")

        self._status = TrainingJobStatus.EVALUATING
        self._touch()

    def complete(
        self,
        output_model_id: UUID,
        final_metrics: dict[str, float],
        logs_path: str | None = None,
    ) -> None:
        """Complete the training job."""
        if self._status != TrainingJobStatus.EVALUATING:
            raise ValueError("Job must be in evaluating status")

        self._status = TrainingJobStatus.COMPLETED
        self._output_model_id = output_model_id
        self._metrics.update(final_metrics)
        self._completed_at = utc_now()
        self._logs_path = logs_path

        # Calculate duration
        if self._started_at:
            self._duration_seconds = (self._completed_at - self._started_at).total_seconds()

        self._touch()

    def fail(self, error_message: str) -> None:
        """Mark the job as failed."""
        if self._status in [TrainingJobStatus.COMPLETED, TrainingJobStatus.CANCELLED]:
            raise ValueError(f"Cannot fail job with status {self._status}")

        self._status = TrainingJobStatus.FAILED
        self._error_message = error_message
        self._completed_at = utc_now()

        # Calculate duration if started
        if self._started_at:
            self._duration_seconds = (self._completed_at - self._started_at).total_seconds()

        self._touch()

    def cancel(self) -> None:
        """Cancel the training job."""
        if self._status in [TrainingJobStatus.COMPLETED, TrainingJobStatus.FAILED]:
            raise ValueError(f"Cannot cancel job with status {self._status}")

        self._status = TrainingJobStatus.CANCELLED
        self._completed_at = utc_now()

        # Calculate duration if started
        if self._started_at:
            self._duration_seconds = (self._completed_at - self._started_at).total_seconds()

        self._touch()

    def update_metrics(self, metrics: dict[str, float]) -> None:
        """Update training metrics (for real-time updates during training)."""
        self._metrics.update(metrics)
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary."""
        return {
            **super().to_dict(),
            "name": self.name,
            "trigger": self.trigger.value,
            "status": self.status.value,
            "config": self.config.__dict__ if self.config else None,
            "current_model_id": str(self.current_model_id) if self.current_model_id else None,
            "output_model_id": str(self.output_model_id) if self.output_model_id else None,
            "mlflow_run_id": self.mlflow_run_id,
            "prefect_flow_run_id": self._prefect_flow_run_id,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "completed_at": self._completed_at.isoformat() if self._completed_at else None,
            "duration_seconds": self.duration_seconds,
            "metrics": self.metrics,
            "error_message": self._error_message,
            "logs_path": self._logs_path,
        }
