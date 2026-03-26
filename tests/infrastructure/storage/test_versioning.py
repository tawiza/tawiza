"""Tests for model versioning service."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.entities.model_version import VersionMetadata
from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.storage.minio_adapter import ModelNotFoundError
from src.infrastructure.storage.versioning_service import (
    ModelVersioningService,
    VersioningError,
)


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    mock = Mock()
    mock.get_latest_version = AsyncMock()
    mock.store_model = AsyncMock()
    mock.retrieve_model = AsyncMock()
    mock.version_exists = AsyncMock()
    mock.get_version_metadata = AsyncMock()
    mock.update_version_metadata = AsyncMock()
    mock.list_versions = AsyncMock()
    return mock


@pytest.fixture
def versioning_service(mock_storage_service):
    """Create versioning service with mocked storage."""
    return ModelVersioningService(mock_storage_service)


@pytest.fixture
def sample_metadata_v1():
    """Create sample metadata for version 1."""
    return VersionMetadata(
        model_name="test-model",
        version=AutoIncrementVersion(1),
        base_model="qwen3-coder:30b",
        accuracy=0.90,
        training_examples=100,
        task_type="classification",
        created_at=datetime.utcnow(),
        is_baseline=True,
    )


@pytest.fixture
def sample_metadata_v2():
    """Create sample metadata for version 2."""
    return VersionMetadata(
        model_name="test-model",
        version=AutoIncrementVersion(2),
        base_model="qwen3-coder:30b",
        accuracy=0.95,
        training_examples=200,
        task_type="classification",
        created_at=datetime.utcnow(),
        is_baseline=False,
    )


class TestModelVersioningService:
    """Tests for model versioning service."""

    @pytest.mark.asyncio
    async def test_create_first_version(self, versioning_service, mock_storage_service):
        """Test creating the first version of a model."""
        # No existing versions
        mock_storage_service.get_latest_version.return_value = None
        mock_storage_service.store_model.return_value = "test-model/v1/"

        modelfile = "FROM qwen3-coder:30b"
        metadata = {
            "accuracy": 0.90,
            "training_examples": 100,
            "task_type": "classification",
        }

        result = await versioning_service.create_new_version(
            model_name="test-model",
            base_model="qwen3-coder:30b",
            modelfile_content=modelfile,
            metadata=metadata,
        )

        # Should create version 1 as baseline
        assert result.version == AutoIncrementVersion(1)
        assert result.is_baseline is True
        assert result.is_active is True
        mock_storage_service.store_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_subsequent_version(self, versioning_service, mock_storage_service):
        """Test creating a new version when versions exist."""
        # Existing version 1
        mock_storage_service.get_latest_version.return_value = AutoIncrementVersion(1)
        mock_storage_service.store_model.return_value = "test-model/v2/"

        modelfile = "FROM qwen3-coder:30b"
        metadata = {
            "accuracy": 0.95,
            "training_examples": 200,
        }

        result = await versioning_service.create_new_version(
            model_name="test-model",
            base_model="qwen3-coder:30b",
            modelfile_content=modelfile,
            metadata=metadata,
        )

        # Should create version 2, not baseline
        assert result.version == AutoIncrementVersion(2)
        assert result.is_baseline is False
        assert result.is_active is True
        mock_storage_service.store_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_version(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
    ):
        """Test rolling back to a previous version."""
        # Mock version exists
        mock_storage_service.version_exists.return_value = True

        # Mock retrieve model
        modelfile = "FROM qwen3-coder:30b"
        mock_storage_service.retrieve_model.return_value = (modelfile, sample_metadata_v1)

        # Mock latest version is v2
        mock_storage_service.get_latest_version.return_value = AutoIncrementVersion(2)
        mock_storage_service.store_model.return_value = "test-model/v3/"

        # Rollback to v1
        result = await versioning_service.rollback_to_version(
            model_name="test-model",
            target_version=AutoIncrementVersion(1),
            reason="Performance regression",
        )

        # Should create v3 based on v1
        assert result.version == AutoIncrementVersion(3)
        assert result.accuracy == sample_metadata_v1.accuracy
        assert result.tags["rollback_from"] == "v1"
        assert result.tags["rollback_reason"] == "Performance regression"
        mock_storage_service.store_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_nonexistent_version(
        self,
        versioning_service,
        mock_storage_service,
    ):
        """Test rollback to non-existent version raises error."""
        mock_storage_service.version_exists.return_value = False

        with pytest.raises(ModelNotFoundError):
            await versioning_service.rollback_to_version(
                model_name="test-model",
                target_version=AutoIncrementVersion(99),
                reason="Test",
            )

    @pytest.mark.asyncio
    async def test_compare_versions(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
        sample_metadata_v2,
    ):
        """Test comparing two versions."""
        # Mock retrieve for both versions
        modelfile_v1 = "FROM qwen3-coder:30b"
        modelfile_v2 = "FROM qwen3-coder:30b\nSYSTEM You are helpful."

        async def retrieve_side_effect(model_name, version):
            if version == AutoIncrementVersion(1):
                return (modelfile_v1, sample_metadata_v1)
            elif version == AutoIncrementVersion(2):
                return (modelfile_v2, sample_metadata_v2)

        mock_storage_service.retrieve_model.side_effect = retrieve_side_effect

        # Compare versions
        comparison = await versioning_service.compare_versions(
            model_name="test-model",
            version_a=AutoIncrementVersion(1),
            version_b=AutoIncrementVersion(2),
        )

        # Verify comparison results
        assert comparison["model_name"] == "test-model"
        assert comparison["version_a"] == "v1"
        assert comparison["version_b"] == "v2"

        # Check metrics diff
        assert "accuracy" in comparison["metrics_diff"]
        accuracy_diff = comparison["metrics_diff"]["accuracy"]
        assert accuracy_diff["version_a"] == 0.90
        assert accuracy_diff["version_b"] == 0.95
        assert abs(accuracy_diff["diff"] - 0.05) < 1e-10

        # Check training examples diff
        assert comparison["training_examples_a"] == 100
        assert comparison["training_examples_b"] == 200
        assert comparison["training_examples_diff"] == 100

    @pytest.mark.asyncio
    async def test_tag_version(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
    ):
        """Test tagging a version."""
        mock_storage_service.get_version_metadata.return_value = sample_metadata_v1

        await versioning_service.tag_version(
            model_name="test-model",
            version=AutoIncrementVersion(1),
            tag_key="environment",
            tag_value="production",
        )

        # Should update metadata with tag
        mock_storage_service.update_version_metadata.assert_called_once()
        updated_metadata = mock_storage_service.update_version_metadata.call_args[0][2]
        assert updated_metadata.tags["environment"] == "production"

    @pytest.mark.asyncio
    async def test_promote_to_production(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
    ):
        """Test promoting version to production."""
        mock_storage_service.get_version_metadata.return_value = sample_metadata_v1
        mock_storage_service.set_active_version = AsyncMock()

        await versioning_service.promote_version(
            model_name="test-model",
            version=AutoIncrementVersion(1),
            environment="production",
        )

        # Should tag and set as active
        mock_storage_service.update_version_metadata.assert_called_once()
        mock_storage_service.set_active_version.assert_called_once_with(
            "test-model", AutoIncrementVersion(1)
        )

    @pytest.mark.asyncio
    async def test_promote_to_staging(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
    ):
        """Test promoting version to staging."""
        mock_storage_service.get_version_metadata.return_value = sample_metadata_v1
        mock_storage_service.set_active_version = AsyncMock()

        await versioning_service.promote_version(
            model_name="test-model",
            version=AutoIncrementVersion(1),
            environment="staging",
        )

        # Should tag but NOT set as active (only production does that)
        mock_storage_service.update_version_metadata.assert_called_once()
        mock_storage_service.set_active_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_promote_invalid_environment(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
    ):
        """Test promoting to invalid environment raises error."""
        mock_storage_service.get_version_metadata.return_value = sample_metadata_v1

        with pytest.raises(VersioningError, match="Invalid environment"):
            await versioning_service.promote_version(
                model_name="test-model",
                version=AutoIncrementVersion(1),
                environment="invalid",
            )

    @pytest.mark.asyncio
    async def test_get_version_history(
        self,
        versioning_service,
        mock_storage_service,
        sample_metadata_v1,
        sample_metadata_v2,
    ):
        """Test getting version history."""
        mock_storage_service.list_versions.return_value = [
            sample_metadata_v2,
            sample_metadata_v1,
        ]

        history = await versioning_service.get_version_history(
            model_name="test-model",
            limit=10,
        )

        assert len(history) == 2
        assert history[0].version == AutoIncrementVersion(2)
        assert history[1].version == AutoIncrementVersion(1)
        mock_storage_service.list_versions.assert_called_once_with(
            "test-model", include_inactive=True
        )

    @pytest.mark.asyncio
    async def test_get_version_history_with_limit(
        self,
        versioning_service,
        mock_storage_service,
    ):
        """Test getting version history with limit."""
        # Create 5 versions
        versions = [
            VersionMetadata(
                model_name="test-model",
                version=AutoIncrementVersion(i),
                base_model="qwen3-coder:30b",
                created_at=datetime.utcnow(),
            )
            for i in range(5, 0, -1)  # v5, v4, v3, v2, v1
        ]
        mock_storage_service.list_versions.return_value = versions

        # Get only 3 most recent
        history = await versioning_service.get_version_history(
            model_name="test-model",
            limit=3,
        )

        assert len(history) == 3
        assert history[0].version == AutoIncrementVersion(5)
        assert history[2].version == AutoIncrementVersion(3)
