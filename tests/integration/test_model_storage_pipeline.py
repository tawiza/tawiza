"""
Integration tests for MinIO model storage pipeline.

Tests the complete storage workflow:
1. Bucket initialization
2. Model version creation
3. Version listing and retrieval
4. Version comparison
5. Rollback operations
6. Deletion and cleanup
"""

import pytest
from loguru import logger

# Skip all tests - requires MinIO service
pytestmark = pytest.mark.skipif(True, reason="Requires MinIO service")

from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.storage.minio_adapter import (
    MinIOStorageAdapter,
    ModelNotFoundError,
)
from src.infrastructure.storage.versioning_service import ModelVersioningService


@pytest.mark.integration
@pytest.mark.minio
class TestModelStoragePipeline:
    """Test complete model storage pipeline."""

    @pytest.mark.asyncio
    async def test_bucket_initialization(
        self,
        storage_adapter: MinIOStorageAdapter,
    ):
        """Test MinIO bucket initialization."""
        # Bucket should be created by fixture
        assert storage_adapter.client.bucket_exists(storage_adapter.bucket_name)
        logger.info(f"✓ Bucket initialized: {storage_adapter.bucket_name}")

    @pytest.mark.asyncio
    async def test_store_and_retrieve_model(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
    ):
        """Test storing and retrieving a model version."""
        from src.domain.entities.model_version import VersionMetadata

        # Create version metadata
        version = AutoIncrementVersion(1)
        metadata = VersionMetadata(
            model_name=test_model_name,
            version=version,
            base_model="qwen3-coder:30b",
            **sample_training_metadata,
        )

        # Store model
        storage_path = await storage_adapter.store_model(
            model_name=test_model_name,
            version=version,
            modelfile_content=sample_modelfile,
            metadata=metadata,
        )

        assert storage_path is not None
        logger.info(f"✓ Model stored at: {storage_path}")

        # Verify version exists
        exists = await storage_adapter.version_exists(test_model_name, version)
        assert exists is True

        # Retrieve model
        retrieved_content, retrieved_metadata = await storage_adapter.retrieve_model(
            model_name=test_model_name,
            version=version,
        )

        assert retrieved_content == sample_modelfile
        assert retrieved_metadata.model_name == test_model_name
        assert retrieved_metadata.version == version
        assert retrieved_metadata.checksum is not None
        logger.info(
            f"✓ Model retrieved successfully (checksum: {retrieved_metadata.checksum[:8]}...)"
        )

    @pytest.mark.asyncio
    async def test_version_listing(
        self,
        versioning_service: ModelVersioningService,
        test_model_name: str,
        sample_modelfile: str,
    ):
        """Test listing model versions."""
        # Create multiple versions
        versions_created = []
        for i in range(3):
            metadata_dict = {
                "mlflow_run_id": f"run-{i}",
                "mlflow_experiment_id": "test-experiment",
                "accuracy": 0.8 + (i * 0.05),
                "training_examples": 100 * (i + 1),
                "task_type": "classification",
                "description": f"Version {i + 1}",
            }

            version_meta = await versioning_service.create_new_version(
                model_name=test_model_name,
                base_model="qwen3-coder:30b",
                modelfile_content=sample_modelfile + f"\n# Version {i + 1}",
                metadata=metadata_dict,
            )
            versions_created.append(version_meta)
            logger.info(f"✓ Created version: {version_meta.version}")

        # List versions
        versions = await versioning_service.storage.list_versions(test_model_name)

        assert len(versions) == 3
        assert all(v.model_name == test_model_name for v in versions)

        # Verify sorted by version (newest first)
        assert versions[0].version.value > versions[1].version.value
        assert versions[1].version.value > versions[2].version.value

        logger.info(f"✓ Listed {len(versions)} versions correctly")

    @pytest.mark.asyncio
    async def test_get_latest_version(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
    ):
        """Test getting latest version of a model."""
        from src.domain.entities.model_version import VersionMetadata

        # Create versions v1, v2, v3
        for i in range(1, 4):
            version = AutoIncrementVersion(i)
            metadata = VersionMetadata(
                model_name=test_model_name,
                version=version,
                base_model="qwen3-coder:30b",
                **sample_training_metadata,
            )

            await storage_adapter.store_model(
                model_name=test_model_name,
                version=version,
                modelfile_content=sample_modelfile,
                metadata=metadata,
            )

        # Get latest version
        latest = await storage_adapter.get_latest_version(test_model_name)

        assert latest is not None
        assert latest.value == 3
        logger.info(f"✓ Latest version retrieved: {latest}")

    @pytest.mark.asyncio
    async def test_version_comparison(
        self,
        versioning_service: ModelVersioningService,
        test_model_name: str,
        sample_modelfile: str,
    ):
        """Test comparing two model versions."""
        # Create version 1
        metadata_v1 = {
            "mlflow_run_id": "run-1",
            "mlflow_experiment_id": "test-experiment",
            "accuracy": 0.85,
            "precision": 0.82,
            "recall": 0.88,
            "f1_score": 0.85,
            "loss": 0.15,
            "training_examples": 100,
            "task_type": "classification",
            "hyperparameters": {
                "learning_rate": 0.001,
                "batch_size": 32,
            },
        }

        v1 = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile,
            metadata=metadata_v1,
        )

        # Create version 2 with improved metrics
        metadata_v2 = {
            "mlflow_run_id": "run-2",
            "mlflow_experiment_id": "test-experiment",
            "accuracy": 0.92,
            "precision": 0.90,
            "recall": 0.94,
            "f1_score": 0.92,
            "loss": 0.08,
            "training_examples": 200,
            "task_type": "classification",
            "hyperparameters": {
                "learning_rate": 0.0005,
                "batch_size": 64,
            },
        }

        v2 = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile + "\n# Improved",
            metadata=metadata_v2,
        )

        # Compare versions
        comparison = await versioning_service.compare_versions(
            model_name=test_model_name,
            version_a=v1.version,
            version_b=v2.version,
        )

        assert comparison["model_name"] == test_model_name
        assert comparison["metrics_diff"]["accuracy"]["diff"] == pytest.approx(0.07)
        assert comparison["metrics_diff"]["accuracy"]["percent_change"] > 0
        assert comparison["hyperparameters_diff"]["changed"]["learning_rate"]["from"] == 0.001
        assert comparison["hyperparameters_diff"]["changed"]["learning_rate"]["to"] == 0.0005
        assert comparison["training_examples_diff"] == 100

        logger.info("✓ Comparison completed:")
        logger.info(f"  Accuracy improvement: {comparison['metrics_diff']['accuracy']['diff']:.2%}")
        logger.info(
            f"  Training examples: {comparison['training_examples_a']} → {comparison['training_examples_b']}"
        )

    @pytest.mark.asyncio
    async def test_rollback_version(
        self,
        versioning_service: ModelVersioningService,
        test_model_name: str,
        sample_modelfile: str,
    ):
        """Test rolling back to a previous version."""
        # Create v1 (good version)
        v1_metadata = {
            "mlflow_run_id": "run-1",
            "mlflow_experiment_id": "test",
            "accuracy": 0.90,
            "training_examples": 100,
            "task_type": "classification",
        }

        v1 = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile,
            metadata=v1_metadata,
        )

        # Create v2 (bad version)
        v2_metadata = {
            "mlflow_run_id": "run-2",
            "mlflow_experiment_id": "test",
            "accuracy": 0.75,  # Lower accuracy
            "training_examples": 150,
            "task_type": "classification",
        }

        v2 = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile + "\n# Bad version",
            metadata=v2_metadata,
        )

        logger.info(f"✓ Created v1 (acc: {v1.accuracy}) and v2 (acc: {v2.accuracy})")

        # Rollback to v1
        rollback = await versioning_service.rollback_to_version(
            model_name=test_model_name,
            target_version=v1.version,
            reason="Performance degradation in v2",
        )

        # Verify rollback created v3
        assert rollback.version.value == 3
        assert rollback.accuracy == v1.accuracy
        assert "rollback_from" in rollback.tags
        assert rollback.tags["rollback_from"] == str(v1.version)
        assert "Performance degradation" in rollback.description

        logger.info(f"✓ Rolled back to v1, created {rollback.version}")

    @pytest.mark.asyncio
    async def test_active_version_management(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
    ):
        """Test active version management."""
        from src.domain.entities.model_version import VersionMetadata

        # Create versions
        v1 = AutoIncrementVersion(1)
        v2 = AutoIncrementVersion(2)

        for version in [v1, v2]:
            metadata = VersionMetadata(
                model_name=test_model_name,
                version=version,
                base_model="qwen3-coder:30b",
                **sample_training_metadata,
            )
            await storage_adapter.store_model(
                model_name=test_model_name,
                version=version,
                modelfile_content=sample_modelfile,
                metadata=metadata,
            )

        # Set v1 as active
        await storage_adapter.set_active_version(test_model_name, v1)

        # Get active version
        active = await storage_adapter.get_active_version(test_model_name)
        assert active is not None
        assert active.version == v1

        logger.info(f"✓ Set and retrieved active version: {active.version}")

        # Switch to v2
        await storage_adapter.set_active_version(test_model_name, v2)
        active = await storage_adapter.get_active_version(test_model_name)
        assert active.version == v2

        logger.info(f"✓ Switched active version to: {active.version}")

    @pytest.mark.asyncio
    async def test_version_deletion(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
    ):
        """Test deleting a model version."""
        from src.domain.entities.model_version import VersionMetadata

        # Create version
        version = AutoIncrementVersion(1)
        metadata = VersionMetadata(
            model_name=test_model_name,
            version=version,
            base_model="qwen3-coder:30b",
            **sample_training_metadata,
        )

        await storage_adapter.store_model(
            model_name=test_model_name,
            version=version,
            modelfile_content=sample_modelfile,
            metadata=metadata,
        )

        # Verify exists
        assert await storage_adapter.version_exists(test_model_name, version)

        # Delete version
        deleted = await storage_adapter.delete_version(test_model_name, version)
        assert deleted is True

        # Verify doesn't exist
        assert not await storage_adapter.version_exists(test_model_name, version)

        logger.info(f"✓ Deleted version: {version}")

    @pytest.mark.asyncio
    async def test_storage_statistics(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
    ):
        """Test storage statistics calculation."""
        from src.domain.entities.model_version import VersionMetadata

        # Create multiple versions
        for i in range(1, 4):
            version = AutoIncrementVersion(i)
            metadata = VersionMetadata(
                model_name=test_model_name,
                version=version,
                base_model="qwen3-coder:30b",
                **sample_training_metadata,
            )

            await storage_adapter.store_model(
                model_name=test_model_name,
                version=version,
                modelfile_content=sample_modelfile * (i + 1),  # Different sizes
                metadata=metadata,
            )

        # Get stats
        stats = await storage_adapter.get_storage_stats(test_model_name)

        assert stats["total_versions"] == 3
        assert test_model_name in stats["models"]
        assert stats["models"][test_model_name]["version_count"] == 3
        assert stats["total_size_bytes"] > 0

        logger.info("✓ Storage stats:")
        logger.info(f"  Total versions: {stats['total_versions']}")
        logger.info(f"  Total size: {stats['total_size_bytes']} bytes")

    @pytest.mark.asyncio
    async def test_model_not_found_error(
        self,
        storage_adapter: MinIOStorageAdapter,
    ):
        """Test error handling for non-existent models."""
        with pytest.raises(ModelNotFoundError):
            await storage_adapter.retrieve_model(
                model_name="non-existent-model",
                version=AutoIncrementVersion(1),
            )

        logger.info("✓ ModelNotFoundError raised correctly")

    @pytest.mark.asyncio
    async def test_export_version_to_file(
        self,
        storage_adapter: MinIOStorageAdapter,
        test_model_name: str,
        sample_modelfile: str,
        sample_training_metadata: dict,
        tmp_path,
    ):
        """Test exporting a model version to file."""
        from src.domain.entities.model_version import VersionMetadata

        # Create version
        version = AutoIncrementVersion(1)
        metadata = VersionMetadata(
            model_name=test_model_name,
            version=version,
            base_model="qwen3-coder:30b",
            **sample_training_metadata,
        )

        await storage_adapter.store_model(
            model_name=test_model_name,
            version=version,
            modelfile_content=sample_modelfile,
            metadata=metadata,
        )

        # Export to file
        export_path = tmp_path / "exported_modelfile"
        exported = await storage_adapter.export_version_to_file(
            model_name=test_model_name,
            version=version,
            export_path=export_path,
        )

        assert exported.exists()
        assert exported.read_text() == sample_modelfile

        # Check metadata file was also created
        metadata_file = export_path.with_suffix(".metadata.json")
        assert metadata_file.exists()

        logger.info(f"✓ Exported version to: {exported}")


@pytest.mark.integration
@pytest.mark.minio
class TestModelStorageEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_retrieve_latest_version_when_none_exists(
        self,
        storage_adapter: MinIOStorageAdapter,
    ):
        """Test getting latest version when no versions exist."""
        latest = await storage_adapter.get_latest_version("non-existent-model")
        assert latest is None
        logger.info("✓ Returns None when no versions exist")

    @pytest.mark.asyncio
    async def test_version_tagging(
        self,
        versioning_service: ModelVersioningService,
        test_model_name: str,
        sample_modelfile: str,
    ):
        """Test adding tags to versions."""
        # Create version
        metadata = {
            "mlflow_run_id": "test-run",
            "mlflow_experiment_id": "test",
            "training_examples": 100,
            "task_type": "classification",
        }

        version_meta = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile,
            metadata=metadata,
        )

        # Add tags
        await versioning_service.tag_version(
            model_name=test_model_name,
            version=version_meta.version,
            tag_key="environment",
            tag_value="production",
        )

        # Retrieve and verify
        updated_meta = await versioning_service.storage.get_version_metadata(
            test_model_name, version_meta.version
        )

        assert "environment" in updated_meta.tags
        assert updated_meta.tags["environment"] == "production"

        logger.info("✓ Version tagged successfully")

    @pytest.mark.asyncio
    async def test_version_promotion(
        self,
        versioning_service: ModelVersioningService,
        test_model_name: str,
        sample_modelfile: str,
    ):
        """Test promoting a version to production."""
        # Create version
        metadata = {
            "mlflow_run_id": "test-run",
            "mlflow_experiment_id": "test",
            "training_examples": 100,
            "task_type": "classification",
        }

        version_meta = await versioning_service.create_new_version(
            model_name=test_model_name,
            base_model="qwen3-coder:30b",
            modelfile_content=sample_modelfile,
            metadata=metadata,
        )

        # Promote to production
        await versioning_service.promote_version(
            model_name=test_model_name,
            version=version_meta.version,
            environment="production",
        )

        # Verify active version
        active = await versioning_service.storage.get_active_version(test_model_name)
        assert active.version == version_meta.version

        # Verify promotion tag
        assert "promoted_to_production" in active.tags

        logger.info("✓ Version promoted to production")
