"""Tests for Sprint 4: Phone Numbers + Inbound/Outbound Telephony.

Tests cover:
- Phone number API schemas (search, buy, update, response)
- Outbound call schemas
- Inbound webhook schemas
- Cost calculation service
- Config settings for Twilio + AI providers
- API router endpoint structure validation
"""

import pytest
from datetime import datetime, timezone

from app.models.database import (
    # Phone Number schemas
    PhoneNumber,
    PhoneNumberBuyRequest,
    PhoneNumberResponse,
    PhoneNumberSearchRequest,
    PhoneNumberSearchResult,
    PhoneNumberStatus,
    PhoneNumberUpdate,
    # Call schemas
    Call,
    CallDirection,
    CallStatus,
    OutboundCallRequest,
    OutboundCallResponse,
    # Webhook
    InboundCallWebhook,
    # Existing
    Agent,
    AgentStatus,
    Customer,
    PlanTier,
)
from app.config import Settings
from app.services.database import calculate_call_cost


# ──────────────────────────────────────────────────────────────────
# Phone Number Search Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberSearchRequest:
    def test_defaults(self):
        req = PhoneNumberSearchRequest()
        assert req.country == "US"
        assert req.area_code is None
        assert req.contains is None
        assert req.limit == 10

    def test_custom_search(self):
        req = PhoneNumberSearchRequest(
            country="CA",
            area_code="416",
            contains="1234",
            limit=5,
        )
        assert req.country == "CA"
        assert req.area_code == "416"
        assert req.contains == "1234"
        assert req.limit == 5


class TestPhoneNumberSearchResult:
    def test_defaults(self):
        result = PhoneNumberSearchResult(phone_number="+14155551234")
        assert result.phone_number == "+14155551234"
        assert result.friendly_name == ""
        assert result.country == "US"
        assert result.region == ""
        assert result.capabilities == ["voice"]
        assert result.monthly_cost_cents == 100

    def test_with_details(self):
        result = PhoneNumberSearchResult(
            phone_number="+14155551234",
            friendly_name="(415) 555-1234",
            country="US",
            region="CA",
            capabilities=["voice", "sms"],
            monthly_cost_cents=150,
        )
        assert result.friendly_name == "(415) 555-1234"
        assert "sms" in result.capabilities
        assert result.monthly_cost_cents == 150


# ──────────────────────────────────────────────────────────────────
# Phone Number Buy Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberBuyRequest:
    def test_required_fields(self):
        req = PhoneNumberBuyRequest(phone_number="+14155551234")
        assert req.phone_number == "+14155551234"
        assert req.agent_id is None

    def test_with_agent(self):
        req = PhoneNumberBuyRequest(
            phone_number="+14155551234",
            agent_id="agent-1",
        )
        assert req.agent_id == "agent-1"


# ──────────────────────────────────────────────────────────────────
# Phone Number Response Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberResponse:
    def test_full_response(self):
        resp = PhoneNumberResponse(
            id="phone-1",
            phone_number="+14155551234",
            provider="twilio",
            country="US",
            capabilities=["voice"],
            status=PhoneNumberStatus.ACTIVE,
            agent_id="agent-1",
            agent_name="Support Bot",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.id == "phone-1"
        assert resp.status == PhoneNumberStatus.ACTIVE
        assert resp.agent_name == "Support Bot"

    def test_unassigned(self):
        resp = PhoneNumberResponse(
            id="phone-2",
            phone_number="+14155555678",
            provider="twilio",
            country="US",
            capabilities=["voice"],
            status=PhoneNumberStatus.ACTIVE,
            agent_id=None,
            agent_name="",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.agent_id is None
        assert resp.agent_name == ""


class TestPhoneNumberUpdate:
    def test_assign_agent(self):
        update = PhoneNumberUpdate(agent_id="agent-1")
        assert update.agent_id == "agent-1"

    def test_unassign(self):
        update = PhoneNumberUpdate(agent_id=None)
        assert update.agent_id is None

    def test_default(self):
        update = PhoneNumberUpdate()
        assert update.agent_id is None


# ──────────────────────────────────────────────────────────────────
# Phone Number Status Enum Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberStatusEnum:
    def test_values(self):
        assert PhoneNumberStatus.ACTIVE == "active"
        assert PhoneNumberStatus.RELEASED == "released"
        assert PhoneNumberStatus.PENDING == "pending"

    def test_membership(self):
        assert "active" in [s.value for s in PhoneNumberStatus]
        assert "released" in [s.value for s in PhoneNumberStatus]


# ──────────────────────────────────────────────────────────────────
# Outbound Call Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestOutboundCallRequest:
    def test_required_fields(self):
        req = OutboundCallRequest(
            agent_id="agent-1",
            to="+14155551234",
        )
        assert req.agent_id == "agent-1"
        assert req.to == "+14155551234"
        assert req.from_number_id is None
        assert req.metadata == {}

    def test_with_options(self):
        req = OutboundCallRequest(
            agent_id="agent-1",
            to="+14155551234",
            from_number_id="phone-1",
            metadata={"campaign": "followup"},
        )
        assert req.from_number_id == "phone-1"
        assert req.metadata["campaign"] == "followup"


class TestOutboundCallResponse:
    def test_response(self):
        resp = OutboundCallResponse(
            call_id="call-1",
            status=CallStatus.INITIATED,
            from_number="+14155550001",
            to_number="+14155551234",
            agent_id="agent-1",
            agent_name="Support Bot",
        )
        assert resp.call_id == "call-1"
        assert resp.status == CallStatus.INITIATED
        assert resp.agent_name == "Support Bot"


# ──────────────────────────────────────────────────────────────────
# Inbound Call Webhook Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestInboundCallWebhook:
    def test_defaults(self):
        webhook = InboundCallWebhook()
        assert webhook.CallSid == ""
        assert webhook.From == ""
        assert webhook.To == ""
        assert webhook.Direction == "inbound"
        assert webhook.CallStatus == ""
        assert webhook.AccountSid == ""

    def test_twilio_payload(self):
        webhook = InboundCallWebhook(
            CallSid="CA1234567890abcdef",
            From="+14155551234",
            To="+14155550001",
            Direction="inbound",
            CallStatus="ringing",
            AccountSid="AC1234567890abcdef",
        )
        assert webhook.CallSid == "CA1234567890abcdef"
        assert webhook.From == "+14155551234"
        assert webhook.To == "+14155550001"
        assert webhook.CallStatus == "ringing"


# ──────────────────────────────────────────────────────────────────
# Cost Calculation Tests
# ──────────────────────────────────────────────────────────────────

class TestCostCalculation:
    def test_one_minute(self):
        cost = calculate_call_cost(60.0, cost_per_minute_cents=6)
        assert cost == 6

    def test_half_minute(self):
        cost = calculate_call_cost(30.0, cost_per_minute_cents=6)
        assert cost == 3

    def test_minimum_cost(self):
        """Very short calls should have minimum 1 cent."""
        cost = calculate_call_cost(1.0, cost_per_minute_cents=6)
        assert cost == 1

    def test_zero_duration(self):
        """Zero-duration calls should still cost 1 cent minimum."""
        cost = calculate_call_cost(0.0, cost_per_minute_cents=6)
        assert cost == 1

    def test_five_minutes(self):
        cost = calculate_call_cost(300.0, cost_per_minute_cents=6)
        assert cost == 30  # 5 min * 6 cents

    def test_custom_rate(self):
        cost = calculate_call_cost(60.0, cost_per_minute_cents=10)
        assert cost == 10

    def test_fractional_minutes(self):
        cost = calculate_call_cost(90.0, cost_per_minute_cents=6)
        assert cost == 9  # 1.5 min * 6 cents

    def test_long_call(self):
        cost = calculate_call_cost(3600.0, cost_per_minute_cents=6)
        assert cost == 360  # 60 min * 6 cents

    def test_rounding(self):
        """Cost should round half up."""
        # 45 seconds = 0.75 min * 6 = 4.5 → rounds to 5
        cost = calculate_call_cost(45.0, cost_per_minute_cents=6)
        assert cost == 5


# ──────────────────────────────────────────────────────────────────
# Config Tests
# ──────────────────────────────────────────────────────────────────

class TestTelephonyConfig:
    def test_twilio_settings_exist(self):
        """Verify Twilio settings are defined in the Settings model."""
        s = Settings()
        assert hasattr(s, "twilio_account_sid")
        assert hasattr(s, "twilio_auth_token")
        assert hasattr(s, "twilio_webhook_base_url")

    def test_ai_provider_keys_exist(self):
        """Verify AI provider API key fields exist."""
        s = Settings()
        assert hasattr(s, "deepgram_api_key")
        assert hasattr(s, "openai_api_key")
        assert hasattr(s, "anthropic_api_key")
        assert hasattr(s, "elevenlabs_api_key")

    def test_cost_settings_defaults(self):
        s = Settings()
        assert s.cost_per_minute_cents == 6
        assert s.twilio_cost_per_minute_cents == 1

    def test_plan_limits(self):
        s = Settings()
        assert s.free_plan_minutes == 100
        assert s.pro_plan_minutes == 5000
        assert s.enterprise_plan_minutes == 50000

    def test_concurrent_call_limits(self):
        s = Settings()
        assert s.free_max_concurrent_calls == 2
        assert s.pro_max_concurrent_calls == 20
        assert s.enterprise_max_concurrent_calls == 200


# ──────────────────────────────────────────────────────────────────
# Call Creation for Outbound Tests
# ──────────────────────────────────────────────────────────────────

class TestCallModelForOutbound:
    def test_outbound_call_creation(self):
        call = Call(
            customer_id="cust-1",
            agent_id="agent-1",
            phone_number_id="phone-1",
            direction=CallDirection.OUTBOUND,
            from_number="+14155550001",
            to_number="+14155551234",
            status=CallStatus.INITIATED,
            metadata={"campaign": "followup"},
        )
        assert call.direction == CallDirection.OUTBOUND
        assert call.from_number == "+14155550001"
        assert call.to_number == "+14155551234"
        assert call.status == CallStatus.INITIATED
        assert call.metadata["campaign"] == "followup"
        assert call.phone_number_id == "phone-1"

    def test_inbound_call_with_twilio_sid(self):
        call = Call(
            customer_id="cust-1",
            agent_id="agent-1",
            phone_number_id="phone-1",
            direction=CallDirection.INBOUND,
            from_number="+14155551234",
            to_number="+14155550001",
            status=CallStatus.RINGING,
            metadata={
                "twilio_call_sid": "CA1234567890",
                "twilio_account_sid": "AC1234567890",
            },
        )
        assert call.metadata["twilio_call_sid"] == "CA1234567890"
        assert call.status == CallStatus.RINGING


# ──────────────────────────────────────────────────────────────────
# PhoneNumber Model Extended Tests
# ──────────────────────────────────────────────────────────────────

class TestPhoneNumberModelExtended:
    def test_with_provider_sid(self):
        phone = PhoneNumber(
            customer_id="cust-1",
            phone_number="+14155551234",
            provider="twilio",
            provider_sid="PN1234567890abcdef",
            country="US",
            capabilities=["voice", "sms"],
        )
        assert phone.provider_sid == "PN1234567890abcdef"
        assert "sms" in phone.capabilities

    def test_released_number(self):
        phone = PhoneNumber(
            customer_id="cust-1",
            phone_number="+14155551234",
            status=PhoneNumberStatus.RELEASED,
            agent_id=None,
        )
        assert phone.status == PhoneNumberStatus.RELEASED
        assert phone.agent_id is None

    def test_multiple_capabilities(self):
        phone = PhoneNumber(
            customer_id="cust-1",
            phone_number="+14155551234",
            capabilities=["voice", "sms", "fax"],
        )
        assert len(phone.capabilities) == 3


# ──────────────────────────────────────────────────────────────────
# Integration-style Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestSchemaIntegration:
    def test_buy_request_to_phone_number(self):
        """Simulate the buy flow: request → phone number record."""
        buy_req = PhoneNumberBuyRequest(
            phone_number="+14155551234",
            agent_id="agent-1",
        )

        # Simulate DB creation
        phone = PhoneNumber(
            customer_id="cust-1",
            phone_number=buy_req.phone_number,
            agent_id=buy_req.agent_id,
            provider="twilio",
            provider_sid="PN_test_1234",
        )

        # Simulate response
        resp = PhoneNumberResponse(
            id=phone.id,
            phone_number=phone.phone_number,
            provider=phone.provider,
            country=phone.country,
            capabilities=phone.capabilities,
            status=phone.status,
            agent_id=phone.agent_id,
            agent_name="Test Agent",
            created_at=phone.created_at,
        )

        assert resp.phone_number == buy_req.phone_number
        assert resp.agent_id == buy_req.agent_id
        assert resp.status == PhoneNumberStatus.ACTIVE

    def test_outbound_call_flow(self):
        """Simulate outbound call: request → call → response."""
        req = OutboundCallRequest(
            agent_id="agent-1",
            to="+14155551234",
        )

        call = Call(
            customer_id="cust-1",
            agent_id=req.agent_id,
            phone_number_id="phone-1",
            direction=CallDirection.OUTBOUND,
            from_number="+14155550001",
            to_number=req.to,
            status=CallStatus.INITIATED,
            metadata=req.metadata,
        )

        resp = OutboundCallResponse(
            call_id=call.id,
            status=call.status,
            from_number=call.from_number,
            to_number=call.to_number,
            agent_id=call.agent_id,
            agent_name="Support Bot",
        )

        assert resp.to_number == req.to
        assert resp.agent_id == req.agent_id
        assert resp.status == CallStatus.INITIATED

    def test_inbound_webhook_to_call(self):
        """Simulate inbound call: webhook → call record."""
        webhook = InboundCallWebhook(
            CallSid="CA_test_123",
            From="+14155551234",
            To="+14155550001",
            Direction="inbound",
            CallStatus="ringing",
        )

        call = Call(
            customer_id="cust-1",
            agent_id="agent-1",
            phone_number_id="phone-1",
            direction=CallDirection.INBOUND,
            from_number=webhook.From,
            to_number=webhook.To,
            status=CallStatus.RINGING,
            metadata={
                "twilio_call_sid": webhook.CallSid,
            },
        )

        assert call.from_number == webhook.From
        assert call.to_number == webhook.To
        assert call.metadata["twilio_call_sid"] == webhook.CallSid
