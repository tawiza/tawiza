"""Semantic Search Service for TAJINE.

High-level facade providing semantic search with automatic fallback
between primary (pgvector) and fallback (Qdrant) vector stores.
"""
import os
from typing import Any

from loguru import logger

from src.infrastructure.agents.tajine.core.types import RawData
from src.infrastructure.agents.tajine.semantic.protocol import (
    SemanticResult,
    VectorStoreProtocol,
)


class SemanticSearchService:
    """Semantic search service with automatic fallback.

    Features:
    - Primary/fallback vector store pattern
    - Automatic failover on primary failure
    - Embedding generation via Ollama
    - Integration with TAJINE DataHunter

    Usage:
        service = SemanticSearchService()
        await service.connect()

        # Search
        results = await service.search("entreprises BTP Toulouse", limit=5)

        # Index territorial data
        await service.index_raw_data(raw_data)

        await service.close()
    """

    def __init__(
        self,
        primary: VectorStoreProtocol | None = None,
        fallback: VectorStoreProtocol | None = None,
        ollama_url: str | None = None,
        embedding_model: str = "nomic-embed-text",
    ):
        """Initialize semantic search service.

        Args:
            primary: Primary vector store (defaults to PGVectorAdapter)
            fallback: Fallback vector store (defaults to QdrantAdapter)
            ollama_url: Ollama server URL for embeddings
            embedding_model: Model to use for embeddings
        """
        self.primary = primary
        self.fallback = fallback
        self.ollama_url = ollama_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.embedding_model = embedding_model
        self._active_store: str = "primary"
        self._initialized = False

    async def connect(self) -> None:
        """Initialize vector stores and embedding service."""
        if self._initialized:
            return

        # Lazy import adapters
        if self.primary is None:
            from src.infrastructure.agents.tajine.semantic.pgvector_adapter import PGVectorAdapter
            self.primary = PGVectorAdapter()

        if self.fallback is None:
            try:
                from src.infrastructure.agents.tajine.semantic.qdrant_adapter import QdrantAdapter
                self.fallback = QdrantAdapter()
            except ImportError:
                logger.warning("Qdrant not available, running without fallback")
                self.fallback = None

        # Connect primary
        try:
            await self.primary.connect()
            self._active_store = "primary"
            logger.info(f"Semantic search using primary: {self.primary.name}")
        except Exception as e:
            logger.warning(f"Primary vector store failed: {e}")
            if self.fallback:
                await self.fallback.connect()
                self._active_store = "fallback"
                logger.info(f"Semantic search using fallback: {self.fallback.name}")
            else:
                raise

        self._initialized = True

    async def close(self) -> None:
        """Close all connections."""
        if self.primary:
            await self.primary.close()
        if self.fallback:
            await self.fallback.close()
        self._initialized = False

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using Ollama."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.embedding_model, "input": text},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            embs = data.get("embeddings", [[]])
            return embs[0] if embs else []

    async def search(
        self,
        query: str,
        limit: int = 10,
        territory: str | None = None,
        source_filter: str | None = None,
        score_threshold: float = 0.5,
    ) -> list[SemanticResult]:
        """Search for semantically similar documents.

        Args:
            query: Search query text
            limit: Maximum results to return
            territory: Filter by territory (department code)
            source_filter: Filter by data source (sirene, bodacc, etc.)
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of SemanticResult ordered by descending similarity
        """
        if not self._initialized:
            await self.connect()

        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        # Build metadata filter
        metadata_filter = {}
        if territory:
            metadata_filter["territory"] = territory
        if source_filter:
            metadata_filter["source"] = source_filter

        # Try primary first
        store = self.primary if self._active_store == "primary" else self.fallback

        try:
            results = await store.search(
                query_embedding=query_embedding,
                limit=limit,
                metadata_filter=metadata_filter if metadata_filter else None,
                score_threshold=score_threshold,
            )
            return results

        except Exception as e:
            logger.warning(f"Search failed on {store.name}: {e}")

            # Try fallback if available
            if self.fallback and store != self.fallback:
                try:
                    results = await self.fallback.search(
                        query_embedding=query_embedding,
                        limit=limit,
                        metadata_filter=metadata_filter if metadata_filter else None,
                        score_threshold=score_threshold,
                    )
                    self._active_store = "fallback"
                    return results
                except Exception as e2:
                    logger.error(f"Fallback also failed: {e2}")

            return []

    async def index(
        self,
        doc_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a document for semantic search.

        Args:
            doc_id: Unique document identifier
            content: Text content to index
            metadata: Optional metadata (territory, source, etc.)
        """
        if not self._initialized:
            await self.connect()

        # Generate embedding
        embedding = await self._get_embedding(content)

        # Index in active store
        store = self.primary if self._active_store == "primary" else self.fallback

        try:
            await store.index(
                doc_id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to index {doc_id}: {e}")
            raise

    async def index_raw_data(self, data: RawData) -> None:
        """Index RawData from TAJINE DataHunter.

        Args:
            data: RawData object from hunt results
        """
        doc_id = f"{data.source}:{data.url}"

        # Extract text content
        if isinstance(data.content, dict):
            content = str(data.content.get("text", data.content))
        else:
            content = str(data.content)

        # Build metadata
        metadata = {
            "source": data.source,
            "url": data.url,
            "fetched_at": data.fetched_at.isoformat() if data.fetched_at else None,
            "quality_hint": data.quality_hint,
        }

        # Add territory if available in content
        if isinstance(data.content, dict):
            if territory := data.content.get("territory"):
                metadata["territory"] = territory
            if department := data.content.get("department"):
                metadata["territory"] = department

        await self.index(doc_id, content, metadata)

    async def search_for_hunt(
        self,
        query: str,
        territory: str | None = None,
        limit: int = 5,
    ) -> list[RawData]:
        """Search and return results as RawData for DataHunter integration.

        Args:
            query: Search query
            territory: Filter by territory
            limit: Maximum results

        Returns:
            List of RawData compatible with HuntResult
        """
        results = await self.search(
            query=query,
            limit=limit,
            territory=territory,
            score_threshold=0.5,
        )

        raw_data_list = []
        for result in results:
            raw_data_list.append(RawData(
                source=f"semantic:{result.source_store}",
                content={"text": result.content, "semantic_score": result.score},
                url=f"semantic://{result.source_store}/{result.id}",
                fetched_at=result.fetched_at,
                quality_hint=result.score,
            ))

        return raw_data_list

    @property
    def active_store(self) -> str:
        """Get the name of the currently active store."""
        if self._active_store == "primary" and self.primary:
            return self.primary.name
        elif self.fallback:
            return self.fallback.name
        return "none"

    async def health_check(self) -> dict[str, bool]:
        """Check health of all vector stores.

        Returns:
            Dict with store names and their health status
        """
        health = {}

        if self.primary:
            health[self.primary.name] = await self.primary.health_check()

        if self.fallback:
            health[self.fallback.name] = await self.fallback.health_check()

        return health

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
