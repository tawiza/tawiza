"""
Embedding Service - Orchestrates document chunking, embedding generation, and vector storage
Integrates PGVectorClient with Ollama (direct or via LitServe) for end-to-end semantic search

Performance Modes:
- Direct Ollama: Standard performance
- LitServe: 2-5x faster with automatic batching (Phase 3 optimization)
"""

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any, Union

from src.infrastructure.ml.ollama.ollama_adapter import OllamaAdapter
from src.infrastructure.vector_store import PGVectorClient, SearchResult

# Optional LitServe support (Phase 3)
try:
    from src.infrastructure.llm.litserve_client import LitServeClient

    LITSERVE_AVAILABLE = True
except ImportError:
    LITSERVE_AVAILABLE = False
    LitServeClient = None


@dataclass
class Document:
    """Document to be embedded"""

    id: str
    content: str
    metadata: dict[str, Any] | None = None
    source: str | None = None


@dataclass
class Chunk:
    """Document chunk with embedding"""

    document_id: str
    chunk_id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None
    source: str | None = None


class EmbeddingService:
    """
    High-level service for document embedding and semantic search

    Features:
    - Document chunking with overlap
    - Batch embedding generation with Ollama
    - Vector storage with pgvector
    - Semantic search with metadata filtering
    - Deduplication by content hash

    Usage:
        service = EmbeddingService(
            vector_client=pgvector_client,
            ollama_adapter=ollama_adapter
        )

        # Index documents
        await service.index_documents([
            Document(id="doc1", content="Long text...", metadata={"category": "docs"})
        ])

        # Search
        results = await service.search("query text", limit=10)
    """

    def __init__(
        self,
        vector_client: PGVectorClient,
        ollama_adapter: Union[OllamaAdapter, "LitServeClient"] | None = None,
        embedding_model: str = "nomic-embed-text",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        embedding_dim: int = 768,
        use_litserve: bool = False,
        litserve_url: str = "http://localhost:8001",
    ):
        """
        Initialize embedding service

        Args:
            vector_client: PGVectorClient for vector storage
            ollama_adapter: OllamaAdapter or LitServeClient for embedding generation
                           If None and use_litserve=True, creates LitServeClient automatically
                           If None and use_litserve=False, creates OllamaAdapter automatically
            embedding_model: Ollama model for embeddings (default: nomic-embed-text)
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Tokens to overlap between chunks
            embedding_dim: Embedding dimension (must match model)
            use_litserve: If True, use LitServe for 2-5x performance (Phase 3)
            litserve_url: LitServe server URL (when use_litserve=True)
        """
        self.vector_client = vector_client
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_dim = embedding_dim
        self.use_litserve = use_litserve

        # Initialize LLM client
        if ollama_adapter is not None:
            # Use provided adapter
            self.ollama = ollama_adapter
            if isinstance(ollama_adapter, LitServeClient if LITSERVE_AVAILABLE else type(None)):
                self.use_litserve = True
        elif use_litserve and LITSERVE_AVAILABLE:
            # Create LitServe client (Phase 3 optimization)
            self.ollama = LitServeClient(base_url=litserve_url)
            print(f"✅ LitServe enabled for {chunk_size}x faster batch embedding generation")
        else:
            # Create standard Ollama adapter
            from src.infrastructure.config.settings import get_settings

            settings = get_settings()
            self.ollama = OllamaAdapter(base_url=settings.ollama.base_url)
            if use_litserve and not LITSERVE_AVAILABLE:
                print("⚠️  LitServe requested but not available, using standard Ollama")

    async def index_document(self, document: Document, generate_embeddings: bool = True) -> int:
        """
        Index a single document

        Args:
            document: Document to index
            generate_embeddings: If True, generate embeddings; if False, just chunk

        Returns:
            Number of chunks created
        """
        # Chunk document
        chunks = self._chunk_document(document)

        # Generate embeddings if requested
        if generate_embeddings:
            contents = [chunk.content for chunk in chunks]
            embeddings = await self._generate_embeddings_batch(contents)

            for chunk, embedding in zip(chunks, embeddings, strict=False):
                chunk.embedding = embedding

        # Store in vector database
        chunk_count = 0
        for chunk in chunks:
            if chunk.embedding:
                await self.vector_client.insert_embedding(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    embedding=chunk.embedding,
                    metadata=chunk.metadata,
                    source=chunk.source,
                )
                chunk_count += 1

        return chunk_count

    async def index_documents(
        self, documents: list[Document], batch_size: int = 10, show_progress: bool = True
    ) -> dict[str, int]:
        """
        Index multiple documents

        Args:
            documents: List of documents to index
            batch_size: Number of documents to process in parallel
            show_progress: Print progress messages

        Returns:
            Dict with stats: total_documents, total_chunks, etc.
        """
        total_chunks = 0
        processed = 0

        # Process in batches to avoid overwhelming Ollama
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            # Process batch in parallel
            tasks = [self.index_document(doc) for doc in batch]
            chunk_counts = await asyncio.gather(*tasks)

            total_chunks += sum(chunk_counts)
            processed += len(batch)

            if show_progress:
                print(f"Indexed {processed}/{len(documents)} documents ({total_chunks} chunks)")

        return {
            "total_documents": len(documents),
            "total_chunks": total_chunks,
            "avg_chunks_per_doc": total_chunks / len(documents) if documents else 0,
        }

    async def search(
        self,
        query: str,
        limit: int = 10,
        metadata_filter: dict[str, Any] | None = None,
        source_filter: str | None = None,
        distance_threshold: float = 1.0,
    ) -> list[SearchResult]:
        """
        Semantic search

        Args:
            query: Search query text
            limit: Number of results
            metadata_filter: Filter by metadata
            source_filter: Filter by source
            distance_threshold: Maximum distance (0-2, lower = more similar)

        Returns:
            List of SearchResult ordered by relevance
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Search vector database
        results = await self.vector_client.search(
            query_embedding=query_embedding,
            limit=limit,
            metadata_filter=metadata_filter,
            source_filter=source_filter,
            distance_threshold=distance_threshold,
        )

        return results

    async def delete_document(self, document_id: str) -> int:
        """
        Delete all chunks for a document

        Args:
            document_id: Document ID

        Returns:
            Number of chunks deleted
        """
        return await self.vector_client.delete_by_document_id(document_id)

    async def delete_source(self, source: str) -> int:
        """
        Delete all documents from a source

        Args:
            source: Source identifier

        Returns:
            Number of chunks deleted
        """
        return await self.vector_client.delete_by_source(source)

    async def get_stats(self) -> dict[str, Any]:
        """
        Get embedding database statistics

        Returns:
            Dict with stats
        """
        return await self.vector_client.get_stats()

    def _chunk_document(self, document: Document) -> list[Chunk]:
        """
        Chunk document into overlapping segments

        Args:
            document: Document to chunk

        Returns:
            List of chunks
        """
        # Simple word-based chunking (can be improved with tiktoken)
        words = document.content.split()
        chunks = []

        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i : i + self.chunk_size]
            chunk_content = " ".join(chunk_words)

            # Create chunk ID from content hash
            content_hash = hashlib.md5(chunk_content.encode(), usedforsecurity=False).hexdigest()[
                :8
            ]
            chunk_id = f"chunk_{i}_{content_hash}"

            chunks.append(
                Chunk(
                    document_id=document.id,
                    chunk_id=chunk_id,
                    content=chunk_content,
                    metadata=document.metadata,
                    source=document.source,
                )
            )

        return chunks

    async def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embedding = await self.ollama.get_embedding(model=self.embedding_model, text=text)
        return embedding

    async def _generate_embeddings_batch(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in parallel

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Generate embeddings in parallel
            tasks = [self._generate_embedding(text) for text in batch]
            batch_embeddings = await asyncio.gather(*tasks)

            embeddings.extend(batch_embeddings)

        return embeddings

    async def reindex_all(
        self,
        source: str | None = None,
        batch_size: int = 100,
        show_progress: bool = True,
        new_model: str | None = None,
    ) -> dict[str, int]:
        """
        Reindex all documents by regenerating embeddings.

        Useful after changing embedding model. Content is already stored
        in the embeddings table, so we fetch it and regenerate vectors.

        Args:
            source: Only reindex documents from this source (None = all)
            batch_size: Batch size for processing
            show_progress: Print progress messages
            new_model: Optional new embedding model to use (updates self.embedding_model)

        Returns:
            Stats dict with total_chunks, reindexed, failed, errors
        """
        # Update embedding model if specified
        if new_model:
            old_model = self.embedding_model
            self.embedding_model = new_model
            if show_progress:
                print(f"🔄 Switching embedding model: {old_model} → {new_model}")

        # Get total count for progress
        total_count = await self.vector_client.count_chunks(source)
        if show_progress:
            source_str = f" (source: {source})" if source else ""
            print(f"📊 Found {total_count} chunks to reindex{source_str}")

        if total_count == 0:
            return {"total_chunks": 0, "reindexed": 0, "failed": 0, "errors": []}

        reindexed = 0
        failed = 0
        errors = []
        offset = 0

        while True:
            # Fetch batch of chunks
            chunks = await self.vector_client.get_all_chunks(
                source=source, batch_size=batch_size, offset=offset
            )

            if not chunks:
                break

            # Generate new embeddings for this batch
            contents = [chunk.content for chunk in chunks]
            try:
                new_embeddings = await self._generate_embeddings_batch(contents)
            except Exception as e:
                error_msg = f"Batch embedding generation failed at offset {offset}: {e}"
                errors.append(error_msg)
                if show_progress:
                    print(f"❌ {error_msg}")
                failed += len(chunks)
                offset += batch_size
                continue

            # Update each chunk with new embedding
            for chunk, new_embedding in zip(chunks, new_embeddings, strict=False):
                try:
                    success = await self.vector_client.update_embedding(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        embedding=new_embedding,
                    )
                    if success:
                        reindexed += 1
                    else:
                        failed += 1
                        errors.append(f"Chunk not found: {chunk.document_id}/{chunk.chunk_id}")
                except Exception as e:
                    failed += 1
                    errors.append(f"Update failed for {chunk.chunk_id}: {e}")

            offset += batch_size

            if show_progress:
                progress = min(offset, total_count)
                pct = (progress / total_count) * 100
                print(f"  Reindexed {reindexed}/{total_count} ({pct:.1f}%)")

        if show_progress:
            print(f"✅ Reindexing complete: {reindexed} success, {failed} failed")

        return {
            "total_chunks": total_count,
            "reindexed": reindexed,
            "failed": failed,
            "errors": errors[:10] if len(errors) > 10 else errors,  # Limit error list
            "embedding_model": self.embedding_model,
        }
