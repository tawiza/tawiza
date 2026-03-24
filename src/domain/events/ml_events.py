"""Machine Learning domain events."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ModelTrainedEvent(DomainEvent):
    """Event emitted when a model completes training."""

    model_name: str
    version: str
    accuracy: float
    mlflow_run_id: str | None

    def __init__(
        self,
        model_id: UUID,
        model_name: str,
        version: str,
        accuracy: float,
        mlflow_run_id: str | None = None,
    ) -> None:
        super().__init__(aggregate_id=model_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "accuracy", accuracy)
        object.__setattr__(self, "mlflow_run_id", mlflow_run_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "accuracy": self.accuracy,
            "mlflow_run_id": self.mlflow_run_id,
        }


@dataclass(frozen=True)
class ModelDeployedEvent(DomainEvent):
    """Event emitted when a model is deployed."""

    model_name: str
    version: str
    deployment_strategy: str
    traffic_percentage: int

    def __init__(
        self,
        model_id: UUID,
        model_name: str,
        version: str,
        deployment_strategy: str,
        traffic_percentage: int,
    ) -> None:
        super().__init__(aggregate_id=model_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "deployment_strategy", deployment_strategy)
        object.__setattr__(self, "traffic_percentage", traffic_percentage)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "deployment_strategy": self.deployment_strategy,
            "traffic_percentage": self.traffic_percentage,
        }


@dataclass(frozen=True)
class ModelRetiredEvent(DomainEvent):
    """Event emitted when a model is retired."""

    model_name: str
    version: str
    reason: str

    def __init__(
        self,
        model_id: UUID,
        model_name: str,
        version: str,
        reason: str = "",
    ) -> None:
        super().__init__(aggregate_id=model_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "reason", reason)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PredictionRequestedEvent(DomainEvent):
    """Event emitted when a prediction is requested."""

    model_id: UUID
    input_data: dict[str, Any]

    def __init__(
        self,
        prediction_id: UUID,
        model_id: UUID,
        input_data: dict[str, Any],
    ) -> None:
        super().__init__(aggregate_id=prediction_id)
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "input_data", input_data)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "model_id": str(self.model_id),
            "input_data": self.input_data,
        }


@dataclass(frozen=True)
class FeedbackReceivedEvent(DomainEvent):
    """Event emitted when feedback is received on a prediction."""

    prediction_id: UUID
    feedback_type: str  # "positive", "negative", "correction"
    feedback_value: Any

    def __init__(
        self,
        feedback_id: UUID,
        prediction_id: UUID,
        feedback_type: str,
        feedback_value: Any,
    ) -> None:
        super().__init__(aggregate_id=feedback_id)
        object.__setattr__(self, "prediction_id", prediction_id)
        object.__setattr__(self, "feedback_type", feedback_type)
        object.__setattr__(self, "feedback_value", feedback_value)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "prediction_id": str(self.prediction_id),
            "feedback_type": self.feedback_type,
            "feedback_value": self.feedback_value,
        }


@dataclass(frozen=True)
class DatasetCreatedEvent(DomainEvent):
    """Event emitted when a new dataset is created."""

    dataset_name: str
    size: int
    dataset_type: str  # "training", "validation", "test"

    def __init__(
        self,
        dataset_id: UUID,
        dataset_name: str,
        size: int,
        dataset_type: str,
    ) -> None:
        super().__init__(aggregate_id=dataset_id)
        object.__setattr__(self, "dataset_name", dataset_name)
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "dataset_type", dataset_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "dataset_name": self.dataset_name,
            "size": self.size,
            "dataset_type": self.dataset_type,
        }


@dataclass(frozen=True)
class RetrainingTriggeredEvent(DomainEvent):
    """Event emitted when automatic retraining is triggered."""

    trigger_reason: str  # "scheduled", "performance_degradation", "data_drift"
    current_model_id: UUID
    metrics: dict[str, float]

    def __init__(
        self,
        training_job_id: UUID,
        trigger_reason: str,
        current_model_id: UUID,
        metrics: dict[str, float],
    ) -> None:
        super().__init__(aggregate_id=training_job_id)
        object.__setattr__(self, "trigger_reason", trigger_reason)
        object.__setattr__(self, "current_model_id", current_model_id)
        object.__setattr__(self, "metrics", metrics)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "trigger_reason": self.trigger_reason,
            "current_model_id": str(self.current_model_id),
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class DriftDetectedEvent(DomainEvent):
    """Event emitted when model drift is detected."""

    model_name: str
    model_version: str
    drift_type: str  # "data_drift", "concept_drift", "prediction_drift", "performance_drift"
    drift_score: float
    severity: str  # "low", "medium", "high", "critical"
    metric_name: str
    current_value: float
    baseline_value: float

    def __init__(
        self,
        drift_report_id: UUID,
        model_name: str,
        model_version: str,
        drift_type: str,
        drift_score: float,
        severity: str,
        metric_name: str,
        current_value: float,
        baseline_value: float,
    ) -> None:
        super().__init__(aggregate_id=drift_report_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "drift_type", drift_type)
        object.__setattr__(self, "drift_score", drift_score)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "metric_name", metric_name)
        object.__setattr__(self, "current_value", current_value)
        object.__setattr__(self, "baseline_value", baseline_value)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "drift_type": self.drift_type,
            "drift_score": self.drift_score,
            "severity": self.severity,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
        }


@dataclass(frozen=True)
class SamplesSelectedForLabelingEvent(DomainEvent):
    """Event emitted when samples are selected for labeling via active learning."""

    strategy_type: str  # "uncertainty", "margin", "entropy", "diversity"
    sample_count: int
    model_name: str
    model_version: str
    average_score: float

    def __init__(
        self,
        selection_id: UUID,
        strategy_type: str,
        sample_count: int,
        model_name: str,
        model_version: str,
        average_score: float,
    ) -> None:
        super().__init__(aggregate_id=selection_id)
        object.__setattr__(self, "strategy_type", strategy_type)
        object.__setattr__(self, "sample_count", sample_count)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "average_score", average_score)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            **super().to_dict(),
            "strategy_type": self.strategy_type,
            "sample_count": self.sample_count,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "average_score": self.average_score,
        }
