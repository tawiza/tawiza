"""Tests for MinIO storage adapter."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from minio import Minio
from minio.error import S3Error

from src.domain.entities.model_version import VersionMetadata
from src.domain.value_objects.version import AutoIncrementVersion
from src.infrastructure.storage.minio_adapter import (
    MinIOStorageAdapter,
    ModelNotFoundError,
    StorageError,
)


@pytest.fixture
def mock_minio_client():
    """Create a mock MinIO client."""
    mock_client = Mock(spec=Minio)
    mock_client.bucket_exists = Mock(return_value=False)
    mock_client.make_bucket = Mock()
    mock_client.put_object = Mock()
    mock_client.get_object = Mock()
    mock_client.stat_object = Mock()
    mock_client.list_objects = Mock()
    mock_client.remove_object = Mock()
    return mock_client


@pytest.fixture
def storage_adapter(mock_minio_client):
    """Create a storage adapter with mocked client."""
    adapter = MinIOStorageAdapter(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket_name="test-bucket",
        secure=False,
    )
    adapter.client = mock_minio_client
    return adapter


@pytest.fixture
def sample_metadata():
    """Create sample version metadata."""
    return VersionMetadata(
        model_name="test-model",
        version=AutoIncrementVersion(1),
        base_model="qwen3-coder:30b",
        accuracy=0.95,
        training_examples=100,
        task_type="classification",
    )


class TestMinIOStorageAdapter:
    """Tests for MinIO storage adapter."""

    @pytest.mark.asyncio
    async def test_initialize_bucket_creates_new(self, storage_adapter, mock_minio_client):
        """Test bucket initialization creates new bucket."""
        mock_minio_client.bucket_exists.return_value = False

        await storage_adapter.initialize_bucket()

        mock_minio_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_minio_client.make_bucket.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_initialize_bucket_exists(self, storage_adapter, mock_minio_client):
        """Test bucket initialization skips if exists."""
        mock_minio_client.bucket_exists.return_value = True

        await storage_adapter.initialize_bucket()

        mock_minio_client.bucket_exists.assert_called_once_with("test-bucket")
        mock_minio_client.make_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_model(self, storage_adapter, mock_minio_client, sample_metadata):
        """Test storing a model version."""
        modelfile_content = "FROM qwen3-coder:30b\nSYSTEM You are a helpful assistant."

        storage_path = await storage_adapter.store_model(
            model_name="test-model",
            version=AutoIncrementVersion(1),
            modelfile_content=modelfile_content,
            metadata=sample_metadata,
        )

        # Should have stored both modelfile and metadata
        assert mock_minio_client.put_object.call_count == 2
        assert storage_path == "test-model/v1/"

        # Verify checksum was calculated
        assert sample_metadata.checksum is not None
        assert len(sample_metadata.checksum) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_retrieve_model(self, storage_adapter, mock_minio_client, sample_metadata):
        """Test retrieving a model version."""
        modelfile_content = "FROM qwen3-coder:30b"

        # Mock modelfile retrieval
        modelfile_response = Mock()
        modelfile_response.read = Mock(return_value=modelfile_content.encode())
        modelfile_response.close = Mock()
        modelfile_response.release_conn = Mock()

        # Mock metadata retrieval
        import json

        metadata_json = json.dumps(sample_metadata.to_dict())
        metadata_response = Mock()
        metadata_response.read = Mock(return_value=metadata_json.encode())
        metadata_response.close = Mock()
        metadata_response.release_conn = Mock()

        # Configure mock to return different responses
        def get_object_side_effect(bucket, path):
            if "modelfile" in path:
                return modelfile_response
            elif "metadata.json" in path:
                return metadata_response

        mock_minio_client.get_object.side_effect = get_object_side_effect
        mock_minio_client.stat_object.return_value = Mock()

        # Retrieve model
        retrieved_content, retrieved_metadata = await storage_adapter.retrieve_model(
            model_name="test-model",
            version=AutoIncrementVersion(1),
        )

        assert retrieved_content == modelfile_content
        assert retrieved_metadata.model_name == "test-model"
        assert retrieved_metadata.version == AutoIncrementVersion(1)

    @pytest.mark.asyncio
    async def test_retrieve_model_not_found(self, storage_adapter, mock_minio_client):
        """Test retrieving non-existent model raises error."""
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Key not found",
            resource="test-bucket/test-model/v1/metadata.json",
            request_id="",
            host_id="",
            response=Mock(status=404),
        )

        with pytest.raises(ModelNotFoundError):
            await storage_adapter.retrieve_model(
                model_name="test-model",
                version=AutoIncrementVersion(1),
            )

    @pytest.mark.asyncio
    async def test_list_versions(self, storage_adapter, mock_minio_client):
        """Test listing model versions."""
        # Mock objects in MinIO
        mock_objects = [
            Mock(object_name="test-model/v1/modelfile", size=1000),
            Mock(object_name="test-model/v1/metadata.json", size=500),
            Mock(object_name="test-model/v2/modelfile", size=1200),
            Mock(object_name="test-model/v2/metadata.json", size=600),
        ]
        mock_minio_client.list_objects.return_value = mock_objects

        # Mock metadata retrieval
        import json
        from datetime import datetime

        def mock_get_metadata(version_num):
            metadata = VersionMetadata(
                model_name="test-model",
                version=AutoIncrementVersion(version_num),
                base_model="qwen3-coder:30b",
                created_at=datetime.utcnow(),
            )
            return metadata

        # Configure get_object to return metadata
        def get_object_side_effect(bucket, path):
            if "v1/metadata.json" in path:
                metadata = mock_get_metadata(1)
            elif "v2/metadata.json" in path:
                metadata = mock_get_metadata(2)
            else:
                raise S3Error(
                    code="NoSuchKey",
                    message="Not found",
                    resource="",
                    request_id="",
                    host_id="",
                    response=Mock(status=404),
                )

            response = Mock()
            response.read = Mock(return_value=json.dumps(metadata.to_dict()).encode())
            response.close = Mock()
            response.release_conn = Mock()
            return response

        mock_minio_client.get_object.side_effect = get_object_side_effect

        # List versions
        versions = await storage_adapter.list_versions("test-model")

        # Should return 2 versions, sorted newest first
        assert len(versions) == 2
        assert versions[0].version == AutoIncrementVersion(2)
        assert versions[1].version == AutoIncrementVersion(1)

    @pytest.mark.asyncio
    async def test_delete_version(self, storage_adapter, mock_minio_client):
        """Test deleting a model version."""
        # Mock version exists
        mock_minio_client.stat_object.return_value = Mock()

        result = await storage_adapter.delete_version(
            model_name="test-model",
            version=AutoIncrementVersion(1),
        )

        assert result is True
        # Should delete both modelfile and metadata
        assert mock_minio_client.remove_object.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_version_not_found(self, storage_adapter, mock_minio_client):
        """Test deleting non-existent version raises error."""
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Key not found",
            resource="test-bucket/test-model/v1/metadata.json",
            request_id="",
            host_id="",
            response=Mock(status=404),
        )

        with pytest.raises(ModelNotFoundError):
            await storage_adapter.delete_version(
                model_name="test-model",
                version=AutoIncrementVersion(1),
            )

    @pytest.mark.asyncio
    async def test_version_exists(self, storage_adapter, mock_minio_client):
        """Test checking if version exists."""
        mock_minio_client.stat_object.return_value = Mock()

        exists = await storage_adapter.version_exists(
            model_name="test-model",
            version=AutoIncrementVersion(1),
        )

        assert exists is True

    @pytest.mark.asyncio
    async def test_version_not_exists(self, storage_adapter, mock_minio_client):
        """Test checking if version doesn't exist."""
        mock_minio_client.stat_object.side_effect = S3Error(
            code="NoSuchKey",
            message="Key not found",
            resource="",
            request_id="",
            host_id="",
            response=Mock(status=404),
        )

        exists = await storage_adapter.version_exists(
            model_name="test-model",
            version=AutoIncrementVersion(1),
        )

        assert exists is False

    @pytest.mark.asyncio
    async def test_set_active_version(self, storage_adapter, mock_minio_client):
        """Test setting active version."""
        # Mock list_versions to return multiple versions
        import json
        from datetime import datetime

        v1_metadata = VersionMetadata(
            model_name="test-model",
            version=AutoIncrementVersion(1),
            base_model="qwen3-coder:30b",
            is_active=True,
            created_at=datetime.utcnow(),
        )

        v2_metadata = VersionMetadata(
            model_name="test-model",
            version=AutoIncrementVersion(2),
            base_model="qwen3-coder:30b",
            is_active=False,
            created_at=datetime.utcnow(),
        )

        # Mock objects
        mock_objects = [
            Mock(object_name="test-model/v1/modelfile", size=1000),
            Mock(object_name="test-model/v1/metadata.json", size=500),
            Mock(object_name="test-model/v2/modelfile", size=1200),
            Mock(object_name="test-model/v2/metadata.json", size=600),
        ]
        mock_minio_client.list_objects.return_value = mock_objects

        # Configure get_object
        def get_object_side_effect(bucket, path):
            if "v1/metadata.json" in path:
                metadata = v1_metadata
            elif "v2/metadata.json" in path:
                metadata = v2_metadata
            else:
                raise S3Error(
                    code="NoSuchKey",
                    message="Not found",
                    resource="",
                    request_id="",
                    host_id="",
                    response=Mock(status=404),
                )

            response = Mock()
            response.read = Mock(return_value=json.dumps(metadata.to_dict()).encode())
            response.close = Mock()
            response.release_conn = Mock()
            return response

        mock_minio_client.get_object.side_effect = get_object_side_effect

        # Set v2 as active
        await storage_adapter.set_active_version(
            model_name="test-model",
            version=AutoIncrementVersion(2),
        )

        # Should update metadata for both versions
        assert mock_minio_client.put_object.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, storage_adapter, mock_minio_client):
        """Test getting storage statistics."""
        mock_objects = [
            Mock(object_name="model1/v1/modelfile", size=1000),
            Mock(object_name="model1/v1/metadata.json", size=100),
            Mock(object_name="model1/v2/modelfile", size=1200),
            Mock(object_name="model1/v2/metadata.json", size=120),
            Mock(object_name="model2/v1/modelfile", size=800),
            Mock(object_name="model2/v1/metadata.json", size=80),
        ]
        mock_minio_client.list_objects.return_value = mock_objects

        stats = await storage_adapter.get_storage_stats()

        assert stats["total_size_bytes"] == 3300
        assert stats["total_versions"] == 3
        assert "model1" in stats["models"]
        assert "model2" in stats["models"]
        assert stats["models"]["model1"]["version_count"] == 2
        assert stats["models"]["model2"]["version_count"] == 1
