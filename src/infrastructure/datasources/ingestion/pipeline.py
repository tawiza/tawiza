"""Document ingestion pipeline."""

import uuid
from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.infrastructure.datasources.ingestion.chunker import TextChunker
from src.infrastructure.storage.qdrant import EmbeddingsService, QdrantClient


@dataclass
class IngestionConfig:
    """Ingestion pipeline configuration."""

    chunk_size: int = 512
    chunk_overlap: int = 50


class IngestionPipeline:
    """Pipeline for ingesting documents into Qdrant."""

    def __init__(
        self,
        config: IngestionConfig | None = None,
        qdrant: QdrantClient | None = None,
        embeddings: EmbeddingsService | None = None,
    ) -> None:
        self.config = config or IngestionConfig()
        self.chunker = TextChunker(
            chunk_size=self.config.chunk_size, overlap=self.config.chunk_overlap
        )
        self._qdrant = qdrant
        self._embeddings = embeddings

    async def _get_qdrant(self) -> QdrantClient:
        if self._qdrant is None:
            self._qdrant = QdrantClient()
            await self._qdrant.ensure_collection()
        return self._qdrant

    async def _get_embeddings(self) -> EmbeddingsService:
        if self._embeddings is None:
            self._embeddings = EmbeddingsService()
        return self._embeddings

    async def ingest(self, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Ingest document content into vector store."""
        chunks = self.chunker.chunk(content)
        chunk_ids = []

        qdrant = await self._get_qdrant()
        embeddings_service = await self._get_embeddings()

        for i, chunk in enumerate(chunks):
            chunk_id = f"{metadata.get('evaluation_id', 'unknown')}-{uuid.uuid4().hex[:8]}"
            embedding = await embeddings_service.embed(chunk)

            await qdrant.upsert(
                id=chunk_id, vector=embedding, payload={**metadata, "chunk_index": i, "text": chunk}
            )
            chunk_ids.append(chunk_id)

        logger.info(f"Ingested {len(chunks)} chunks for {metadata.get('source', 'unknown')}")

        return {"chunk_ids": chunk_ids, "chunk_count": len(chunks)}
