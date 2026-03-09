"""Model version domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.value_objects.version import AutoIncrementVersion


@dataclass
class VersionMetadata:
    """Metadata for a model version."""

    # Version information
    model_name: str
    version: AutoIncrementVersion
    base_model: str

    # MLflow tracking
    mlflow_run_id: str | None = None
    mlflow_experiment_id: str | None = None

    # Performance metrics
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    loss: float | None = None
    perplexity: float | None = None

    # Training information
    training_examples: int = 0
    task_type: str = "classification"
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    # Storage information
    storage_path: str | None = None  # Path in MinIO
    modelfile_size_bytes: int = 0
    checksum: str | None = None  # SHA256 hash

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    trained_at: datetime | None = None

    # Tags and labels
    tags: dict[str, str] = field(default_factory=dict)
    is_active: bool = True  # Whether this version is currently deployed
    is_baseline: bool = False  # Whether this is the baseline version

    # Comments and notes
    description: str | None = None
    training_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "model_name": self.model_name,
            "version": str(self.version),
            "base_model": self.base_model,
            "mlflow_run_id": self.mlflow_run_id,
            "mlflow_experiment_id": self.mlflow_experiment_id,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "loss": self.loss,
            "perplexity": self.perplexity,
            "training_examples": self.training_examples,
            "task_type": self.task_type,
            "hyperparameters": self.hyperparameters,
            "storage_path": self.storage_path,
            "modelfile_size_bytes": self.modelfile_size_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "tags": self.tags,
            "is_active": self.is_active,
            "is_baseline": self.is_baseline,
            "description": self.description,
            "training_notes": self.training_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionMetadata":
        """Create from dictionary."""
        # Parse version
        version = AutoIncrementVersion.from_string(data["version"])

        # Parse timestamps
        created_at = (
            datetime.fromisoformat(data["created_at"])
            if isinstance(data.get("created_at"), str)
            else data.get("created_at", datetime.utcnow())
        )

        trained_at = None
        if data.get("trained_at"):
            trained_at = (
                datetime.fromisoformat(data["trained_at"])
                if isinstance(data["trained_at"], str)
                else data["trained_at"]
            )

        return cls(
            model_name=data["model_name"],
            version=version,
            base_model=data["base_model"],
            mlflow_run_id=data.get("mlflow_run_id"),
            mlflow_experiment_id=data.get("mlflow_experiment_id"),
            accuracy=data.get("accuracy"),
            precision=data.get("precision"),
            recall=data.get("recall"),
            f1_score=data.get("f1_score"),
            loss=data.get("loss"),
            perplexity=data.get("perplexity"),
            training_examples=data.get("training_examples", 0),
            task_type=data.get("task_type", "classification"),
            hyperparameters=data.get("hyperparameters", {}),
            storage_path=data.get("storage_path"),
            modelfile_size_bytes=data.get("modelfile_size_bytes", 0),
            checksum=data.get("checksum"),
            created_at=created_at,
            trained_at=trained_at,
            tags=data.get("tags", {}),
            is_active=data.get("is_active", True),
            is_baseline=data.get("is_baseline", False),
            description=data.get("description"),
            training_notes=data.get("training_notes"),
        )


@dataclass
class ModelVersionSnapshot:
    """Snapshot of a model version for rollback purposes."""

    id: UUID = field(default_factory=uuid4)
    model_name: str = ""
    version: AutoIncrementVersion = field(default_factory=lambda: AutoIncrementVersion(1))
    metadata: VersionMetadata = field(default_factory=lambda: VersionMetadata("", AutoIncrementVersion(1), ""))
    modelfile_content: str = ""
    snapshot_created_at: datetime = field(default_factory=datetime.utcnow)
    snapshot_reason: str = "backup"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "model_name": self.model_name,
            "version": str(self.version),
            "metadata": self.metadata.to_dict(),
            "modelfile_content": self.modelfile_content,
            "snapshot_created_at": self.snapshot_created_at.isoformat(),
            "snapshot_reason": self.snapshot_reason,
        }
