"""Tests for Qdrant client."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.storage.qdrant.client import QdrantClient, QdrantConfig


class TestQdrantConfig:
    """Test Qdrant configuration."""

    def test_config_defaults(self):
        """Test default configuration."""
        config = QdrantConfig()
        assert config.host == "localhost"
        assert config.port == 6333
        assert config.collection_name == "tawiza_documents"
        assert config.vector_size == 768


class TestQdrantClient:
    """Test Qdrant client functionality."""

    @pytest.mark.asyncio
    async def test_create_collection(self):
        """Test collection creation."""
        with patch("src.infrastructure.storage.qdrant.client.QdrantBaseClient") as mock_qdrant:
            mock_instance = MagicMock()
            mock_qdrant.return_value = mock_instance
            mock_instance.collection_exists.return_value = False

            client = QdrantClient()
            await client.ensure_collection()

            mock_instance.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_collection_if_exists(self):
        """Test that collection is not recreated if it exists."""
        with patch("src.infrastructure.storage.qdrant.client.QdrantBaseClient") as mock_qdrant:
            mock_instance = MagicMock()
            mock_qdrant.return_value = mock_instance
            mock_instance.collection_exists.return_value = True

            client = QdrantClient()
            await client.ensure_collection()

            mock_instance.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert(self):
        """Test vector upsert."""
        with patch("src.infrastructure.storage.qdrant.client.QdrantBaseClient") as mock_qdrant:
            mock_instance = MagicMock()
            mock_qdrant.return_value = mock_instance

            client = QdrantClient()
            await client.upsert(id="test-123", vector=[0.1] * 1024, payload={"text": "test"})

            mock_instance.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search(self):
        """Test vector search."""
        with patch("src.infrastructure.storage.qdrant.client.QdrantBaseClient") as mock_qdrant:
            mock_instance = MagicMock()
            mock_qdrant.return_value = mock_instance

            # Mock search result
            mock_result = MagicMock()
            mock_result.id = "test-123"
            mock_result.score = 0.95
            mock_result.payload = {"text": "test"}
            mock_instance.search.return_value = [mock_result]

            client = QdrantClient()
            results = await client.search(query_vector=[0.1] * 1024, limit=10)

            assert len(results) == 1
            assert results[0]["id"] == "test-123"
            assert results[0]["score"] == 0.95
