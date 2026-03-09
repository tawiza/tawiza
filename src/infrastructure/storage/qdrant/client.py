"""Qdrant vector store client."""
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from qdrant_client import QdrantClient as QdrantBaseClient
from qdrant_client.models import Distance, PointStruct, VectorParams


@dataclass
class QdrantConfig:
    """Qdrant configuration."""
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "tawiza_documents"
    vector_size: int = 1024  # mxbai-embed-large dimension
    distance: Distance = field(default=Distance.COSINE)


class QdrantClient:
    """Client for Qdrant vector database."""

    def __init__(self, config: QdrantConfig | None = None) -> None:
        self.config = config or QdrantConfig()
        self._client = QdrantBaseClient(
            host=self.config.host,
            port=self.config.port
        )
        logger.info(f"Qdrant client initialized: {self.config.host}:{self.config.port}")

    async def ensure_collection(self) -> None:
        """Ensure collection exists, create if not."""
        if not self._client.collection_exists(self.config.collection_name):
            self._client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=self.config.vector_size,
                    distance=self.config.distance
                )
            )
            logger.info(f"Created collection: {self.config.collection_name}")

    async def upsert(
        self,
        id: str,
        vector: list[float],
        payload: dict[str, Any]
    ) -> None:
        """Insert or update a vector."""
        self._client.upsert(
            collection_name=self.config.collection_name,
            points=[PointStruct(id=id, vector=vector, payload=payload)]
        )

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        filter_conditions: dict | None = None
    ) -> list[dict[str, Any]]:
        """Search for similar vectors."""
        results = self._client.search(
            collection_name=self.config.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=filter_conditions
        )
        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]
