"""Semantic search module for TAJINE.

Provides vector-based semantic search with automatic failover
between primary (pgvector) and fallback (Qdrant) vector stores.

Components:
- VectorStoreProtocol: Abstract interface for vector stores
- SemanticResult: Search result dataclass
- PGVectorAdapter: PostgreSQL + pgvector adapter
- QdrantAdapter: Qdrant vector database adapter
- SemanticSearchService: High-level facade with fallback

Usage:
    from src.infrastructure.agents.tajine.semantic import SemanticSearchService

    async with SemanticSearchService() as service:
        results = await service.search("entreprises BTP Toulouse", limit=5)
        for r in results:
            print(f"{r.id}: {r.score:.2f}")
"""

from src.infrastructure.agents.tajine.semantic.protocol import (
    SemanticResult,
    VectorStoreProtocol,
)
from src.infrastructure.agents.tajine.semantic.service import SemanticSearchService

# Lazy imports for adapters (they have heavy dependencies)
__all__ = [
    "VectorStoreProtocol",
    "SemanticResult",
    "SemanticSearchService",
    # Adapters available via direct import:
    # from src.infrastructure.agents.tajine.semantic.pgvector_adapter import PGVectorAdapter
    # from src.infrastructure.agents.tajine.semantic.qdrant_adapter import QdrantAdapter
]
