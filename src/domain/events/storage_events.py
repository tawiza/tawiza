"""Domain events for model storage and versioning."""

from dataclasses import dataclass
from typing import Any

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ModelVersionCreatedEvent(DomainEvent):
    """Event emitted when a new model version is created."""

    model_name: str
    version: str
    base_model: str
    mlflow_run_id: str | None
    storage_path: str
    accuracy: float | None
    training_examples: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "base_model": self.base_model,
            "mlflow_run_id": self.mlflow_run_id,
            "storage_path": self.storage_path,
            "accuracy": self.accuracy,
            "training_examples": self.training_examples,
        }


@dataclass(frozen=True)
class ModelVersionDeletedEvent(DomainEvent):
    """Event emitted when a model version is deleted."""

    model_name: str
    version: str
    deleted_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "deleted_by": self.deleted_by,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ModelRolledBackEvent(DomainEvent):
    """Event emitted when a model is rolled back to a previous version."""

    model_name: str
    from_version: str
    to_version: str
    reason: str
    rolled_back_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reason": self.reason,
            "rolled_back_by": self.rolled_back_by,
        }


@dataclass(frozen=True)
class ModelVersionActivatedEvent(DomainEvent):
    """Event emitted when a model version is activated (set as current)."""

    model_name: str
    version: str
    previous_active_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "previous_active_version": self.previous_active_version,
        }


@dataclass(frozen=True)
class ModelVersionArchivedEvent(DomainEvent):
    """Event emitted when a model version is archived."""

    model_name: str
    version: str
    archive_reason: str
    archived_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "archive_reason": self.archive_reason,
            "archived_by": self.archived_by,
        }


@dataclass(frozen=True)
class ModelStorageFailedEvent(DomainEvent):
    """Event emitted when model storage fails."""

    model_name: str
    version: str
    error_message: str
    error_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            **super().to_dict(),
            "model_name": self.model_name,
            "version": self.version,
            "error_message": self.error_message,
            "error_type": self.error_type,
        }
