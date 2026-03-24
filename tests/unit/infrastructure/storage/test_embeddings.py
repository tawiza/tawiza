"""Tests for embeddings service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.storage.qdrant.embeddings import EmbeddingsConfig, EmbeddingsService


class TestEmbeddingsConfig:
    """Test Embeddings configuration."""

    def test_config_defaults(self):
        """Test default configuration."""
        config = EmbeddingsConfig()
        assert config.ollama_url == "http://localhost:11434"
        assert config.model == "nomic-embed-text"


class TestEmbeddingsService:
    """Test embeddings generation."""

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test text embedding generation."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            service = EmbeddingsService()
            embedding = await service.embed("test text")

            assert len(embedding) == 768
            assert all(isinstance(x, float) for x in embedding)
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Test batch embedding."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock multiple responses
            mock_response1 = MagicMock()
            mock_response1.json.return_value = {"embedding": [0.1] * 768}
            mock_response1.raise_for_status = MagicMock()

            mock_response2 = MagicMock()
            mock_response2.json.return_value = {"embedding": [0.2] * 768}
            mock_response2.raise_for_status = MagicMock()

            mock_client.post.side_effect = [mock_response1, mock_response2]

            service = EmbeddingsService()
            embeddings = await service.embed_batch(["text1", "text2"])

            assert len(embeddings) == 2
            assert len(embeddings[0]) == 768
            assert len(embeddings[1]) == 768

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Test custom configuration."""
        config = EmbeddingsConfig(ollama_url="http://custom:11434", model="custom-model")
        service = EmbeddingsService(config=config)
        assert service.config.ollama_url == "http://custom:11434"
        assert service.config.model == "custom-model"
