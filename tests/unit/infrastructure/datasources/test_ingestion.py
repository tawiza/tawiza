"""Tests for document ingestion pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.datasources.ingestion.chunker import TextChunker
from src.infrastructure.datasources.ingestion.pipeline import IngestionConfig, IngestionPipeline


class TestTextChunker:
    """Test text chunking."""

    def test_chunk_short_text(self):
        """Short text should be single chunk."""
        chunker = TextChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk("This is a short text.")
        assert len(chunks) == 1
        assert chunks[0] == "This is a short text."

    def test_chunk_long_text(self):
        """Long text should be multiple chunks with overlap."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "A" * 100
        chunks = chunker.chunk(text)
        assert len(chunks) > 1
        # Check overlap exists
        assert chunks[0][-10:] == chunks[1][:10]

    def test_chunk_exact_size(self):
        """Text exactly chunk_size should be single chunk."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        text = "A" * 50
        chunks = chunker.chunk(text)
        assert len(chunks) == 1

    def test_default_config(self):
        """Test default chunker config."""
        chunker = TextChunker()
        assert chunker.chunk_size == 512
        assert chunker.overlap == 50


class TestIngestionConfig:
    """Test ingestion configuration."""

    def test_config_defaults(self):
        """Test default configuration."""
        config = IngestionConfig()
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50


class TestIngestionPipeline:
    """Test ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_document(self):
        """Test document ingestion."""
        mock_qdrant = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.embed.return_value = [0.1] * 1024

        pipeline = IngestionPipeline(qdrant=mock_qdrant, embeddings=mock_embeddings)

        result = await pipeline.ingest(
            content="Test document content for ingestion.",
            metadata={"source": "test", "evaluation_id": "eval-123"},
        )

        assert "chunk_ids" in result
        assert len(result["chunk_ids"]) > 0
        assert result["chunk_count"] >= 1
        mock_embeddings.embed.assert_called()
        mock_qdrant.upsert.assert_called()

    @pytest.mark.asyncio
    async def test_ingest_long_document(self):
        """Test ingestion of long document creates multiple chunks."""
        mock_qdrant = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_embeddings.embed.return_value = [0.1] * 1024

        config = IngestionConfig(chunk_size=100, chunk_overlap=10)
        pipeline = IngestionPipeline(config=config, qdrant=mock_qdrant, embeddings=mock_embeddings)

        # Create text longer than chunk_size
        long_content = "Test " * 100  # 500 characters

        result = await pipeline.ingest(
            content=long_content, metadata={"source": "test", "evaluation_id": "eval-456"}
        )

        assert result["chunk_count"] > 1
        assert len(result["chunk_ids"]) == result["chunk_count"]
