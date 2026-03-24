"""PGVector adapter implementing VectorStoreProtocol.

Wraps the existing PGVectorClient to provide a unified interface
for semantic search in TAJINE.
"""

import os
from typing import Any

from loguru import logger

from src.infrastructure.agents.tajine.semantic.protocol import (
    SemanticResult,
    VectorStoreProtocol,
)


class PGVectorAdapter(VectorStoreProtocol):
    """Adapter for PostgreSQL + pgvector as primary vector store.

    Uses the existing PGVectorClient infrastructure.
    """

    def __init__(
        self,
        dsn: str | None = None,
        embedding_dim: int = 768,
    ):
        """Initialize PGVector adapter.

        Args:
            dsn: PostgreSQL connection string. Defaults to settings.
            embedding_dim: Dimension of embeddings (768 for nomic-embed-text)
        """
        self.dsn = dsn
        self.embedding_dim = embedding_dim
        self._client = None
        self._connected = False

    @property
    def name(self) -> str:
        return "pgvector"

    async def connect(self) -> None:
        """Initialize connection pool."""
        if self._connected:
            return

        from src.infrastructure.config.settings import settings
        from src.infrastructure.vector_store.pgvector_client import PGVectorClient

        dsn = self.dsn or getattr(settings, "vectordb_url", None)
        if not dsn:
            dsn = os.getenv("DATABASE_URL", "postgresql://localhost:5433/tawiza")
            logger.warning(f"No vectordb_url in settings, using default: {dsn}")

        self._client = PGVectorClient(dsn, self.embedding_dim)
        try:
            await self._client.connect()
            self._connected = True
            logger.info(f"PGVector adapter connected to {dsn[:30]}...")
        except Exception as e:
            logger.error(f"Failed to connect to PGVector: {e}")
            raise

    async def close(self) -> None:
        """Close connection pool."""
        if self._client and self._connected:
            await self._client.close()
            self._connected = False
            logger.info("PGVector adapter disconnected")

    async def health_check(self) -> bool:
        """Check if PGVector is available."""
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return False
        return self._connected

    async def index(
        self,
        doc_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a document with its embedding."""
        if not self._connected:
            await self.connect()

        # PGVectorClient uses document_id + chunk_id
        # We'll use doc_id as both for single-chunk documents
        await self._client.insert_embedding(
            document_id=doc_id,
            chunk_id="0",  # Single chunk
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            source=metadata.get("source", "tajine") if metadata else "tajine",
        )

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        score_threshold: float = 0.5,
    ) -> list[SemanticResult]:
        """Search for similar documents."""
        if not self._connected:
            await self.connect()

        # PGVector uses distance (0-2), we convert threshold to distance
        # score 0.5 -> distance 1.0 (cosine distance)
        distance_threshold = 2.0 * (1.0 - score_threshold)

        results = await self._client.search(
            query_embedding=query_embedding,
            limit=limit,
            metadata_filter=metadata_filter,
            distance_threshold=distance_threshold,
        )

        # Convert SearchResult to SemanticResult
        semantic_results = []
        for r in results:
            # Convert distance (0-2) back to score (1-0)
            score = 1.0 - (r.distance / 2.0)
            if score >= score_threshold:
                semantic_results.append(
                    SemanticResult(
                        id=r.document_id,
                        content=r.content,
                        score=score,
                        metadata=r.metadata or {},
                        source_store="pgvector",
                    )
                )

        return semantic_results

    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if not self._connected:
            await self.connect()

        try:
            await self._client.delete_by_document_id(doc_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete {doc_id}: {e}")
            return False

    async def count(self, metadata_filter: dict[str, Any] | None = None) -> int:
        """Count documents in the store."""
        if not self._connected:
            await self.connect()

        try:
            stats = await self._client.get_stats()
            return stats.get("total_embeddings", 0)
        except Exception:
            return 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
