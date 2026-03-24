"""Tests complets pour s3_storage_agent.py

Tests couvrant:
- S3Object, BucketInfo, UploadResult, StorageAnalytics dataclasses
- S3StorageAgent
- Tests conditionnels (MinIO optionnel)
"""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.s3_storage_agent import (
    BucketInfo,
    S3Object,
    S3StorageAgent,
    StorageAnalytics,
    UploadResult,
)


# ============================================================================
# Tests S3Object Dataclass
# ============================================================================
class TestS3Object:
    """Tests pour la dataclass S3Object."""

    def test_create_object(self):
        """Création d'un objet S3."""
        obj = S3Object(
            bucket="test-bucket",
            key="path/to/file.txt",
            size=1024,
            last_modified=datetime(2024, 1, 1, 12, 0, 0),
            etag="abc123",
            content_type="text/plain",
        )

        assert obj.bucket == "test-bucket"
        assert obj.key == "path/to/file.txt"
        assert obj.size == 1024
        assert obj.etag == "abc123"
        assert obj.content_type == "text/plain"
        assert obj.metadata == {}
        assert obj.tags == {}

    def test_object_with_metadata(self):
        """Objet avec métadonnées et tags."""
        obj = S3Object(
            bucket="bucket",
            key="file.json",
            size=2048,
            last_modified=datetime.now(),
            etag="def456",
            content_type="application/json",
            metadata={"author": "test", "version": "1.0"},
            tags={"environment": "production", "team": "ml"},
        )

        assert obj.metadata["author"] == "test"
        assert obj.tags["environment"] == "production"


# ============================================================================
# Tests BucketInfo Dataclass
# ============================================================================
class TestBucketInfo:
    """Tests pour la dataclass BucketInfo."""

    def test_create_bucket_info(self):
        """Création d'info bucket."""
        info = BucketInfo(
            name="my-bucket",
            creation_date=datetime(2024, 1, 1, 0, 0, 0),
            object_count=100,
            total_size=1024 * 1024 * 500,  # 500MB
            versioning_enabled=True,
        )

        assert info.name == "my-bucket"
        assert info.object_count == 100
        assert info.total_size == 500 * 1024 * 1024
        assert info.versioning_enabled is True

    def test_bucket_info_defaults(self):
        """Valeurs par défaut."""
        info = BucketInfo(name="default-bucket", creation_date=datetime.now())

        assert info.object_count == 0
        assert info.total_size == 0
        assert info.versioning_enabled is False


# ============================================================================
# Tests UploadResult Dataclass
# ============================================================================
class TestUploadResult:
    """Tests pour la dataclass UploadResult."""

    def test_create_success_result(self):
        """Résultat de téléversement réussi."""
        result = UploadResult(
            success=True,
            bucket="uploads",
            key="files/document.pdf",
            etag="xyz789",
            version_id="v1",
            size=5000,
            url="https://s3.example.com/uploads/files/document.pdf",
        )

        assert result.success is True
        assert result.bucket == "uploads"
        assert result.key == "files/document.pdf"
        assert result.etag == "xyz789"
        assert result.error is None

    def test_create_failure_result(self):
        """Résultat de téléversement échoué."""
        result = UploadResult(
            success=False,
            bucket="uploads",
            key="files/large.zip",
            error="File too large: 5GB exceeds limit",
        )

        assert result.success is False
        assert result.error == "File too large: 5GB exceeds limit"
        assert result.etag is None
        assert result.url is None


# ============================================================================
# Tests StorageAnalytics Dataclass
# ============================================================================
class TestStorageAnalytics:
    """Tests pour la dataclass StorageAnalytics."""

    def test_create_analytics(self):
        """Création d'analytics de stockage."""
        dummy_objects = [
            S3Object(
                bucket="bucket",
                key=f"file{i}.txt",
                size=1000 * (i + 1),
                last_modified=datetime.now(),
                etag=f"etag{i}",
                content_type="text/plain",
            )
            for i in range(3)
        ]

        analytics = StorageAnalytics(
            total_buckets=5,
            total_objects=1000,
            total_size_bytes=1024 * 1024 * 1024,  # 1GB
            total_size_human="1.00 GB",
            objects_by_type={"text/plain": 500, "application/json": 300, "image/png": 200},
            size_by_bucket={"bucket1": 500 * 1024 * 1024, "bucket2": 524 * 1024 * 1024},
            largest_objects=dummy_objects,
            oldest_objects=dummy_objects,
            recent_objects=dummy_objects,
            generated_at="2024-01-01T12:00:00",
        )

        assert analytics.total_buckets == 5
        assert analytics.total_objects == 1000
        assert analytics.total_size_human == "1.00 GB"
        assert len(analytics.objects_by_type) == 3
        assert len(analytics.largest_objects) == 3


# ============================================================================
# Tests S3StorageAgent - Création
# ============================================================================
class TestS3StorageAgentBasic:
    """Tests basiques pour S3StorageAgent."""

    def test_create_agent_default(self):
        """Création avec valeurs par défaut."""
        agent = S3StorageAgent()

        assert agent.name == "S3StorageAgent"
        assert agent.agent_type == "storage"
        assert agent.endpoint == "localhost:9002"
        assert agent.is_connected is False
        assert agent.client is None

    def test_create_agent_custom(self):
        """Création avec paramètres personnalisés."""
        agent = S3StorageAgent(
            endpoint="minio.example.com:9000",
            access_key="custom_key",
            secret_key="custom_secret",
            secure=True,
            region="eu-west-1",
        )

        assert agent.endpoint == "minio.example.com:9000"
        assert agent.access_key == "custom_key"
        assert agent.secure is True
        assert agent.region == "eu-west-1"

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = S3StorageAgent()

        expected_capabilities = [
            "bucket_management",
            "file_upload",
            "file_download",
            "file_sync",
            "storage_analytics",
            "lifecycle_management",
            "presigned_urls",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_env_variables(self):
        """Configuration via variables d'environnement."""
        os.environ["MINIO_ENDPOINT"] = "env-minio:9000"
        os.environ["MINIO_ACCESS_KEY"] = "env_key"
        os.environ["MINIO_SECRET_KEY"] = "env_secret"

        agent = S3StorageAgent()

        assert agent.endpoint == "env-minio:9000"
        assert agent.access_key == "env_key"
        assert agent.secret_key == "env_secret"

        # Nettoyer
        del os.environ["MINIO_ENDPOINT"]
        del os.environ["MINIO_ACCESS_KEY"]
        del os.environ["MINIO_SECRET_KEY"]


# ============================================================================
# Tests S3StorageAgent - Connexion mockée
# ============================================================================
class TestS3StorageAgentConnection:
    """Tests de connexion avec mocks."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Connexion réussie."""
        agent = S3StorageAgent()

        with patch("src.infrastructure.agents.advanced.s3_storage_agent.MINIO_AVAILABLE", True):
            with patch("src.infrastructure.agents.advanced.s3_storage_agent.Minio") as mock_minio:
                mock_client = MagicMock()
                mock_client.list_buckets.return_value = []
                mock_minio.return_value = mock_client

                result = await agent.connect()

                assert result is True
                assert agent.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_minio_not_available(self):
        """Connexion échouée - MinIO non disponible."""
        agent = S3StorageAgent()

        with patch("src.infrastructure.agents.advanced.s3_storage_agent.MINIO_AVAILABLE", False):
            result = await agent.connect()

            assert result is False
            assert agent.is_connected is False


# ============================================================================
# Tests S3StorageAgent - Cache
# ============================================================================
class TestS3StorageAgentCache:
    """Tests du système de cache."""

    def test_empty_cache(self):
        """Cache vide au départ."""
        agent = S3StorageAgent()

        assert agent._bucket_cache == {}
        assert agent._cache_time == {}

    def test_cache_ttl(self):
        """TTL du cache."""
        agent = S3StorageAgent()
        assert agent._cache_ttl == 300  # 5 minutes

    def test_cache_bucket_info(self):
        """Mise en cache des infos bucket."""
        agent = S3StorageAgent()

        bucket_info = BucketInfo(name="cached-bucket", creation_date=datetime.now())

        agent._bucket_cache["cached-bucket"] = bucket_info
        agent._cache_time["cached-bucket"] = datetime.now()

        assert "cached-bucket" in agent._bucket_cache


# ============================================================================
# Tests conditionnels - MinIO disponible
# ============================================================================
class TestS3StorageAgentConditional:
    """Tests conditionnels si MinIO est disponible."""

    @pytest.fixture
    def minio_available(self):
        """Vérifie si MinIO est disponible."""
        try:
            from minio import Minio

            client = Minio(
                "localhost:9002", access_key="tawiza", secret_key="changeme", secure=False
            )
            list(client.list_buckets())
            return True
        except Exception:
            return False

    @pytest.mark.asyncio
    async def test_real_connection(self, minio_available):
        """Test avec MinIO réel."""
        if not minio_available:
            pytest.skip("MinIO non disponible")

        agent = S3StorageAgent()
        result = await agent.connect()

        assert result is True
        assert agent.is_connected is True


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestS3StorageAgentEdgeCases:
    """Tests des cas limites."""

    def test_upload_result_no_version(self):
        """Résultat sans versioning."""
        result = UploadResult(success=True, bucket="simple", key="file.txt", etag="abc", size=100)

        assert result.version_id is None
        assert result.url is None

    def test_large_object(self):
        """Objet de grande taille."""
        obj = S3Object(
            bucket="large-files",
            key="huge-dataset.parquet",
            size=10 * 1024 * 1024 * 1024,  # 10GB
            last_modified=datetime.now(),
            etag="large123",
            content_type="application/octet-stream",
        )

        assert obj.size == 10 * 1024 * 1024 * 1024

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = S3StorageAgent(endpoint="minio1.local:9000")
        agent2 = S3StorageAgent(endpoint="minio2.local:9000")

        assert agent1.endpoint != agent2.endpoint

    def test_analytics_with_empty_data(self):
        """Analytics avec données vides."""
        analytics = StorageAnalytics(
            total_buckets=0,
            total_objects=0,
            total_size_bytes=0,
            total_size_human="0 B",
            objects_by_type={},
            size_by_bucket={},
            largest_objects=[],
            oldest_objects=[],
            recent_objects=[],
            generated_at="2024-01-01T00:00:00",
        )

        assert analytics.total_buckets == 0
        assert analytics.total_objects == 0
        assert len(analytics.largest_objects) == 0
