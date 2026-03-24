"""MinIO storage adapter for Ollama models.

Security: Includes path traversal protection (VULN-005)
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from loguru import logger
from minio import Minio
from minio.error import S3Error

from src.application.ports.storage_ports import IModelStorageService
from src.domain.entities.model_version import VersionMetadata
from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.security.validators import validate_model_name, validate_path


class StorageError(Exception):
    """Base exception for storage operations."""

    pass


class ModelNotFoundError(StorageError):
    """Raised when a model version is not found."""

    pass


class MinIOStorageAdapter(IModelStorageService):
    """MinIO adapter for storing Ollama model versions.

    Storage structure in MinIO:
    bucket/
      └── {model_name}/
          ├── v1/
          │   ├── modelfile
          │   └── metadata.json
          ├── v2/
          │   ├── modelfile
          │   └── metadata.json
          └── ...
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
    ):
        """Initialize MinIO storage adapter.

        Args:
            endpoint: MinIO endpoint (e.g., "localhost:9000")
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket_name: Bucket name for storing models
            secure: Use HTTPS (default: False for local dev)
        """
        self.endpoint = endpoint
        self.bucket_name = bucket_name

        # Initialize MinIO client
        try:
            self.client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
            logger.info(f"MinIO client initialized: {endpoint}/{bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise StorageError(f"MinIO initialization failed: {e}")

    async def initialize_bucket(self) -> None:
        """Initialize storage bucket if it doesn't exist."""
        try:
            # Check if bucket exists
            if not self.client.bucket_exists(self.bucket_name):
                # Create bucket
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: {self.bucket_name}")
            else:
                logger.info(f"MinIO bucket already exists: {self.bucket_name}")

        except S3Error as e:
            logger.error(f"Failed to initialize bucket: {e}")
            raise StorageError(f"Bucket initialization failed: {e}")

    def _get_object_path(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        filename: str,
    ) -> str:
        """Generate object path in MinIO.

        Security: Validates inputs to prevent path traversal (VULN-005)

        Args:
            model_name: Model name
            version: Version number
            filename: File name (e.g., "modelfile", "metadata.json")

        Returns:
            Object path (e.g., "model-name/v1/modelfile")

        Raises:
            ValueError: If inputs contain invalid characters
        """
        # SECURITY FIX (VULN-005): Validate model_name to prevent path traversal
        try:
            validated_model_name = validate_model_name(model_name)
        except ValueError as e:
            raise ValueError(f"Invalid model name for storage path: {e}")

        # SECURITY FIX (VULN-005): Validate filename to prevent path traversal
        # Filename should not contain path separators or parent directory references
        if not filename:
            raise ValueError("Filename cannot be empty")

        if "/" in filename or "\\" in filename:
            raise ValueError("Filename cannot contain path separators")

        if ".." in filename:
            raise ValueError("Filename cannot contain parent directory references")

        # Additional check: filename should be alphanumeric with dots/hyphens
        if not all(c.isalnum() or c in ".-_" for c in filename):
            raise ValueError(f"Filename contains invalid characters: {filename}")

        return f"{validated_model_name}/{version}/{filename}"

    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA256 checksum of content.

        Args:
            content: Content to hash

        Returns:
            SHA256 hex digest
        """
        return hashlib.sha256(content.encode()).hexdigest()

    async def store_model(
        self,
        model_name: str,
        version: AutoIncrementVersion,
        modelfile_content: str,
        metadata: VersionMetadata,
    ) -> str:
        """Store a model version in MinIO.

        Args:
            model_name: Name of the model
            version: Version number
            modelfile_content: Content of the Ollama Modelfile
            metadata: Version metadata

        Returns:
            Storage path in MinIO

        Raises:
            StorageError: If storage operation fails
        """
        try:
            # Calculate checksum
            checksum = self._calculate_checksum(modelfile_content)
            metadata.checksum = checksum
            metadata.modelfile_size_bytes = len(modelfile_content.encode())
            metadata.storage_path = self._get_object_path(model_name, version, "")

            # Store modelfile
            modelfile_path = self._get_object_path(model_name, version, "modelfile")
            modelfile_bytes = modelfile_content.encode()

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=modelfile_path,
                data=modelfile_bytes,
                length=len(modelfile_bytes),
                content_type="text/plain",
            )

            logger.info(
                f"Stored modelfile: {modelfile_path} "
                f"({len(modelfile_bytes)} bytes, checksum: {checksum[:8]}...)"
            )

            # Store metadata
            metadata_path = self._get_object_path(model_name, version, "metadata.json")
            metadata_json = json.dumps(metadata.to_dict(), indent=2)
            metadata_bytes = metadata_json.encode()

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=metadata_path,
                data=metadata_bytes,
                length=len(metadata_bytes),
                content_type="application/json",
            )

            logger.info(f"Stored metadata: {metadata_path}")

            return metadata.storage_path

        except S3Error as e:
            logger.error(f"Failed to store model {model_name} v{version}: {e}")
            raise StorageError(f"Model storage failed: {e}")

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
        try:
            # Get latest version if not specified
            if version is None:
                version = await self.get_latest_version(model_name)
                if version is None:
                    raise ModelNotFoundError(f"No versions found for model: {model_name}")

            # Check if version exists
            if not await self.version_exists(model_name, version):
                raise ModelNotFoundError(f"Model {model_name} version {version} not found")

            # Retrieve modelfile
            modelfile_path = self._get_object_path(model_name, version, "modelfile")
            response = self.client.get_object(self.bucket_name, modelfile_path)
            modelfile_content = response.read().decode()
            response.close()
            response.release_conn()

            # Retrieve metadata
            metadata = await self.get_version_metadata(model_name, version)

            logger.info(f"Retrieved model {model_name} {version}")

            return modelfile_content, metadata

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ModelNotFoundError(f"Model {model_name} version {version} not found")
            logger.error(f"Failed to retrieve model {model_name} {version}: {e}")
            raise StorageError(f"Model retrieval failed: {e}")

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
        try:
            versions: list[VersionMetadata] = []

            # List all objects under model_name/
            prefix = f"{model_name}/"
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            # Extract version numbers from paths
            version_numbers = set()
            for obj in objects:
                # Path format: model_name/v1/filename
                parts = obj.object_name.split("/")
                if len(parts) >= 2 and parts[1].startswith("v"):
                    version_str = parts[1]
                    version_numbers.add(version_str)

            # Retrieve metadata for each version
            for version_str in version_numbers:
                try:
                    version = AutoIncrementVersion.from_string(version_str)
                    metadata = await self.get_version_metadata(model_name, version)

                    # Filter by active status if requested
                    if not include_inactive and not metadata.is_active:
                        continue

                    versions.append(metadata)
                except Exception as e:
                    logger.warning(
                        f"Failed to retrieve metadata for {model_name} {version_str}: {e}"
                    )
                    continue

            # Sort by version (newest first)
            versions.sort(key=lambda m: m.version, reverse=True)

            logger.info(f"Listed {len(versions)} versions for model {model_name}")

            return versions

        except S3Error as e:
            logger.error(f"Failed to list versions for {model_name}: {e}")
            raise StorageError(f"Version listing failed: {e}")

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
        versions = await self.list_versions(model_name, include_inactive=True)

        if not versions:
            return None

        # Return highest version number
        return max(versions, key=lambda m: m.version).version

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
        try:
            # Check if version exists
            if not await self.version_exists(model_name, version):
                raise ModelNotFoundError(f"Model {model_name} version {version} not found")

            # Delete modelfile
            modelfile_path = self._get_object_path(model_name, version, "modelfile")
            self.client.remove_object(self.bucket_name, modelfile_path)

            # Delete metadata
            metadata_path = self._get_object_path(model_name, version, "metadata.json")
            self.client.remove_object(self.bucket_name, metadata_path)

            logger.info(f"Deleted model {model_name} {version}")

            return True

        except S3Error as e:
            logger.error(f"Failed to delete model {model_name} {version}: {e}")
            raise StorageError(f"Model deletion failed: {e}")

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
        try:
            metadata_path = self._get_object_path(model_name, version, "metadata.json")

            # Try to get object metadata (stat_object is faster than get_object)
            try:
                self.client.stat_object(self.bucket_name, metadata_path)
                return True
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return False
                raise

        except S3Error as e:
            logger.error(f"Failed to check version existence: {e}")
            raise StorageError(f"Version existence check failed: {e}")

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
        try:
            metadata_path = self._get_object_path(model_name, version, "metadata.json")
            response = self.client.get_object(self.bucket_name, metadata_path)
            metadata_json = response.read().decode()
            response.close()
            response.release_conn()

            metadata_dict = json.loads(metadata_json)
            metadata = VersionMetadata.from_dict(metadata_dict)

            return metadata

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ModelNotFoundError(f"Metadata for {model_name} {version} not found")
            logger.error(f"Failed to get metadata for {model_name} {version}: {e}")
            raise StorageError(f"Metadata retrieval failed: {e}")

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
        try:
            # Check if version exists
            if not await self.version_exists(model_name, version):
                raise ModelNotFoundError(f"Model {model_name} version {version} not found")

            # Store updated metadata
            metadata_path = self._get_object_path(model_name, version, "metadata.json")
            metadata_json = json.dumps(metadata.to_dict(), indent=2)
            metadata_bytes = metadata_json.encode()

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=metadata_path,
                data=metadata_bytes,
                length=len(metadata_bytes),
                content_type="application/json",
            )

            logger.info(f"Updated metadata for {model_name} {version}")

        except S3Error as e:
            logger.error(f"Failed to update metadata for {model_name} {version}: {e}")
            raise StorageError(f"Metadata update failed: {e}")

    async def set_active_version(
        self,
        model_name: str,
        version: AutoIncrementVersion,
    ) -> None:
        """Set a version as the active/current version.

        Args:
            model_name: Name of the model
            version: Version to activate

        Raises:
            ModelNotFoundError: If version doesn't exist
            StorageError: If operation fails
        """
        try:
            # Get all versions
            all_versions = await self.list_versions(model_name, include_inactive=True)

            # Deactivate all versions
            for v in all_versions:
                if v.is_active:
                    v.is_active = False
                    await self.update_version_metadata(model_name, v.version, v)

            # Activate target version
            target_metadata = await self.get_version_metadata(model_name, version)
            target_metadata.is_active = True
            await self.update_version_metadata(model_name, version, target_metadata)

            logger.info(f"Set {model_name} {version} as active version")

        except Exception as e:
            logger.error(f"Failed to set active version: {e}")
            raise StorageError(f"Set active version failed: {e}")

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
        versions = await self.list_versions(model_name, include_inactive=True)

        for v in versions:
            if v.is_active:
                return v

        return None

    async def get_storage_stats(
        self,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Get storage statistics.

        Args:
            model_name: Specific model (if None, returns stats for all models)

        Returns:
            Dictionary with storage statistics

        Raises:
            StorageError: If operation fails
        """
        try:
            stats = {
                "total_size_bytes": 0,
                "total_versions": 0,
                "models": {},
            }

            prefix = f"{model_name}/" if model_name else ""
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            for obj in objects:
                stats["total_size_bytes"] += obj.size

                # Extract model name from path
                model = obj.object_name.split("/")[0]

                if model not in stats["models"]:
                    stats["models"][model] = {
                        "size_bytes": 0,
                        "versions": set(),
                    }

                stats["models"][model]["size_bytes"] += obj.size

                # Extract version if present
                parts = obj.object_name.split("/")
                if len(parts) >= 2 and parts[1].startswith("v"):
                    stats["models"][model]["versions"].add(parts[1])

            # Count versions and convert sets to lists
            for model in stats["models"]:
                stats["models"][model]["version_count"] = len(stats["models"][model]["versions"])
                stats["models"][model]["versions"] = sorted(stats["models"][model]["versions"])
                stats["total_versions"] += stats["models"][model]["version_count"]

            logger.info(
                f"Storage stats: {stats['total_versions']} versions, {stats['total_size_bytes']} bytes"
            )

            return stats

        except S3Error as e:
            logger.error(f"Failed to get storage stats: {e}")
            raise StorageError(f"Storage stats failed: {e}")

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
        try:
            # SECURITY FIX (VULN-005): Validate export path to prevent path traversal
            validated_export_path = validate_path(
                str(export_path),
                must_be_within_base=False,  # Allow exports anywhere
            )

            # Retrieve model
            modelfile_content, metadata = await self.retrieve_model(model_name, version)

            # Ensure export directory exists
            validated_export_path.parent.mkdir(parents=True, exist_ok=True)

            # Write modelfile to file
            validated_export_path.write_text(modelfile_content)

            # Write metadata alongside
            metadata_path = validated_export_path.with_suffix(".metadata.json")
            metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2))

            logger.info(
                f"Exported {model_name} {version} to {validated_export_path} "
                f"({len(modelfile_content)} bytes)"
            )

            return validated_export_path

        except Exception as e:
            logger.error(f"Failed to export {model_name} {version}: {e}")
            raise StorageError(f"Model export failed: {e}")
