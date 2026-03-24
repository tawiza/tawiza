"""Tests for SemanticSearchService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.semantic.protocol import SemanticResult
from src.infrastructure.agents.tajine.semantic.service import SemanticSearchService


@pytest.fixture
def mock_primary_store():
    """Create mock primary vector store."""
    store = MagicMock()
    store.name = "pgvector"
    store.connect = AsyncMock()
    store.close = AsyncMock()
    store.health_check = AsyncMock(return_value=True)
    store.index = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            SemanticResult(
                id="doc1",
                content="Test result",
                score=0.8,
                source_store="pgvector",
            )
        ]
    )
    return store


@pytest.fixture
def mock_fallback_store():
    """Create mock fallback vector store."""
    store = MagicMock()
    store.name = "qdrant"
    store.connect = AsyncMock()
    store.close = AsyncMock()
    store.health_check = AsyncMock(return_value=True)
    store.index = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            SemanticResult(
                id="doc2",
                content="Fallback result",
                score=0.7,
                source_store="qdrant",
            )
        ]
    )
    return store


class TestSemanticSearchService:
    """Tests for SemanticSearchService."""

    @pytest.mark.asyncio
    async def test_connect_primary(self, mock_primary_store):
        """Test connecting to primary store."""
        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=None,
        )

        await service.connect()

        mock_primary_store.connect.assert_called_once()
        assert service._initialized
        assert service._active_store == "primary"

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self, mock_primary_store, mock_fallback_store):
        """Test automatic fallback when primary fails."""
        mock_primary_store.connect.side_effect = Exception("Connection failed")

        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )

        await service.connect()

        mock_fallback_store.connect.assert_called_once()
        assert service._active_store == "fallback"

    @pytest.mark.asyncio
    async def test_close(self, mock_primary_store, mock_fallback_store):
        """Test closing all connections."""
        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )
        await service.connect()
        await service.close()

        mock_primary_store.close.assert_called_once()
        mock_fallback_store.close.assert_called_once()
        assert not service._initialized

    @pytest.mark.asyncio
    async def test_search_uses_primary(self, mock_primary_store, mock_fallback_store):
        """Test search uses primary store when available."""
        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )
        await service.connect()

        # Mock embedding generation
        with patch.object(service, "_get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            results = await service.search("test query", limit=5)

            assert len(results) == 1
            assert results[0].content == "Test result"
            mock_primary_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_fallback_on_error(self, mock_primary_store, mock_fallback_store):
        """Test search falls back on primary error."""
        mock_primary_store.search.side_effect = Exception("Search failed")

        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )
        service._initialized = True
        service._active_store = "primary"

        with patch.object(service, "_get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            results = await service.search("test query")

            assert len(results) == 1
            assert results[0].content == "Fallback result"
            assert service._active_store == "fallback"

    @pytest.mark.asyncio
    async def test_index(self, mock_primary_store):
        """Test indexing a document."""
        service = SemanticSearchService(primary=mock_primary_store)
        service._initialized = True
        service._active_store = "primary"

        with patch.object(service, "_get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            await service.index("doc1", "test content", {"territory": "31"})

            mock_primary_store.index.assert_called_once()
            call_args = mock_primary_store.index.call_args
            assert call_args.kwargs["doc_id"] == "doc1"
            assert call_args.kwargs["content"] == "test content"

    @pytest.mark.asyncio
    async def test_index_raw_data(self, mock_primary_store):
        """Test indexing RawData from DataHunter."""
        service = SemanticSearchService(primary=mock_primary_store)
        service._initialized = True
        service._active_store = "primary"

        raw_data = RawData(
            source="sirene",
            content={"text": "Company info", "territory": "31"},
            url="https://api.sirene.fr/companies/123",
            fetched_at=datetime.now(),
            quality_hint=0.8,
        )

        with patch.object(service, "_get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            await service.index_raw_data(raw_data)

            mock_primary_store.index.assert_called_once()
            call_args = mock_primary_store.index.call_args
            assert "sirene:" in call_args.kwargs["doc_id"]
            assert call_args.kwargs["metadata"]["source"] == "sirene"
            assert call_args.kwargs["metadata"]["territory"] == "31"

    @pytest.mark.asyncio
    async def test_search_for_hunt(self, mock_primary_store):
        """Test search_for_hunt returns RawData list."""
        service = SemanticSearchService(primary=mock_primary_store)
        service._initialized = True
        service._active_store = "primary"

        with patch.object(service, "_get_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768

            results = await service.search_for_hunt("BTP Toulouse", territory="31")

            assert len(results) == 1
            assert isinstance(results[0], RawData)
            assert results[0].source.startswith("semantic:")

    def test_active_store_property(self, mock_primary_store, mock_fallback_store):
        """Test active_store property."""
        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )
        service._active_store = "primary"

        assert service.active_store == "pgvector"

        service._active_store = "fallback"
        assert service.active_store == "qdrant"

    @pytest.mark.asyncio
    async def test_health_check(self, mock_primary_store, mock_fallback_store):
        """Test health check for all stores."""
        service = SemanticSearchService(
            primary=mock_primary_store,
            fallback=mock_fallback_store,
        )

        health = await service.health_check()

        assert health["pgvector"] is True
        assert health["qdrant"] is True

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_primary_store):
        """Test async context manager usage."""
        service = SemanticSearchService(primary=mock_primary_store)

        async with service as s:
            assert s._initialized
            assert s is service

        mock_primary_store.close.assert_called_once()
