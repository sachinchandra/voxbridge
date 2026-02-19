-- Migration 005: QA Scoring Tables
-- Sprint 6: Analytics, QA, Polish

-- ──────────────────────────────────────────────────────────────────
-- call_qa_scores: Automated quality scores for each call
-- ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS call_qa_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Individual scores (0-100)
    accuracy_score INTEGER NOT NULL DEFAULT 0 CHECK (accuracy_score >= 0 AND accuracy_score <= 100),
    tone_score INTEGER NOT NULL DEFAULT 0 CHECK (tone_score >= 0 AND tone_score <= 100),
    resolution_score INTEGER NOT NULL DEFAULT 0 CHECK (resolution_score >= 0 AND resolution_score <= 100),
    compliance_score INTEGER NOT NULL DEFAULT 0 CHECK (compliance_score >= 0 AND compliance_score <= 100),
    overall_score INTEGER NOT NULL DEFAULT 0 CHECK (overall_score >= 0 AND overall_score <= 100),

    -- Flags
    pii_detected BOOLEAN NOT NULL DEFAULT FALSE,
    angry_caller BOOLEAN NOT NULL DEFAULT FALSE,
    flagged BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- AI-generated analysis
    summary TEXT NOT NULL DEFAULT '',
    improvement_suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One QA score per call
    UNIQUE(call_id)
);

-- Indexes for common queries
CREATE INDEX idx_qa_scores_customer ON call_qa_scores(customer_id);
CREATE INDEX idx_qa_scores_agent ON call_qa_scores(agent_id);
CREATE INDEX idx_qa_scores_flagged ON call_qa_scores(customer_id, flagged) WHERE flagged = TRUE;
CREATE INDEX idx_qa_scores_overall ON call_qa_scores(customer_id, overall_score);
CREATE INDEX idx_qa_scores_created ON call_qa_scores(customer_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────
-- Additional indexes for analytics queries on calls table
-- ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_calls_sentiment ON calls(customer_id, sentiment_score) WHERE sentiment_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calls_resolution ON calls(customer_id, resolution);
CREATE INDEX IF NOT EXISTS idx_calls_escalated ON calls(customer_id, escalated_to_human) WHERE escalated_to_human = TRUE;
CREATE INDEX IF NOT EXISTS idx_calls_period ON calls(customer_id, created_at DESC);

-- ──────────────────────────────────────────────────────────────────
-- RLS Policies
-- ──────────────────────────────────────────────────────────────────

ALTER TABLE call_qa_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own QA scores"
    ON call_qa_scores FOR SELECT
    USING (customer_id = auth.uid()::text);

CREATE POLICY "Users can insert their own QA scores"
    ON call_qa_scores FOR INSERT
    WITH CHECK (customer_id = auth.uid()::text);
