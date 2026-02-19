-- VoxBridge Platform — Sprint 5 Migration
-- Knowledge Bases, Documents, Document Chunks (with pgvector)
-- Run this in Supabase SQL editor after 003_telephony_indexes.sql

-- Enable pgvector extension (Supabase has this available)
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────────────────────────
-- Knowledge Bases table
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'New Knowledge Base',
    description TEXT DEFAULT '',
    embedding_model TEXT DEFAULT 'text-embedding-3-small',
    chunk_size INTEGER DEFAULT 512,
    chunk_overlap INTEGER DEFAULT 50,
    document_count INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
        CHECK (status IN ('active', 'deleted')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_bases_customer ON knowledge_bases(customer_id);
CREATE INDEX idx_knowledge_bases_customer_status ON knowledge_bases(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- Documents table
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    filename TEXT DEFAULT '',
    content_type TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    file_size_bytes INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'processing'
        CHECK (status IN ('processing', 'ready', 'failed', 'deleted')),
    error_message TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_kb ON documents(knowledge_base_id);
CREATE INDEX idx_documents_customer ON documents(customer_id);
CREATE INDEX idx_documents_status ON documents(knowledge_base_id, status);

-- ──────────────────────────────────────────────────────────────────
-- Document Chunks table (with pgvector embedding)
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    chunk_index INTEGER DEFAULT 0,
    content TEXT DEFAULT '',
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    token_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_kb ON document_chunks(knowledge_base_id);

-- Vector similarity index for fast search (IVFFlat)
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ──────────────────────────────────────────────────────────────────
-- Vector similarity search function (used by the API)
-- ──────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_knowledge_base_id UUID,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    chunk_id TEXT,
    document_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        dc.content,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        dc.metadata
    FROM document_chunks dc
    WHERE dc.knowledge_base_id = match_knowledge_base_id
      AND 1 - (dc.embedding <=> query_embedding) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ──────────────────────────────────────────────────────────────────
-- Row Level Security
-- ──────────────────────────────────────────────────────────────────
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON knowledge_bases FOR ALL USING (true);
CREATE POLICY "Service role full access" ON documents FOR ALL USING (true);
CREATE POLICY "Service role full access" ON document_chunks FOR ALL USING (true);

-- ──────────────────────────────────────────────────────────────────
-- Updated_at trigger for knowledge_bases
-- ──────────────────────────────────────────────────────────────────
CREATE TRIGGER update_knowledge_bases_updated_at
    BEFORE UPDATE ON knowledge_bases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
