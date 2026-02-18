-- VoxBridge Platform — Sprint 4 Migration
-- Additional indexes for telephony operations (inbound routing, outbound calls)
-- Run this in Supabase SQL editor after 002_agents_calls.sql

-- ──────────────────────────────────────────────────────────────────
-- Phone number lookup for inbound call routing
-- The webhook needs to quickly find a phone number + agent by the called number
-- ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_phone_numbers_active_number
    ON phone_numbers(phone_number, status)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_phone_numbers_customer_status
    ON phone_numbers(customer_id, status);

-- ──────────────────────────────────────────────────────────────────
-- Call lookups by Twilio SID (stored in metadata->>'twilio_call_sid')
-- Used by the status webhook to find call records
-- ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_calls_twilio_sid
    ON calls((metadata->>'twilio_call_sid'))
    WHERE metadata->>'twilio_call_sid' IS NOT NULL;

-- ──────────────────────────────────────────────────────────────────
-- Calls by phone_number_id for number → call lookups
-- ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_calls_phone_number
    ON calls(phone_number_id);

-- ──────────────────────────────────────────────────────────────────
-- Composite index for call list filtering
-- Covers the common dashboard query: customer + agent + direction + status
-- ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_calls_customer_direction_status
    ON calls(customer_id, direction, status, created_at DESC);
