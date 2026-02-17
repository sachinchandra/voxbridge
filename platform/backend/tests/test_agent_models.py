"""Tests for Agent, Call, PhoneNumber, ToolCall models and schemas."""

import pytest
from datetime import datetime, timezone

from app.models.database import (
    Agent,
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentStatsResponse,
    AgentStatus,
    AgentUpdate,
    Call,
    CallDetailResponse,
    CallDirection,
    CallResponse,
    CallStatus,
    PhoneNumber,
    PhoneNumberStatus,
    ToolCall,
)


# ──────────────────────────────────────────────────────────────────
# Agent Model Tests
# ──────────────────────────────────────────────────────────────────

class TestAgentModel:
    def test_defaults(self):
        agent = Agent(customer_id="cust-1")
        assert agent.customer_id == "cust-1"
        assert agent.name == "New Agent"
        assert agent.status == AgentStatus.DRAFT
        assert agent.system_prompt == ""
        assert agent.llm_provider == "openai"
        assert agent.llm_model == "gpt-4o-mini"
        assert agent.stt_provider == "deepgram"
        assert agent.tts_provider == "elevenlabs"
        assert agent.max_duration_seconds == 300
        assert agent.interruption_enabled is True
        assert agent.tools == []
        assert agent.knowledge_base_id is None
        assert agent.escalation_config == {}
        assert isinstance(agent.id, str)
        assert len(agent.id) > 0

    def test_custom_values(self):
        agent = Agent(
            customer_id="cust-1",
            name="Support Bot",
            status=AgentStatus.ACTIVE,
            system_prompt="You are a helpful support agent.",
            first_message="Hello! How can I help you today?",
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
            tts_voice_id="voice-123",
            max_duration_seconds=600,
            tools=[{"name": "check_order", "endpoint": "https://api.example.com/orders"}],
        )
        assert agent.name == "Support Bot"
        assert agent.status == AgentStatus.ACTIVE
        assert agent.llm_provider == "anthropic"
        assert agent.llm_model == "claude-sonnet-4-20250514"
        assert len(agent.tools) == 1

    def test_end_call_phrases(self):
        agent = Agent(
            customer_id="cust-1",
            end_call_phrases=["goodbye", "bye", "have a nice day"],
        )
        assert len(agent.end_call_phrases) == 3
        assert "goodbye" in agent.end_call_phrases


class TestAgentStatusEnum:
    def test_values(self):
        assert AgentStatus.DRAFT == "draft"
        assert AgentStatus.ACTIVE == "active"
        assert AgentStatus.PAUSED == "paused"
        assert AgentStatus.ARCHIVED == "archived"


# ──────────────────────────────────────────────────────────────────
# Call Model Tests
# ──────────────────────────────────────────────────────────────────

class TestCallModel:
    def test_defaults(self):
        call = Call(customer_id="cust-1", agent_id="agent-1")
        assert call.direction == CallDirection.INBOUND
        assert call.status == CallStatus.INITIATED
        assert call.duration_seconds == 0.0
        assert call.transcript == []
        assert call.escalated_to_human is False
        assert call.cost_cents == 0
        assert call.metadata == {}

    def test_completed_call(self):
        call = Call(
            customer_id="cust-1",
            agent_id="agent-1",
            direction=CallDirection.OUTBOUND,
            from_number="+14155551234",
            to_number="+14155555678",
            duration_seconds=180.5,
            status=CallStatus.COMPLETED,
            end_reason="caller_hangup",
            sentiment_score=0.85,
            resolution="resolved",
            cost_cents=36,
            transcript=[
                {"role": "assistant", "content": "Hello!", "timestamp": "2024-01-01T00:00:00Z"},
                {"role": "user", "content": "Hi, I need help.", "timestamp": "2024-01-01T00:00:03Z"},
            ],
        )
        assert call.direction == CallDirection.OUTBOUND
        assert call.duration_seconds == 180.5
        assert call.cost_cents == 36
        assert len(call.transcript) == 2

    def test_escalated_call(self):
        call = Call(
            customer_id="cust-1",
            agent_id="agent-1",
            escalated_to_human=True,
            resolution="escalated",
        )
        assert call.escalated_to_human is True
        assert call.resolution == "escalated"


class TestCallEnums:
    def test_direction(self):
        assert CallDirection.INBOUND == "inbound"
        assert CallDirection.OUTBOUND == "outbound"

    def test_status(self):
        assert CallStatus.INITIATED == "initiated"
        assert CallStatus.IN_PROGRESS == "in_progress"
        assert CallStatus.COMPLETED == "completed"
        assert CallStatus.FAILED == "failed"


# ──────────────────────────────────────────────────────────────────
# PhoneNumber Model Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberModel:
    def test_defaults(self):
        phone = PhoneNumber(customer_id="cust-1", phone_number="+14155551234")
        assert phone.provider == "twilio"
        assert phone.country == "US"
        assert phone.status == PhoneNumberStatus.ACTIVE
        assert phone.capabilities == ["voice"]
        assert phone.agent_id is None

    def test_assigned(self):
        phone = PhoneNumber(
            customer_id="cust-1",
            phone_number="+14155551234",
            agent_id="agent-1",
            provider="telnyx",
        )
        assert phone.agent_id == "agent-1"
        assert phone.provider == "telnyx"


# ──────────────────────────────────────────────────────────────────
# ToolCall Model Tests
# ──────────────────────────────────────────────────────────────────

class TestToolCallModel:
    def test_defaults(self):
        tc = ToolCall(
            call_id="call-1",
            agent_id="agent-1",
            function_name="check_order_status",
        )
        assert tc.function_name == "check_order_status"
        assert tc.arguments == {}
        assert tc.result == {}
        assert tc.duration_ms == 0

    def test_with_data(self):
        tc = ToolCall(
            call_id="call-1",
            agent_id="agent-1",
            function_name="check_order_status",
            arguments={"order_id": "ORD-123"},
            result={"status": "shipped", "tracking": "1Z999AA10123456784"},
            duration_ms=245,
        )
        assert tc.arguments["order_id"] == "ORD-123"
        assert tc.result["status"] == "shipped"
        assert tc.duration_ms == 245


# ──────────────────────────────────────────────────────────────────
# API Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestAgentSchemas:
    def test_agent_create_defaults(self):
        body = AgentCreate()
        assert body.name == "New Agent"
        assert body.llm_provider == "openai"
        assert body.llm_model == "gpt-4o-mini"

    def test_agent_create_custom(self):
        body = AgentCreate(
            name="Sales Bot",
            system_prompt="You are a sales agent.",
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
        )
        assert body.name == "Sales Bot"
        assert body.llm_provider == "anthropic"

    def test_agent_update_partial(self):
        body = AgentUpdate(name="Updated Name")
        dump = body.model_dump(exclude_unset=True)
        assert "name" in dump
        assert "system_prompt" not in dump

    def test_agent_update_empty(self):
        body = AgentUpdate()
        dump = body.model_dump(exclude_unset=True)
        assert len(dump) == 0

    def test_agent_response(self):
        resp = AgentResponse(
            id="agent-1",
            name="Test",
            status=AgentStatus.ACTIVE,
            system_prompt="test",
            first_message="hi",
            end_call_phrases=[],
            stt_provider="deepgram",
            stt_config={},
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_config={},
            tts_provider="elevenlabs",
            tts_voice_id="",
            tts_config={},
            max_duration_seconds=300,
            interruption_enabled=True,
            tools=[],
            knowledge_base_id=None,
            escalation_config={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.id == "agent-1"
        assert resp.status == AgentStatus.ACTIVE

    def test_agent_list_response(self):
        resp = AgentListResponse(
            id="agent-1",
            name="Test",
            status=AgentStatus.ACTIVE,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            tts_provider="elevenlabs",
            total_calls=42,
            avg_duration=95.3,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.total_calls == 42
        assert resp.avg_duration == 95.3

    def test_agent_stats_response(self):
        resp = AgentStatsResponse(
            agent_id="agent-1",
            agent_name="Test",
            total_calls=100,
            completed_calls=90,
            failed_calls=5,
            escalated_calls=5,
            avg_duration_seconds=120.5,
            total_duration_minutes=200.8,
            avg_sentiment=0.75,
            resolution_rate=85.0,
            containment_rate=95.0,
            total_cost_cents=3600,
        )
        assert resp.containment_rate == 95.0
        assert resp.resolution_rate == 85.0


class TestCallSchemas:
    def test_call_response(self):
        resp = CallResponse(
            id="call-1",
            agent_id="agent-1",
            agent_name="Support Bot",
            direction=CallDirection.INBOUND,
            from_number="+1415",
            to_number="+1650",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration_seconds=60.0,
            status=CallStatus.COMPLETED,
            end_reason="caller_hangup",
            escalated_to_human=False,
            sentiment_score=0.9,
            resolution="resolved",
            cost_cents=12,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.agent_name == "Support Bot"

    def test_call_detail_response(self):
        resp = CallDetailResponse(
            id="call-1",
            agent_id="agent-1",
            direction=CallDirection.INBOUND,
            from_number="+1415",
            to_number="+1650",
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration_seconds=60.0,
            status=CallStatus.COMPLETED,
            end_reason="",
            escalated_to_human=False,
            sentiment_score=None,
            resolution="",
            cost_cents=0,
            created_at=datetime.now(timezone.utc),
            transcript=[{"role": "assistant", "content": "Hello!"}],
            recording_url="https://storage.example.com/rec.mp3",
            metadata={"campaign": "spring_2024"},
            tool_calls=[],
        )
        assert len(resp.transcript) == 1
        assert resp.recording_url.endswith(".mp3")
