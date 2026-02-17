-- VoxBridge Platform — Sprint 1 Migration
-- AI Agents, Phone Numbers, Calls, Tool Calls
-- Run this in Supabase SQL editor after the initial schema

-- ──────────────────────────────────────────────────────────────────
-- AI Agents table (the core entity)
-- ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'New Agent',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'paused', 'archived')),

    -- AI Configuration
    system_prompt TEXT DEFAULT '',
    first_message TEXT DEFAULT '',
    end_call_phrases JSONB DEFAULT '[]',

    -- STT
    stt_provider TEXT DEFAULT 'deepgram',
    stt_config JSONB DEFAULT '{}',

    -- LLM
    llm_provider TEXT DEFAULT 'openai',
    llm_model TEXT DEFAULT 'gpt-4o-mini',
    llm_config JSONB DEFAULT '{}',

    -- TTS
    tts_provider TEXT DEFAULT 'elevenlabs',
    tts_voice_id TEXT DEFAULT '',
    tts_config JSONB DEFAULT '{}',

    -- Behavior
    max_duration_seconds INTEGER DEFAULT 300,
    interruption_enabled BOOLEAN DEFAULT TRUE,

    -- Function calling / tools
    tools JSONB DEFAULT '[]',
    knowledge_base_id UUID,

    -- Escalation config
    escalation_config JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_customer ON agents(customer_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_customer_status ON agents(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- Phone Numbers table
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

CREATE UNIQUE INDEX idx_phone_numbers_number ON phone_numbers(phone_number);
CREATE INDEX idx_phone_numbers_customer ON phone_numbers(customer_id);
CREATE INDEX idx_phone_numbers_agent ON phone_numbers(agent_id);

-- ──────────────────────────────────────────────────────────────────
-- Calls table (every call through the platform)
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

CREATE INDEX idx_calls_customer ON calls(customer_id);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_calls_customer_created ON calls(customer_id, created_at DESC);
CREATE INDEX idx_calls_agent_created ON calls(agent_id, created_at DESC);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_direction ON calls(direction);

-- ──────────────────────────────────────────────────────────────────
-- Tool Calls table (function calls made during calls)
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

CREATE INDEX idx_tool_calls_call ON tool_calls(call_id);
CREATE INDEX idx_tool_calls_agent ON tool_calls(agent_id);

-- ──────────────────────────────────────────────────────────────────
-- Row Level Security
-- ──────────────────────────────────────────────────────────────────
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE phone_numbers ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_calls ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (used by our backend)
CREATE POLICY "Service role full access" ON agents FOR ALL USING (true);
CREATE POLICY "Service role full access" ON phone_numbers FOR ALL USING (true);
CREATE POLICY "Service role full access" ON calls FOR ALL USING (true);
CREATE POLICY "Service role full access" ON tool_calls FOR ALL USING (true);

-- ──────────────────────────────────────────────────────────────────
-- Updated_at trigger for agents
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
