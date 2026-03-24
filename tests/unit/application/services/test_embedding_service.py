"""Tests for EmbeddingService - document chunking, embedding, and reindexing."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.embedding_service import Chunk, Document, EmbeddingService
from src.infrastructure.vector_store import SearchResult


@dataclass
class MockSearchResult:
    """Mock SearchResult for testing."""

    id: int
    document_id: str
    chunk_id: str
    content: str
    distance: float
    metadata: dict
    source: str = None
    created_at: str = None


class TestEmbeddingServiceReindex:
    """Tests for reindex_all functionality."""

    @pytest.fixture
    def mock_vector_client(self):
        """Create mock PGVectorClient."""
        client = MagicMock()
        client.count_chunks = AsyncMock(return_value=3)
        client.get_all_chunks = AsyncMock()
        client.update_embedding = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_ollama_adapter(self):
        """Create mock OllamaAdapter."""
        adapter = MagicMock()
        # Return 768-dim embeddings
        adapter.get_embedding = AsyncMock(return_value=[0.1] * 768)
        return adapter

    @pytest.fixture
    def embedding_service(self, mock_vector_client, mock_ollama_adapter):
        """Create EmbeddingService with mocks."""
        return EmbeddingService(
            vector_client=mock_vector_client,
            ollama_adapter=mock_ollama_adapter,
            embedding_model="nomic-embed-text",
            embedding_dim=768,
        )

    @pytest.mark.asyncio
    async def test_reindex_all_basic(self, embedding_service, mock_vector_client):
        """Test basic reindex_all functionality."""
        # Mock chunks to reindex
        chunks = [
            MockSearchResult(
                id=1,
                document_id="doc1",
                chunk_id="chunk_0",
                content="Hello world",
                distance=0.0,
                metadata={},
            ),
            MockSearchResult(
                id=2,
                document_id="doc1",
                chunk_id="chunk_1",
                content="How are you",
                distance=0.0,
                metadata={},
            ),
            MockSearchResult(
                id=3,
                document_id="doc2",
                chunk_id="chunk_0",
                content="Goodbye",
                distance=0.0,
                metadata={},
            ),
        ]

        # First call returns chunks, second call returns empty (end of pagination)
        mock_vector_client.get_all_chunks.side_effect = [chunks, []]

        result = await embedding_service.reindex_all(show_progress=False)

        assert result["total_chunks"] == 3
        assert result["reindexed"] == 3
        assert result["failed"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_reindex_all_with_source_filter(self, embedding_service, mock_vector_client):
        """Test reindex with source filter."""
        mock_vector_client.count_chunks = AsyncMock(return_value=2)
        chunks = [
            MockSearchResult(
                id=1,
                document_id="doc1",
                chunk_id="chunk_0",
                content="Source A content",
                distance=0.0,
                metadata={},
                source="source_a",
            ),
            MockSearchResult(
                id=2,
                document_id="doc1",
                chunk_id="chunk_1",
                content="More source A",
                distance=0.0,
                metadata={},
                source="source_a",
            ),
        ]
        mock_vector_client.get_all_chunks.side_effect = [chunks, []]

        result = await embedding_service.reindex_all(source="source_a", show_progress=False)

        assert result["total_chunks"] == 2
        assert result["reindexed"] == 2
        # Verify source filter was passed
        mock_vector_client.count_chunks.assert_called_with("source_a")
        mock_vector_client.get_all_chunks.assert_called()

    @pytest.mark.asyncio
    async def test_reindex_all_empty_database(self, embedding_service, mock_vector_client):
        """Test reindex when no chunks exist."""
        mock_vector_client.count_chunks = AsyncMock(return_value=0)

        result = await embedding_service.reindex_all(show_progress=False)

        assert result["total_chunks"] == 0
        assert result["reindexed"] == 0
        assert result["failed"] == 0
        # Should not attempt to fetch chunks if count is 0
        mock_vector_client.get_all_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_reindex_all_with_new_model(self, embedding_service, mock_vector_client):
        """Test reindex with new embedding model."""
        mock_vector_client.count_chunks = AsyncMock(return_value=1)
        chunks = [
            MockSearchResult(
                id=1,
                document_id="doc1",
                chunk_id="chunk_0",
                content="Test content",
                distance=0.0,
                metadata={},
            ),
        ]
        mock_vector_client.get_all_chunks.side_effect = [chunks, []]

        original_model = embedding_service.embedding_model
        result = await embedding_service.reindex_all(
            new_model="mxbai-embed-large", show_progress=False
        )

        assert result["embedding_model"] == "mxbai-embed-large"
        assert embedding_service.embedding_model == "mxbai-embed-large"
        assert original_model != "mxbai-embed-large"

    @pytest.mark.asyncio
    async def test_reindex_all_handles_update_failure(self, embedding_service, mock_vector_client):
        """Test reindex handles chunk update failures."""
        mock_vector_client.count_chunks = AsyncMock(return_value=2)
        chunks = [
            MockSearchResult(
                id=1,
                document_id="doc1",
                chunk_id="chunk_0",
                content="Success",
                distance=0.0,
                metadata={},
            ),
            MockSearchResult(
                id=2,
                document_id="doc2",
                chunk_id="chunk_0",
                content="Failure",
                distance=0.0,
                metadata={},
            ),
        ]
        mock_vector_client.get_all_chunks.side_effect = [chunks, []]

        # First update succeeds, second fails
        mock_vector_client.update_embedding.side_effect = [True, False]

        result = await embedding_service.reindex_all(show_progress=False)

        assert result["total_chunks"] == 2
        assert result["reindexed"] == 1
        assert result["failed"] == 1
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_reindex_all_handles_embedding_error(
        self, embedding_service, mock_vector_client, mock_ollama_adapter
    ):
        """Test reindex handles embedding generation errors."""
        mock_vector_client.count_chunks = AsyncMock(return_value=2)
        chunks = [
            MockSearchResult(
                id=1,
                document_id="doc1",
                chunk_id="chunk_0",
                content="Content",
                distance=0.0,
                metadata={},
            ),
        ]
        mock_vector_client.get_all_chunks.side_effect = [chunks, []]

        # Make embedding generation fail
        mock_ollama_adapter.get_embedding.side_effect = Exception("Ollama unavailable")

        result = await embedding_service.reindex_all(show_progress=False)

        assert result["total_chunks"] == 2
        assert result["failed"] == 1
        assert "Batch embedding generation failed" in result["errors"][0]


class TestEmbeddingServiceChunking:
    """Tests for document chunking."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService with mocks."""
        mock_vector_client = MagicMock()
        mock_ollama_adapter = MagicMock()
        return EmbeddingService(
            vector_client=mock_vector_client,
            ollama_adapter=mock_ollama_adapter,
            chunk_size=10,  # Small for testing
            chunk_overlap=2,
        )

    def test_chunk_document(self, embedding_service):
        """Test document chunking with overlap."""
        doc = Document(
            id="test_doc",
            content=" ".join([f"word{i}" for i in range(25)]),
            metadata={"type": "test"},
        )

        chunks = embedding_service._chunk_document(doc)

        # Should have multiple chunks
        assert len(chunks) >= 2
        # Each chunk should have correct document_id
        assert all(c.document_id == "test_doc" for c in chunks)
        # Metadata should be preserved
        assert all(c.metadata == {"type": "test"} for c in chunks)

    def test_chunk_document_short(self, embedding_service):
        """Test chunking short document."""
        doc = Document(id="short_doc", content="Just a few words")

        chunks = embedding_service._chunk_document(doc)

        assert len(chunks) == 1
        assert chunks[0].content == "Just a few words"


class TestPGVectorClientNewMethods:
    """Tests for new PGVectorClient methods."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        pool = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock()
        pool.acquire.return_value.__aexit__ = AsyncMock()
        return pool

    @pytest.mark.asyncio
    async def test_count_chunks(self, mock_pool):
        """Test count_chunks method."""
        from src.infrastructure.vector_store import PGVectorClient

        client = PGVectorClient("postgresql://test", embedding_dim=768)
        client.pool = mock_pool

        # Mock connection and query result
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"count": 42})
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        count = await client.count_chunks()

        assert count == 42
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_chunks_with_source(self, mock_pool):
        """Test count_chunks with source filter."""
        from src.infrastructure.vector_store import PGVectorClient

        client = PGVectorClient("postgresql://test", embedding_dim=768)
        client.pool = mock_pool

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"count": 10})
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        count = await client.count_chunks(source="my_source")

        assert count == 10
        # Verify source was passed in query
        call_args = mock_conn.fetchrow.call_args
        assert "source" in call_args[0][0].lower() or "my_source" in call_args[0]
