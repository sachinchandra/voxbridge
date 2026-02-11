-- VoxBridge Platform Database Schema
-- Run this in Supabase SQL editor to set up the database

-- ──────────────────────────────────────────────────────────────────
-- Customers table
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

CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_stripe ON customers(stripe_customer_id);

-- ──────────────────────────────────────────────────────────────────
-- API Keys table
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

CREATE INDEX idx_api_keys_customer ON api_keys(customer_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_status ON api_keys(status);

-- ──────────────────────────────────────────────────────────────────
-- Usage Records table
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

CREATE INDEX idx_usage_customer ON usage_records(customer_id);
CREATE INDEX idx_usage_created ON usage_records(created_at);
CREATE INDEX idx_usage_customer_date ON usage_records(customer_id, created_at);

-- ──────────────────────────────────────────────────────────────────
-- Subscriptions table
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

CREATE INDEX idx_subscriptions_customer ON subscriptions(customer_id);
CREATE INDEX idx_subscriptions_stripe ON subscriptions(stripe_subscription_id);

-- ──────────────────────────────────────────────────────────────────
-- Row Level Security (RLS)
-- ──────────────────────────────────────────────────────────────────
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (used by our backend)
CREATE POLICY "Service role full access" ON customers FOR ALL USING (true);
CREATE POLICY "Service role full access" ON api_keys FOR ALL USING (true);
CREATE POLICY "Service role full access" ON usage_records FOR ALL USING (true);
CREATE POLICY "Service role full access" ON subscriptions FOR ALL USING (true);
