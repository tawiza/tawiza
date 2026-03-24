"""Dataset domain entity."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from src.domain.entities.base import AggregateRoot
from src.domain.events.ml_events import DatasetCreatedEvent


class DatasetType(StrEnum):
    """Type of dataset."""

    TRAINING = "training"
    VALIDATION = "validation"
    TEST = "test"
    PRODUCTION = "production"


class DatasetStatus(StrEnum):
    """Status of dataset processing."""

    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    ANNOTATING = "annotating"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class DatasetMetadata:
    """Metadata for a dataset."""

    size: int  # Number of samples
    source: str  # Source of data (e.g., "user_interactions", "manual_upload")
    format: str  # Format (e.g., "jsonl", "parquet", "csv")
    schema_version: str = "1.0"
    annotations_required: bool = True
    annotations_completed: int = 0

    def annotation_progress(self) -> float:
        """Calculate annotation progress percentage."""
        if not self.annotations_required or self.size == 0:
            return 100.0
        return (self.annotations_completed / self.size) * 100


class Dataset(AggregateRoot):
    """Dataset aggregate root.

    Represents a dataset used for training, validation, or testing ML models.
    """

    def __init__(
        self,
        id: UUID | None = None,
        name: str = "",
        dataset_type: DatasetType = DatasetType.TRAINING,
        status: DatasetStatus = DatasetStatus.DRAFT,
    ) -> None:
        super().__init__(id)
        self._name = name
        self._dataset_type = dataset_type
        self._status = status
        self._metadata: DatasetMetadata | None = None
        self._storage_path: str | None = None
        self._label_studio_project_id: int | None = None
        self._dvc_path: str | None = None
        self._tags: dict[str, str] = {}
        self._statistics: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Get dataset name."""
        return self._name

    @property
    def dataset_type(self) -> DatasetType:
        """Get dataset type."""
        return self._dataset_type

    @property
    def status(self) -> DatasetStatus:
        """Get dataset status."""
        return self._status

    @property
    def metadata(self) -> DatasetMetadata | None:
        """Get dataset metadata."""
        return self._metadata

    @property
    def storage_path(self) -> str | None:
        """Get storage path."""
        return self._storage_path

    @property
    def label_studio_project_id(self) -> int | None:
        """Get Label Studio project ID."""
        return self._label_studio_project_id

    @property
    def dvc_path(self) -> str | None:
        """Get DVC path."""
        return self._dvc_path

    @property
    def is_ready(self) -> bool:
        """Check if dataset is ready for use."""
        return self._status == DatasetStatus.READY

    def create(
        self,
        metadata: DatasetMetadata,
        storage_path: str,
        dvc_path: str | None = None,
    ) -> None:
        """Create the dataset."""
        if self._status != DatasetStatus.DRAFT:
            raise ValueError("Can only create datasets in draft status")

        self._metadata = metadata
        self._storage_path = storage_path
        self._dvc_path = dvc_path
        self._status = DatasetStatus.PROCESSING
        self._touch()

    def complete_processing(self, statistics: dict[str, Any]) -> None:
        """Complete dataset processing."""
        if self._status != DatasetStatus.PROCESSING:
            raise ValueError("Dataset is not in processing status")

        self._statistics = statistics

        # If annotations are not required, mark as ready
        if self._metadata and not self._metadata.annotations_required:
            self._status = DatasetStatus.READY
        else:
            self._status = DatasetStatus.ANNOTATING

        self._touch()

        # Emit domain event
        if self._metadata:
            self.add_domain_event(
                DatasetCreatedEvent(
                    dataset_id=self.id,
                    dataset_name=self.name,
                    size=self._metadata.size,
                    dataset_type=self.dataset_type.value,
                )
            )

    def link_label_studio_project(self, project_id: int) -> None:
        """Link dataset to Label Studio project."""
        self._label_studio_project_id = project_id
        self._touch()

    def update_annotation_progress(self, annotations_completed: int) -> None:
        """Update annotation progress."""
        if not self._metadata:
            raise ValueError("Dataset metadata not set")

        if annotations_completed > self._metadata.size:
            raise ValueError("Annotations completed cannot exceed dataset size")

        # Create new metadata with updated count
        self._metadata = DatasetMetadata(
            size=self._metadata.size,
            source=self._metadata.source,
            format=self._metadata.format,
            schema_version=self._metadata.schema_version,
            annotations_required=self._metadata.annotations_required,
            annotations_completed=annotations_completed,
        )

        # Mark as ready if all annotations completed
        if annotations_completed == self._metadata.size:
            self._status = DatasetStatus.READY

        self._touch()

    def mark_ready(self) -> None:
        """Mark dataset as ready."""
        if self._status not in [DatasetStatus.PROCESSING, DatasetStatus.ANNOTATING]:
            raise ValueError(f"Cannot mark dataset as ready from status {self._status}")

        self._status = DatasetStatus.READY
        self._touch()

    def fail(self, error_message: str) -> None:
        """Mark dataset processing as failed."""
        self._status = DatasetStatus.FAILED
        self._tags["error_message"] = error_message
        self._touch()

    def archive(self) -> None:
        """Archive the dataset."""
        self._status = DatasetStatus.ARCHIVED
        self._touch()

    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the dataset."""
        self._tags[key] = value
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        """Convert dataset to dictionary."""
        return {
            **super().to_dict(),
            "name": self.name,
            "dataset_type": self.dataset_type.value,
            "status": self.status.value,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "storage_path": self.storage_path,
            "label_studio_project_id": self.label_studio_project_id,
            "dvc_path": self.dvc_path,
            "statistics": self._statistics.copy(),
            "tags": self._tags.copy(),
        }
