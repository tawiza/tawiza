"""Model versioning service implementation."""

from datetime import datetime
from typing import Any

from loguru import logger

from src.application.ports.storage_ports import (
    IModelStorageService,
    IModelVersioningService,
)
from src.domain.entities.model_version import VersionMetadata
from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.storage.minio_adapter import (
    ModelNotFoundError,
    StorageError,
)


class VersioningError(Exception):
    """Base exception for versioning operations."""

    pass


class ModelVersioningService(IModelVersioningService):
    """Service for managing model versions."""

    def __init__(self, storage_service: IModelStorageService):
        """Initialize versioning service.

        Args:
            storage_service: Storage service implementation (MinIO)
        """
        self.storage = storage_service

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
        try:
            # Get latest version
            latest_version = await self.storage.get_latest_version(model_name)

            # Determine new version number
            if latest_version is None:
                new_version = AutoIncrementVersion(1)
                is_baseline = True
            else:
                new_version = latest_version.next()
                is_baseline = False

            # Create version metadata
            version_metadata = VersionMetadata(
                model_name=model_name,
                version=new_version,
                base_model=base_model,
                mlflow_run_id=metadata.get("mlflow_run_id"),
                mlflow_experiment_id=metadata.get("mlflow_experiment_id"),
                accuracy=metadata.get("accuracy"),
                precision=metadata.get("precision"),
                recall=metadata.get("recall"),
                f1_score=metadata.get("f1_score"),
                loss=metadata.get("loss"),
                perplexity=metadata.get("perplexity"),
                training_examples=metadata.get("training_examples", 0),
                task_type=metadata.get("task_type", "classification"),
                hyperparameters=metadata.get("hyperparameters", {}),
                created_at=datetime.utcnow(),
                trained_at=datetime.utcnow(),
                tags=metadata.get("tags", {}),
                is_active=True,  # New versions are active by default
                is_baseline=is_baseline,
                description=metadata.get("description"),
                training_notes=metadata.get("training_notes"),
            )

            # Store in MinIO
            storage_path = await self.storage.store_model(
                model_name=model_name,
                version=new_version,
                modelfile_content=modelfile_content,
                metadata=version_metadata,
            )

            logger.info(
                f"Created new version {model_name} {new_version} "
                f"(baseline={is_baseline}, path={storage_path})"
            )

            return version_metadata

        except StorageError as e:
            raise VersioningError(f"Failed to create version: {e}")
        except Exception as e:
            logger.error(f"Unexpected error creating version: {e}")
            raise VersioningError(f"Version creation failed: {e}")

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
        try:
            # Check if target version exists
            if not await self.storage.version_exists(model_name, target_version):
                raise ModelNotFoundError(
                    f"Target version {model_name} {target_version} not found"
                )

            # Retrieve target version
            modelfile_content, target_metadata = await self.storage.retrieve_model(
                model_name, target_version
            )

            # Get latest version for new version number
            latest_version = await self.storage.get_latest_version(model_name)
            new_version = (
                latest_version.next()
                if latest_version
                else AutoIncrementVersion(1)
            )

            # Create new metadata based on target version
            rollback_metadata = VersionMetadata(
                model_name=model_name,
                version=new_version,
                base_model=target_metadata.base_model,
                mlflow_run_id=target_metadata.mlflow_run_id,
                mlflow_experiment_id=target_metadata.mlflow_experiment_id,
                accuracy=target_metadata.accuracy,
                precision=target_metadata.precision,
                recall=target_metadata.recall,
                f1_score=target_metadata.f1_score,
                loss=target_metadata.loss,
                perplexity=target_metadata.perplexity,
                training_examples=target_metadata.training_examples,
                task_type=target_metadata.task_type,
                hyperparameters=target_metadata.hyperparameters.copy(),
                created_at=datetime.utcnow(),
                trained_at=target_metadata.trained_at,
                tags={
                    **target_metadata.tags,
                    "rollback_from": str(target_version),
                    "rollback_reason": reason,
                    "rollback_at": datetime.utcnow().isoformat(),
                },
                is_active=True,
                is_baseline=False,
                description=f"Rollback to {target_version}: {reason}",
                training_notes=target_metadata.training_notes,
            )

            # Store the rolled-back version as a new version
            _storage_path = await self.storage.store_model(
                model_name=model_name,
                version=new_version,
                modelfile_content=modelfile_content,
                metadata=rollback_metadata,
            )

            logger.info(
                f"Rolled back {model_name} from {latest_version} to {target_version} "
                f"(new version: {new_version}, reason: {reason})"
            )

            return rollback_metadata

        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise VersioningError(f"Rollback failed: {e}")

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
        try:
            # Retrieve both versions
            _, metadata_a = await self.storage.retrieve_model(model_name, version_a)
            _, metadata_b = await self.storage.retrieve_model(model_name, version_b)

            # Compare metrics
            metrics_diff = {}
            metric_fields = [
                "accuracy",
                "precision",
                "recall",
                "f1_score",
                "loss",
                "perplexity",
            ]

            for field in metric_fields:
                val_a = getattr(metadata_a, field)
                val_b = getattr(metadata_b, field)

                if val_a is not None and val_b is not None:
                    metrics_diff[field] = {
                        "version_a": val_a,
                        "version_b": val_b,
                        "diff": val_b - val_a,
                        "percent_change": (
                            ((val_b - val_a) / val_a * 100) if val_a != 0 else None
                        ),
                    }

            # Compare hyperparameters
            hyper_diff = {
                "added": {},
                "removed": {},
                "changed": {},
                "unchanged": {},
            }

            all_keys = set(metadata_a.hyperparameters.keys()) | set(
                metadata_b.hyperparameters.keys()
            )

            for key in all_keys:
                if key not in metadata_a.hyperparameters:
                    hyper_diff["added"][key] = metadata_b.hyperparameters[key]
                elif key not in metadata_b.hyperparameters:
                    hyper_diff["removed"][key] = metadata_a.hyperparameters[key]
                elif metadata_a.hyperparameters[key] != metadata_b.hyperparameters[key]:
                    hyper_diff["changed"][key] = {
                        "from": metadata_a.hyperparameters[key],
                        "to": metadata_b.hyperparameters[key],
                    }
                else:
                    hyper_diff["unchanged"][key] = metadata_a.hyperparameters[key]

            # Summary
            comparison = {
                "model_name": model_name,
                "version_a": str(version_a),
                "version_b": str(version_b),
                "metrics_diff": metrics_diff,
                "hyperparameters_diff": hyper_diff,
                "base_model_changed": metadata_a.base_model != metadata_b.base_model,
                "base_model_a": metadata_a.base_model,
                "base_model_b": metadata_b.base_model,
                "training_examples_a": metadata_a.training_examples,
                "training_examples_b": metadata_b.training_examples,
                "training_examples_diff": (
                    metadata_b.training_examples - metadata_a.training_examples
                ),
                "size_diff_bytes": (
                    metadata_b.modelfile_size_bytes - metadata_a.modelfile_size_bytes
                ),
            }

            logger.info(f"Compared {model_name} {version_a} vs {version_b}")

            return comparison

        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Version comparison failed: {e}")
            raise VersioningError(f"Comparison failed: {e}")

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
        try:
            versions = await self.storage.list_versions(
                model_name, include_inactive=True
            )

            # Apply limit if specified
            if limit is not None and limit > 0:
                versions = versions[:limit]

            logger.info(f"Retrieved {len(versions)} versions for {model_name}")

            return versions

        except Exception as e:
            logger.error(f"Failed to get version history: {e}")
            raise VersioningError(f"Version history retrieval failed: {e}")

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
        try:
            # Retrieve metadata
            metadata = await self.storage.get_version_metadata(model_name, version)

            # Add tag
            metadata.tags[tag_key] = tag_value

            # Update metadata
            await self.storage.update_version_metadata(model_name, version, metadata)

            logger.info(f"Tagged {model_name} {version} with {tag_key}={tag_value}")

        except ModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Tagging failed: {e}")
            raise VersioningError(f"Tag operation failed: {e}")

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
        try:
            # Validate environment
            valid_envs = ["dev", "development", "staging", "production", "prod"]
            if environment.lower() not in valid_envs:
                raise VersioningError(
                    f"Invalid environment: {environment}. "
                    f"Valid: {', '.join(valid_envs)}"
                )

            # Add promotion tag
            await self.tag_version(
                model_name,
                version,
                f"promoted_to_{environment}",
                datetime.utcnow().isoformat(),
            )

            # If promoting to production, set as active
            if environment.lower() in ["production", "prod"]:
                await self.storage.set_active_version(model_name, version)

            logger.info(f"Promoted {model_name} {version} to {environment}")

        except ModelNotFoundError:
            raise
        except VersioningError:
            raise
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            raise VersioningError(f"Version promotion failed: {e}")
