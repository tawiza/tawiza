-- Vector Database Schema for Tawiza v2.0
-- PostgreSQL + pgvector for high-performance vector search

-- Table for embeddings with metadata
CREATE TABLE IF NOT EXISTS embeddings (
    id BIGSERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),  -- Dimension 768 for common models (adjust as needed)
    metadata JSONB DEFAULT '{}',
    source VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique document_id + chunk_id combination
    UNIQUE(document_id, chunk_id)
);

-- HNSW Index for fast similarity search (Hierarchical Navigable Small World)
-- This provides excellent performance for most use cases
CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx
ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Additional indexes for common queries
CREATE INDEX IF NOT EXISTS embeddings_document_idx
ON embeddings (document_id);

CREATE INDEX IF NOT EXISTS embeddings_source_idx
ON embeddings (source);

CREATE INDEX IF NOT EXISTS embeddings_created_at_idx
ON embeddings (created_at DESC);

-- GIN index for JSONB metadata searching
CREATE INDEX IF NOT EXISTS embeddings_metadata_idx
ON embeddings
USING gin (metadata);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_embeddings_updated_at ON embeddings;
CREATE TRIGGER update_embeddings_updated_at
    BEFORE UPDATE ON embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create statistics for better query planning
CREATE STATISTICS IF NOT EXISTS embeddings_stats
ON document_id, source, created_at
FROM embeddings;

-- Comments for documentation
COMMENT ON TABLE embeddings IS 'Vector embeddings storage with pgvector for semantic search';
COMMENT ON COLUMN embeddings.embedding IS 'Vector embedding (default dimension: 768)';
COMMENT ON COLUMN embeddings.metadata IS 'Flexible JSONB metadata for filtering';
COMMENT ON INDEX embeddings_hnsw_idx IS 'HNSW index for fast approximate nearest neighbor search';

-- View for embedding statistics
CREATE OR REPLACE VIEW embedding_stats AS
SELECT
    COUNT(*) as total_embeddings,
    COUNT(DISTINCT document_id) as unique_documents,
    COUNT(DISTINCT source) as unique_sources,
    AVG(length(content)) as avg_content_length,
    MAX(created_at) as latest_embedding,
    MIN(created_at) as earliest_embedding,
    pg_size_pretty(pg_total_relation_size('embeddings')) as table_size
FROM embeddings;

COMMENT ON VIEW embedding_stats IS 'Quick statistics on the embeddings table';
