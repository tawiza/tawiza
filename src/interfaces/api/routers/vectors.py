"""
Vector/Embedding API Endpoints
Provides semantic search, document indexing, and vector management
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from src.application.services.embedding_service import Document, EmbeddingService
from src.infrastructure.vector_store import PGVectorClient, SearchResult


# Request/Response Models
class IndexDocumentRequest(BaseModel):
    """Request to index a document"""

    id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., min_length=1, description="Document content")
    metadata: dict[str, Any] | None = Field(default=None, description="Document metadata")
    source: str | None = Field(default=None, description="Source identifier")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "doc_123",
                "content": "This is a sample document about machine learning and AI.",
                "metadata": {"category": "documentation", "language": "en"},
                "source": "knowledge_base",
            }
        }
    )


class SearchRequest(BaseModel):
    """Request for semantic search"""

    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results")
    metadata_filter: dict[str, Any] | None = Field(default=None, description="Filter by metadata")
    source_filter: str | None = Field(default=None, description="Filter by source")
    distance_threshold: float = Field(default=1.0, ge=0.0, le=2.0, description="Maximum distance")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "What is machine learning?",
                "limit": 10,
                "metadata_filter": {"category": "documentation"},
                "distance_threshold": 0.8,
            }
        }
    )


class SearchResultResponse(BaseModel):
    """Single search result"""

    id: int
    document_id: str
    chunk_id: str
    content: str
    distance: float
    score: float  # 1 - distance, higher is better
    metadata: dict[str, Any]
    source: str | None
    created_at: datetime | None

    @classmethod
    def from_search_result(cls, result: SearchResult):
        """Convert SearchResult to response model"""
        return cls(
            id=result.id,
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            content=result.content,
            distance=result.distance,
            score=1.0 - (result.distance / 2.0),  # Normalize to 0-1
            metadata=result.metadata,
            source=result.source,
            created_at=result.created_at,
        )


class SearchResponse(BaseModel):
    """Search response with results"""

    query: str
    results: list[SearchResultResponse]
    count: int
    processing_time_ms: float


class IndexResponse(BaseModel):
    """Response after indexing document"""

    document_id: str
    chunks_created: int
    status: str = "indexed"


class StatsResponse(BaseModel):
    """Vector database statistics"""

    total_embeddings: int
    unique_documents: int
    unique_sources: int
    avg_content_length: float
    table_size: str
    latest_embedding: datetime | None
    earliest_embedding: datetime | None


class DeleteResponse(BaseModel):
    """Response after deletion"""

    deleted_count: int
    status: str = "deleted"


# Dependency injection
async def get_embedding_service() -> EmbeddingService:
    """
    Get or create EmbeddingService instance

    Automatically uses LitServe if enabled in settings (Phase 3 optimization)
    """
    # In production, this would be a singleton with proper lifecycle management
    # For now, we'll create a new instance (could be optimized with caching)

    from src.infrastructure.config.settings import get_settings

    settings = get_settings()

    # Initialize vector client
    vector_client = PGVectorClient(
        dsn=str(settings.database.url).replace("postgresql+asyncpg://", "postgresql://"),
        embedding_dim=settings.vectordb.embedding_dim,
    )
    await vector_client.connect(min_size=5, max_size=15)

    # Create service with optional LitServe optimization (Phase 3)
    service = EmbeddingService(
        vector_client=vector_client,
        ollama_adapter=None,  # Auto-created based on use_litserve setting
        embedding_model=settings.vectordb.embedding_model,
        chunk_size=settings.vectordb.chunk_size,
        chunk_overlap=settings.vectordb.chunk_overlap,
        embedding_dim=settings.vectordb.embedding_dim,
        use_litserve=settings.vectordb.use_litserve,
        litserve_url=settings.vectordb.litserve_url,
    )

    return service


# Router
router = APIRouter(prefix="/vectors", tags=["vectors"])


@router.post("/index", response_model=IndexResponse, status_code=status.HTTP_201_CREATED)
async def index_document(
    request: IndexDocumentRequest, service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Index a document for semantic search

    - **id**: Unique document identifier
    - **content**: Document text content
    - **metadata**: Optional metadata for filtering
    - **source**: Optional source identifier

    The document will be:
    1. Chunked into overlapping segments
    2. Embedded using Ollama
    3. Stored in pgvector for fast similarity search
    """
    try:
        document = Document(
            id=request.id, content=request.content, metadata=request.metadata, source=request.source
        )

        chunks_created = await service.index_document(document)

        return IndexResponse(document_id=request.id, chunks_created=chunks_created)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document: {str(e)}",
        )


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Semantic search across indexed documents

    - **query**: Natural language search query
    - **limit**: Number of results (1-100)
    - **metadata_filter**: Filter by metadata fields
    - **source_filter**: Filter by source
    - **distance_threshold**: Maximum distance (0-2, lower = more similar)

    Returns results sorted by relevance (lowest distance = most similar)
    """
    try:
        import time

        start_time = time.time()

        results = await service.search(
            query=request.query,
            limit=request.limit,
            metadata_filter=request.metadata_filter,
            source_filter=request.source_filter,
            distance_threshold=request.distance_threshold,
        )

        processing_time = (time.time() - start_time) * 1000  # ms

        return SearchResponse(
            query=request.query,
            results=[SearchResultResponse.from_search_result(r) for r in results],
            count=len(results),
            processing_time_ms=processing_time,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Search failed: {str(e)}"
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(service: EmbeddingService = Depends(get_embedding_service)):
    """
    Get vector database statistics

    Returns metrics about:
    - Total embeddings stored
    - Number of unique documents
    - Number of unique sources
    - Database size
    - Date range of embeddings
    """
    try:
        stats = await service.get_stats()
        return StatsResponse(**stats)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str, service: EmbeddingService = Depends(get_embedding_service)
):
    """
    Delete a document and all its chunks

    - **document_id**: Document ID to delete
    """
    try:
        deleted_count = await service.delete_document(document_id)

        if deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found"
            )

        return DeleteResponse(deleted_count=deleted_count)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.delete("/sources/{source}", response_model=DeleteResponse)
async def delete_source(source: str, service: EmbeddingService = Depends(get_embedding_service)):
    """
    Delete all documents from a source

    - **source**: Source identifier to delete
    """
    try:
        deleted_count = await service.delete_source(source)

        if deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No documents found for source '{source}'",
            )

        return DeleteResponse(deleted_count=deleted_count)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete source: {str(e)}",
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "vectors", "version": "2.0.3"}
