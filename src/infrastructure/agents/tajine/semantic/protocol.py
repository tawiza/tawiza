"""Vector store protocol for semantic search.

Defines the abstract interface that both PGVector and Qdrant adapters implement,
enabling fallback between vector stores.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SemanticResult:
    """Result from a semantic search query.

    Attributes:
        id: Unique document identifier
        content: The text content that matched
        score: Similarity score (0-1, higher = more similar)
        metadata: Additional metadata (territory, source, etc.)
        source_store: Which vector store provided this result
    """
    id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    source_store: str = "unknown"
    fetched_at: datetime = field(default_factory=datetime.now)

    def to_raw_data_dict(self) -> dict[str, Any]:
        """Convert to dict compatible with RawData construction."""
        return {
            "source": self.metadata.get("source", "semantic"),
            "content": {"text": self.content, "semantic_score": self.score},
            "url": f"semantic://{self.source_store}/{self.id}",
            "quality_hint": self.score,
            "metadata": self.metadata,
        }


class VectorStoreProtocol(ABC):
    """Abstract protocol for vector store implementations.

    Implementations:
    - PGVectorAdapter: PostgreSQL + pgvector (primary)
    - QdrantAdapter: Qdrant vector database (fallback)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this vector store for logging."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the vector store."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connection to the vector store."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the vector store is available.

        Returns:
            True if healthy and ready, False otherwise
        """
        ...

    @abstractmethod
    async def index(
        self,
        doc_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a document with its embedding.

        Args:
            doc_id: Unique identifier for the document
            content: Text content to store
            embedding: Pre-computed embedding vector
            metadata: Optional metadata (territory, source, etc.)
        """
        ...

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        score_threshold: float = 0.5,
    ) -> list[SemanticResult]:
        """Search for similar documents.

        Args:
            query_embedding: Embedding vector of the query
            limit: Maximum number of results
            metadata_filter: Filter by metadata fields
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of SemanticResult ordered by descending similarity
        """
        ...

    @abstractmethod
    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID.

        Args:
            doc_id: Document identifier to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def count(self, metadata_filter: dict[str, Any] | None = None) -> int:
        """Count documents in the store.

        Args:
            metadata_filter: Optional filter to count subset

        Returns:
            Number of documents matching filter
        """
        ...
