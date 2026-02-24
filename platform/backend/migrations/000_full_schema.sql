-- ================================================================
-- VoxBridge Platform — Full Database Schema
-- Run this ONCE in Supabase SQL Editor: https://supabase.com/dashboard
-- Go to: SQL Editor → New Query → Paste & Run
-- ================================================================

-- ──────────────────────────────────────────────────────────────────
-- Extensions
-- ──────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ──────────────────────────────────────────────────────────────────
-- 1. Customers
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id);

-- ──────────────────────────────────────────────────────────────────
-- 2. API Keys
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    name TEXT DEFAULT 'Default',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_customer ON api_keys(customer_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);

-- ──────────────────────────────────────────────────────────────────
-- 3. Usage Records
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    call_id TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION DEFAULT 0.0,
    audio_bytes_in BIGINT DEFAULT 0,
    audio_bytes_out BIGINT DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'error')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usage_customer ON usage_records(customer_id);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_records(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_customer_date ON usage_records(customer_id, created_at);

-- ──────────────────────────────────────────────────────────────────
-- 4. Subscriptions
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    stripe_subscription_id TEXT NOT NULL,
    plan TEXT DEFAULT 'pro' CHECK (plan IN ('free', 'pro', 'enterprise')),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due', 'trialing')),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions(customer_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe ON subscriptions(stripe_subscription_id);

-- ──────────────────────────────────────────────────────────────────
-- 5. AI Agents
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'New Agent',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'archived')),
    system_prompt TEXT DEFAULT '',
    first_message TEXT DEFAULT '',
    end_call_phrases JSONB DEFAULT '[]',
    stt_provider TEXT DEFAULT 'deepgram',
    stt_config JSONB DEFAULT '{}',
    llm_provider TEXT DEFAULT 'openai',
    llm_model TEXT DEFAULT 'gpt-4o-mini',
    llm_config JSONB DEFAULT '{}',
    tts_provider TEXT DEFAULT 'elevenlabs',
    tts_voice_id TEXT DEFAULT '',
    tts_config JSONB DEFAULT '{}',
    max_duration_seconds INTEGER DEFAULT 300,
    interruption_enabled BOOLEAN DEFAULT TRUE,
    tools JSONB DEFAULT '[]',
    knowledge_base_id UUID,
    escalation_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agents_customer ON agents(customer_id);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_customer_status ON agents(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- 6. Phone Numbers
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    phone_number TEXT NOT NULL,
    provider TEXT DEFAULT 'twilio',
    provider_sid TEXT DEFAULT '',
    country TEXT DEFAULT 'US',
    capabilities JSONB DEFAULT '["voice"]',
    status TEXT DEFAULT 'active'
        CHECK (status IN ('active', 'released', 'pending')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_phone_numbers_number ON phone_numbers(phone_number);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_customer ON phone_numbers(customer_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent ON phone_numbers(agent_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_active_number ON phone_numbers(phone_number, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_phone_numbers_customer_status ON phone_numbers(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- 7. Calls
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE SET NULL,
    direction TEXT NOT NULL DEFAULT 'inbound'
        CHECK (direction IN ('inbound', 'outbound')),
    from_number TEXT DEFAULT '',
    to_number TEXT DEFAULT '',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION DEFAULT 0.0,
    status TEXT DEFAULT 'initiated'
        CHECK (status IN ('initiated', 'ringing', 'in_progress', 'completed', 'failed', 'no_answer', 'busy')),
    end_reason TEXT DEFAULT '',
    transcript JSONB DEFAULT '[]',
    recording_url TEXT DEFAULT '',
    sentiment_score DOUBLE PRECISION,
    resolution TEXT DEFAULT '',
    escalated_to_human BOOLEAN DEFAULT FALSE,
    cost_cents INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_calls_customer ON calls(customer_id);
CREATE INDEX IF NOT EXISTS idx_calls_agent ON calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_calls_customer_created ON calls(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_agent_created ON calls(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_direction ON calls(direction);
CREATE INDEX IF NOT EXISTS idx_calls_phone_number ON calls(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_calls_twilio_sid ON calls((metadata->>'twilio_call_sid')) WHERE metadata->>'twilio_call_sid' IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calls_customer_direction_status ON calls(customer_id, direction, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_sentiment ON calls(customer_id, sentiment_score) WHERE sentiment_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calls_resolution ON calls(customer_id, resolution);
CREATE INDEX IF NOT EXISTS idx_calls_escalated ON calls(customer_id, escalated_to_human) WHERE escalated_to_human = TRUE;
CREATE INDEX IF NOT EXISTS idx_calls_period ON calls(customer_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────
-- 8. Tool Calls
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    function_name TEXT NOT NULL,
    arguments JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_call ON tool_calls(call_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_agent ON tool_calls(agent_id);

-- ──────────────────────────────────────────────────────────────────
-- 9. Knowledge Bases
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
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_customer ON knowledge_bases(customer_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_bases_customer_status ON knowledge_bases(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- 10. Documents
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
CREATE INDEX IF NOT EXISTS idx_documents_kb ON documents(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_customer ON documents(customer_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(knowledge_base_id, status);

-- ──────────────────────────────────────────────────────────────────
-- 11. Document Chunks (with pgvector embeddings)
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    chunk_index INTEGER DEFAULT 0,
    content TEXT DEFAULT '',
    embedding vector(1536),
    token_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON document_chunks(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ──────────────────────────────────────────────────────────────────
-- 12. QA Scores
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS call_qa_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    accuracy_score INTEGER NOT NULL DEFAULT 0 CHECK (accuracy_score >= 0 AND accuracy_score <= 100),
    tone_score INTEGER NOT NULL DEFAULT 0 CHECK (tone_score >= 0 AND tone_score <= 100),
    resolution_score INTEGER NOT NULL DEFAULT 0 CHECK (resolution_score >= 0 AND resolution_score <= 100),
    compliance_score INTEGER NOT NULL DEFAULT 0 CHECK (compliance_score >= 0 AND compliance_score <= 100),
    overall_score INTEGER NOT NULL DEFAULT 0 CHECK (overall_score >= 0 AND overall_score <= 100),
    pii_detected BOOLEAN NOT NULL DEFAULT FALSE,
    angry_caller BOOLEAN NOT NULL DEFAULT FALSE,
    flagged BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT NOT NULL DEFAULT '',
    improvement_suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(call_id)
);
CREATE INDEX IF NOT EXISTS idx_qa_scores_customer ON call_qa_scores(customer_id);
CREATE INDEX IF NOT EXISTS idx_qa_scores_agent ON call_qa_scores(agent_id);
CREATE INDEX IF NOT EXISTS idx_qa_scores_flagged ON call_qa_scores(customer_id, flagged) WHERE flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_qa_scores_overall ON call_qa_scores(customer_id, overall_score);
CREATE INDEX IF NOT EXISTS idx_qa_scores_created ON call_qa_scores(customer_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────
-- Triggers
-- ──────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_knowledge_bases_updated_at
    BEFORE UPDATE ON knowledge_bases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ──────────────────────────────────────────────────────────────────
-- Vector similarity search function
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
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_qa_scores ENABLE ROW LEVEL SECURITY;

-- Service role (backend) gets full access to all tables
CREATE POLICY "Service role full access" ON customers FOR ALL USING (true);
CREATE POLICY "Service role full access" ON api_keys FOR ALL USING (true);
CREATE POLICY "Service role full access" ON usage_records FOR ALL USING (true);
CREATE POLICY "Service role full access" ON subscriptions FOR ALL USING (true);
CREATE POLICY "Service role full access" ON agents FOR ALL USING (true);
CREATE POLICY "Service role full access" ON phone_numbers FOR ALL USING (true);
CREATE POLICY "Service role full access" ON calls FOR ALL USING (true);
CREATE POLICY "Service role full access" ON tool_calls FOR ALL USING (true);
CREATE POLICY "Service role full access" ON knowledge_bases FOR ALL USING (true);
CREATE POLICY "Service role full access" ON documents FOR ALL USING (true);
CREATE POLICY "Service role full access" ON document_chunks FOR ALL USING (true);
CREATE POLICY "Service role full access" ON call_qa_scores FOR ALL USING (true);

-- ================================================================
-- Done! 12 tables created with indexes, triggers, RLS, and functions.
-- ================================================================
