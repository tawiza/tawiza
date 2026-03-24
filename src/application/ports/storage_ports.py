"""Port interfaces for model storage operations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.domain.entities.model_version import VersionMetadata
from src.domain.value_objects.version import AutoIncrementVersion


class IModelStorageService(ABC):
    """Port interface for model storage in S3-compatible storage (MinIO).

    This interface abstracts model storage operations, allowing different
    implementations (MinIO, S3, local filesystem, etc.).
    """

    @abstractmethod
    async def initialize_bucket(self) -> None:
        """Initialize storage bucket if it doesn't exist.

        Creates the bucket and sets up necessary configurations.

        Raises:
            StorageError: If bucket initialization fails
        """
        pass

    @abstractmethod
    async def store_model(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        modelfile_content: str,
        metadata: VersionMetadata,
    ) -> str:
        """Store a model version in MinIO.

        Args:
            model_name: Name of the model (e.g., "qwen3-coder-finetuned")
            version: Version number
            modelfile_content: Content of the Ollama Modelfile
            metadata: Version metadata (metrics, hyperparameters, etc.)

        Returns:
            Storage path in MinIO (e.g., "ollama-models/model-name/v1/")

        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    async def retrieve_model(
        self,
        model_name: str,
        version: AutoIncrementVersion | None = None,
    ) -> tuple[str, VersionMetadata]:
        """Retrieve a model version from MinIO.

        Args:
            model_name: Name of the model
            version: Version number (if None, retrieves latest version)

        Returns:
            Tuple of (modelfile_content, metadata)

        Raises:
            ModelNotFoundError: If model version doesn't exist
            StorageError: If retrieval fails
        """
        pass

    @abstractmethod
    async def list_versions(
        self,
        model_name: str,
        include_inactive: bool = False,
    ) -> list[VersionMetadata]:
        """List all versions of a model.

        Args:
            model_name: Name of the model
            include_inactive: Include inactive/archived versions

        Returns:
            List of version metadata, sorted by version (newest first)

        Raises:
            StorageError: If listing fails
        """
        pass

    @abstractmethod
    async def get_latest_version(
        self,
        model_name: str,
    ) -> AutoIncrementVersion | None:
        """Get the latest version number for a model.

        Args:
            model_name: Name of the model

        Returns:
            Latest version number, or None if no versions exist

        Raises:
            StorageError: If operation fails
        """
        pass

    @abstractmethod
    async def delete_version(
        self,
        model_name: str,
        version: AutoIncrementVersion,
    ) -> bool:
        """Delete a specific model version.

        Args:
            model_name: Name of the model
            version: Version to delete

        Returns:
            True if deleted successfully

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If deletion fails
        """
        pass

    @abstractmethod
    async def version_exists(
        self,
        model_name: str,
        version: AutoIncrementVersion,
    ) -> bool:
        """Check if a model version exists.

        Args:
            model_name: Name of the model
            version: Version to check

        Returns:
            True if version exists

        Raises:
            StorageError: If check fails
        """
        pass

    @abstractmethod
    async def get_version_metadata(
        self,
        model_name: str,
        version: AutoIncrementVersion,
    ) -> VersionMetadata:
        """Get metadata for a specific version.

        Args:
            model_name: Name of the model
            version: Version number

        Returns:
            Version metadata

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If retrieval fails
        """
        pass

    @abstractmethod
    async def update_version_metadata(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        metadata: VersionMetadata,
    ) -> None:
        """Update metadata for a specific version.

        Args:
            model_name: Name of the model
            version: Version number
            metadata: Updated metadata

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If update fails
        """
        pass

    @abstractmethod
    async def set_active_version(
        self,
        model_name: str,
        version: AutoIncrementVersion,
    ) -> None:
        """Set a version as the active/current version.

        This deactivates all other versions of the same model.

        Args:
            model_name: Name of the model
            version: Version to activate

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If operation fails
        """
        pass

    @abstractmethod
    async def get_active_version(
        self,
        model_name: str,
    ) -> VersionMetadata | None:
        """Get the currently active version of a model.

        Args:
            model_name: Name of the model

        Returns:
            Metadata of active version, or None if no active version

        Raises:
            StorageError: If operation fails
        """
        pass

    @abstractmethod
    async def get_storage_stats(
        self,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Get storage statistics.

        Args:
            model_name: Specific model (if None, returns stats for all models)

        Returns:
            Dictionary with storage statistics (total size, version count, etc.)

        Raises:
            StorageError: If operation fails
        """
        pass

    @abstractmethod
    async def export_version_to_file(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        export_path: Path,
    ) -> Path:
        """Export a model version to a local file.

        Args:
            model_name: Name of the model
            version: Version to export
            export_path: Local path to export to

        Returns:
            Path to exported file

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If export fails
        """
        pass


class IModelVersioningService(ABC):
    """Port interface for model versioning logic.

    This interface handles version number management, rollbacks,
    and version lifecycle operations.
    """

    @abstractmethod
    async def create_new_version(
        self,
        model_name: str,
        base_model: str,
        modelfile_content: str,
        metadata: dict[str, Any],
    ) -> VersionMetadata:
        """Create a new version of a model.

        Automatically increments version number.

        Args:
            model_name: Name of the model
            base_model: Base model used
            modelfile_content: Modelfile content
            metadata: Additional metadata (metrics, hyperparameters, etc.)

        Returns:
            Created version metadata

        Raises:
            VersioningError: If version creation fails
        """
        pass

    @abstractmethod
    async def rollback_to_version(
        self,
        model_name: str,
        target_version: AutoIncrementVersion,
        reason: str = "",
    ) -> VersionMetadata:
        """Rollback a model to a previous version.

        This creates a new version based on the target version,
        preserving history.

        Args:
            model_name: Name of the model
            target_version: Version to rollback to
            reason: Reason for rollback

        Returns:
            New version metadata (copy of target version)

        Raises:
            ModelNotFoundError: If target version doesn't exist
            VersioningError: If rollback fails
        """
        pass

    @abstractmethod
    async def compare_versions(
        self,
        model_name: str,
        version_a: AutoIncrementVersion,
        version_b: AutoIncrementVersion,
    ) -> dict[str, Any]:
        """Compare two versions of a model.

        Args:
            model_name: Name of the model
            version_a: First version
            version_b: Second version

        Returns:
            Comparison results (metrics diff, metadata diff, etc.)

        Raises:
            ModelNotFoundError: If any version doesn't exist
            VersioningError: If comparison fails
        """
        pass

    @abstractmethod
    async def get_version_history(
        self,
        model_name: str,
        limit: int | None = None,
    ) -> list[VersionMetadata]:
        """Get version history for a model.

        Args:
            model_name: Name of the model
            limit: Maximum number of versions to return

        Returns:
            List of version metadata, sorted by version (newest first)

        Raises:
            VersioningError: If operation fails
        """
        pass

    @abstractmethod
    async def tag_version(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        tag_key: str,
        tag_value: str,
    ) -> None:
        """Add a tag to a model version.

        Args:
            model_name: Name of the model
            version: Version to tag
            tag_key: Tag key
            tag_value: Tag value

        Raises:
            ModelNotFoundError: If version doesn't exist
            VersioningError: If tagging fails
        """
        pass

    @abstractmethod
    async def promote_version(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        environment: str,
    ) -> None:
        """Promote a version to an environment (dev, staging, production).

        Args:
            model_name: Name of the model
            version: Version to promote
            environment: Target environment

        Raises:
            ModelNotFoundError: If version doesn't exist
            VersioningError: If promotion fails
        """
        pass
