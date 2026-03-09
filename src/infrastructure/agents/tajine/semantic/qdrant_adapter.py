"""Qdrant adapter implementing VectorStoreProtocol.

Fallback vector store when PGVector is unavailable.
Enhances the existing stub in src/infrastructure/storage/qdrant/.
"""
import uuid
from typing import Any

from loguru import logger

from src.infrastructure.agents.tajine.semantic.protocol import (
    SemanticResult,
    VectorStoreProtocol,
)


class QdrantAdapter(VectorStoreProtocol):
    """Adapter for Qdrant as fallback vector store.

    Uses qdrant-client library for communication with Qdrant server.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "tajine_documents",
        vector_size: int = 768,
    ):
        """Initialize Qdrant adapter.

        Args:
            host: Qdrant server host
            port: Qdrant server port
            collection_name: Name of the collection
            vector_size: Dimension of embeddings
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._client = None
        self._connected = False

    @property
    def name(self) -> str:
        return "qdrant"

    async def connect(self) -> None:
        """Initialize connection to Qdrant."""
        if self._connected:
            return

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._client = QdrantClient(host=self.host, port=self.port)

            # Ensure collection exists
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")

            self._connected = True
            logger.info(f"Qdrant adapter connected to {self.host}:{self.port}")

        except ImportError:
            logger.error("qdrant-client not installed. Install with: pip install qdrant-client")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    async def close(self) -> None:
        """Close connection to Qdrant."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("Qdrant adapter disconnected")

    async def health_check(self) -> bool:
        """Check if Qdrant is available."""
        if not self._connected:
            try:
                await self.connect()
            except Exception:
                return False

        try:
            # Simple health check - get collection info
            self._client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

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

        from qdrant_client.models import PointStruct

        # Generate UUID from doc_id for Qdrant's point ID
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))

        payload = {
            "doc_id": doc_id,
            "content": content,
            **(metadata or {}),
        }

        self._client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
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

        # Build filter if provided
        query_filter = None
        if metadata_filter:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in metadata_filter.items()
            ]
            query_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
        )

        semantic_results = []
        for hit in results:
            semantic_results.append(SemanticResult(
                id=hit.payload.get("doc_id", str(hit.id)),
                content=hit.payload.get("content", ""),
                score=hit.score,
                metadata={k: v for k, v in hit.payload.items() if k not in ("doc_id", "content")},
                source_store="qdrant",
            ))

        return semantic_results

    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        if not self._connected:
            await self.connect()

        try:
            from qdrant_client.models import PointIdsList

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[point_id]),
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to delete {doc_id} from Qdrant: {e}")
            return False

    async def count(self, metadata_filter: dict[str, Any] | None = None) -> int:
        """Count documents in the store."""
        if not self._connected:
            await self.connect()

        try:
            info = self._client.get_collection(self.collection_name)
            return info.points_count
        except Exception:
            return 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
