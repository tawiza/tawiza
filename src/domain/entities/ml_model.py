"""ML Model domain entity."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any
from uuid import UUID

from src.domain.entities.base import AggregateRoot, utc_now
from src.domain.events.ml_events import (
    ModelDeployedEvent,
    ModelRetiredEvent,
    ModelTrainedEvent,
)


class ModelStatus(StrEnum):
    """Status of an ML model."""

    DRAFT = "draft"
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    RETIRED = "retired"


class DeploymentStrategy(StrEnum):
    """Deployment strategy for models."""

    DIRECT = "direct"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    A_B_TEST = "a_b_test"


@dataclass(frozen=True)
class ModelMetrics:
    """Metrics for a trained model."""

    accuracy: float
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    loss: float | None = None
    perplexity: float | None = None
    custom_metrics: dict[str, float] | None = None

    def __post_init__(self) -> None:
        """Validate metrics."""
        if not 0 <= self.accuracy <= 1:
            raise ValueError("Accuracy must be between 0 and 1")


class MLModel(AggregateRoot):
    """ML Model aggregate root.

    Represents a machine learning model in the system with its lifecycle,
    metrics, and deployment information.
    """

    def __init__(
        self,
        id: UUID | None = None,
        name: str = "",
        version: str = "0.1.0",
        base_model: str = "",
        description: str = "",
        status: ModelStatus = ModelStatus.DRAFT,
    ) -> None:
        super().__init__(id)
        self._name = name
        self._version = version
        self._base_model = base_model
        self._description = description
        self._status = status
        self._metrics: ModelMetrics | None = None
        self._mlflow_run_id: str | None = None
        self._model_path: str | None = None
        self._deployment_strategy: DeploymentStrategy | None = None
        self._traffic_percentage: int = 0
        self._deployed_at: datetime | None = None
        self._retired_at: datetime | None = None
        self._hyperparameters: dict[str, Any] = {}
        self._tags: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Get model name."""
        return self._name

    @property
    def version(self) -> str:
        """Get model version."""
        return self._version

    @property
    def base_model(self) -> str:
        """Get base model (e.g., 'meta-llama/Llama-2-7b-chat-hf')."""
        return self._base_model

    @property
    def description(self) -> str:
        """Get model description."""
        return self._description

    @property
    def status(self) -> ModelStatus:
        """Get model status."""
        return self._status

    @property
    def metrics(self) -> ModelMetrics | None:
        """Get model metrics."""
        return self._metrics

    @property
    def mlflow_run_id(self) -> str | None:
        """Get MLflow run ID."""
        return self._mlflow_run_id

    @property
    def model_path(self) -> str | None:
        """Get model storage path."""
        return self._model_path

    @property
    def deployment_strategy(self) -> DeploymentStrategy | None:
        """Get deployment strategy."""
        return self._deployment_strategy

    @property
    def traffic_percentage(self) -> int:
        """Get traffic percentage for canary deployments."""
        return self._traffic_percentage

    @property
    def is_deployed(self) -> bool:
        """Check if model is deployed."""
        return self._status == ModelStatus.DEPLOYED

    @property
    def hyperparameters(self) -> dict[str, Any]:
        """Get model hyperparameters."""
        return self._hyperparameters.copy()

    def start_training(self, mlflow_run_id: str) -> None:
        """Start model training."""
        if self._status not in [ModelStatus.DRAFT, ModelStatus.FAILED]:
            raise ValueError(f"Cannot start training from status {self._status}")

        self._status = ModelStatus.TRAINING
        self._mlflow_run_id = mlflow_run_id
        self._touch()

    def complete_training(
        self,
        metrics: ModelMetrics,
        model_path: str,
        hyperparameters: dict[str, Any],
    ) -> None:
        """Complete model training."""
        if self._status != ModelStatus.TRAINING:
            raise ValueError("Model is not in training status")

        self._status = ModelStatus.TRAINED
        self._metrics = metrics
        self._model_path = model_path
        self._hyperparameters = hyperparameters
        self._touch()

        # Emit domain event
        self.add_domain_event(
            ModelTrainedEvent(
                model_id=self.id,
                model_name=self.name,
                version=self.version,
                accuracy=metrics.accuracy,
                mlflow_run_id=self._mlflow_run_id,
            )
        )

    def fail_training(self, error_message: str) -> None:
        """Mark training as failed."""
        if self._status != ModelStatus.TRAINING:
            raise ValueError("Model is not in training status")

        self._status = ModelStatus.FAILED
        self._tags["error_message"] = error_message
        self._touch()

    def validate(self) -> None:
        """Start model validation."""
        if self._status != ModelStatus.TRAINED:
            raise ValueError("Model must be trained before validation")

        self._status = ModelStatus.VALIDATING
        self._touch()

    def complete_validation(self, is_valid: bool) -> None:
        """Complete model validation."""
        if self._status != ModelStatus.VALIDATING:
            raise ValueError("Model is not in validating status")

        if is_valid:
            self._status = ModelStatus.VALIDATED
        else:
            self._status = ModelStatus.FAILED
            self._tags["validation_failed"] = "true"

        self._touch()

    def deploy(
        self,
        strategy: DeploymentStrategy = DeploymentStrategy.DIRECT,
        traffic_percentage: int = 100,
    ) -> None:
        """Deploy the model."""
        if self._status != ModelStatus.VALIDATED:
            raise ValueError("Model must be validated before deployment")

        if not 0 <= traffic_percentage <= 100:
            raise ValueError("Traffic percentage must be between 0 and 100")

        self._status = ModelStatus.DEPLOYING
        self._deployment_strategy = strategy
        self._traffic_percentage = traffic_percentage
        self._touch()

    def complete_deployment(self) -> None:
        """Complete model deployment."""
        if self._status != ModelStatus.DEPLOYING:
            raise ValueError("Model is not in deploying status")

        self._status = ModelStatus.DEPLOYED
        self._deployed_at = utc_now()
        self._touch()

        # Emit domain event
        self.add_domain_event(
            ModelDeployedEvent(
                model_id=self.id,
                model_name=self.name,
                version=self.version,
                deployment_strategy=self._deployment_strategy.value if self._deployment_strategy else "",
                traffic_percentage=self._traffic_percentage,
            )
        )

    def update_traffic(self, new_percentage: int) -> None:
        """Update traffic percentage for canary deployment."""
        if not self.is_deployed:
            raise ValueError("Model must be deployed to update traffic")

        if not 0 <= new_percentage <= 100:
            raise ValueError("Traffic percentage must be between 0 and 100")

        self._traffic_percentage = new_percentage
        self._touch()

    def retire(self, reason: str = "") -> None:
        """Retire the model."""
        if not self.is_deployed:
            raise ValueError("Only deployed models can be retired")

        self._status = ModelStatus.RETIRED
        self._retired_at = utc_now()
        self._traffic_percentage = 0
        if reason:
            self._tags["retirement_reason"] = reason
        self._touch()

        # Emit domain event
        self.add_domain_event(
            ModelRetiredEvent(
                model_id=self.id,
                model_name=self.name,
                version=self.version,
                reason=reason,
            )
        )

    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the model."""
        self._tags[key] = value
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            **super().to_dict(),
            "name": self.name,
            "version": self.version,
            "base_model": self.base_model,
            "description": self.description,
            "status": self.status.value,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "mlflow_run_id": self.mlflow_run_id,
            "model_path": self.model_path,
            "deployment_strategy": self.deployment_strategy.value if self.deployment_strategy else None,
            "traffic_percentage": self.traffic_percentage,
            "deployed_at": self._deployed_at.isoformat() if self._deployed_at else None,
            "retired_at": self._retired_at.isoformat() if self._retired_at else None,
            "hyperparameters": self.hyperparameters,
            "tags": self._tags.copy(),
        }
