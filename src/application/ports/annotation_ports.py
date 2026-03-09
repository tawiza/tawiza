"""
Annotation Service Ports (Interfaces).

Defines interfaces for annotation services following hexagonal architecture.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class IAnnotationService(ABC):
    """
    Interface for annotation services.

    Provides abstraction for data annotation tools like Label Studio.
    """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if annotation service is available.

        Returns:
            bool: True if healthy
        """
        pass

    @abstractmethod
    async def create_annotation_project(
        self,
        name: str,
        description: str,
        task_type: str,
        label_config: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new annotation project.

        Args:
            name: Project name
            description: Project description
            task_type: Type of annotation (classification, ner, etc.)
            label_config: Optional custom label configuration

        Returns:
            dict: Created project info with ID
        """
        pass

    @abstractmethod
    async def get_project(self, project_id: str) -> dict[str, Any]:
        """
        Get annotation project details.

        Args:
            project_id: Project identifier

        Returns:
            dict: Project details
        """
        pass

    @abstractmethod
    async def list_projects(self) -> list[dict[str, Any]]:
        """
        List all annotation projects.

        Returns:
            list: List of projects
        """
        pass

    @abstractmethod
    async def import_data_for_annotation(
        self,
        project_id: str,
        data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Import data into annotation project for labeling.

        Args:
            project_id: Project identifier
            data: List of data items to annotate

        Returns:
            dict: Import result with task count
        """
        pass

    @abstractmethod
    async def export_annotations(
        self,
        project_id: str,
        export_format: str = "JSON",
    ) -> list[dict[str, Any]]:
        """
        Export completed annotations.

        Args:
            project_id: Project identifier
            export_format: Export format (JSON, CSV, etc.)

        Returns:
            list: Exported annotations
        """
        pass

    @abstractmethod
    async def get_project_statistics(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """
        Get annotation project statistics.

        Args:
            project_id: Project identifier

        Returns:
            dict: Statistics (total tasks, annotated, pending, etc.)
        """
        pass

    @abstractmethod
    async def delete_project(self, project_id: str) -> bool:
        """
        Delete annotation project.

        Args:
            project_id: Project identifier

        Returns:
            bool: True if deleted successfully
        """
        pass

    @abstractmethod
    async def prepare_dataset_for_annotation(
        self,
        dataset_id: UUID,
        sample_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Prepare a dataset for annotation.

        Creates annotation project and imports data.

        Args:
            dataset_id: Dataset UUID from database
            sample_size: Optional sample size (for large datasets)

        Returns:
            dict: Project info with import status
        """
        pass

    @abstractmethod
    async def sync_annotations_to_dataset(
        self,
        project_id: str,
        dataset_id: UUID,
    ) -> dict[str, Any]:
        """
        Sync completed annotations back to dataset.

        Exports annotations and updates dataset in database.

        Args:
            project_id: Annotation project ID
            dataset_id: Dataset UUID

        Returns:
            dict: Sync result with counts
        """
        pass


class AnnotationError(Exception):
    """Base exception for annotation errors."""
    pass


class ProjectNotFoundError(AnnotationError):
    """Raised when annotation project is not found."""
    pass


class ImportError(AnnotationError):
    """Raised when data import fails."""
    pass


class ExportError(AnnotationError):
    """Raised when annotation export fails."""
    pass
