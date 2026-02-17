"""Database models for VoxBridge Platform.

Uses Supabase (PostgreSQL) with SQLAlchemy for type-safe queries.
Tables: customers, api_keys, usage_records, subscriptions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────

class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class AgentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"


class PhoneNumberStatus(str, Enum):
    ACTIVE = "active"
    RELEASED = "released"
    PENDING = "pending"


# ──────────────────────────────────────────────────────────────────
# Pydantic models (map to Supabase tables)
# ──────────────────────────────────────────────────────────────────

class Customer(BaseModel):
    """A VoxBridge platform customer."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str = ""
    password_hash: str = ""
    plan: PlanTier = PlanTier.FREE
    stripe_customer_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class ApiKey(BaseModel):
    """An API key that SDK users authenticate with."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    key_hash: str  # SHA-256 hash of the actual key
    key_prefix: str  # First 8 chars for display: "vxb_xxxx..."
    name: str = "Default"
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE
    last_used_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class UsageRecord(BaseModel):
    """A single call usage record reported by the SDK."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    api_key_id: str
    session_id: str  # VoxBridge session_id
    call_id: str = ""
    provider: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    duration_seconds: float = 0.0
    audio_bytes_in: int = 0
    audio_bytes_out: int = 0
    status: str = "active"  # active, completed, error
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class Subscription(BaseModel):
    """Stripe subscription record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    stripe_subscription_id: str
    plan: PlanTier = PlanTier.PRO
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class Agent(BaseModel):
    """An AI agent configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    name: str = "New Agent"
    status: AgentStatus = AgentStatus.DRAFT

    # AI Configuration
    system_prompt: str = ""
    first_message: str = ""
    end_call_phrases: list[str] = Field(default_factory=list)

    # STT config
    stt_provider: str = "deepgram"
    stt_config: dict = Field(default_factory=dict)

    # LLM config
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_config: dict = Field(default_factory=dict)

    # TTS config
    tts_provider: str = "elevenlabs"
    tts_voice_id: str = ""
    tts_config: dict = Field(default_factory=dict)

    # Behavior
    max_duration_seconds: int = 300  # 5 min default
    interruption_enabled: bool = True

    # Function calling / tools
    tools: list[dict] = Field(default_factory=list)
    knowledge_base_id: str | None = None

    # Escalation
    escalation_config: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class PhoneNumber(BaseModel):
    """A phone number assigned to an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    agent_id: str | None = None
    phone_number: str  # E.164 format
    provider: str = "twilio"  # twilio, telnyx
    provider_sid: str = ""
    country: str = "US"
    capabilities: list[str] = Field(default_factory=lambda: ["voice"])
    status: PhoneNumberStatus = PhoneNumberStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class Call(BaseModel):
    """A call record — every call through the platform."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    agent_id: str
    phone_number_id: str | None = None
    direction: CallDirection = CallDirection.INBOUND
    from_number: str = ""
    to_number: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    duration_seconds: float = 0.0
    status: CallStatus = CallStatus.INITIATED
    end_reason: str = ""
    transcript: list[dict] = Field(default_factory=list)  # [{role, content, timestamp}]
    recording_url: str = ""
    sentiment_score: float | None = None
    resolution: str = ""  # resolved, escalated, abandoned
    escalated_to_human: bool = False
    cost_cents: int = 0
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class ToolCall(BaseModel):
    """A function/tool call made during a call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    call_id: str
    agent_id: str
    function_name: str
    arguments: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────
# API Schemas (request/response)
# ──────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    email: str
    password: str
    name: str = ""


class CustomerLogin(BaseModel):
    email: str
    password: str


class CustomerResponse(BaseModel):
    id: str
    email: str
    name: str
    plan: PlanTier
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = "Default"


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    status: ApiKeyStatus
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only at creation time - includes the full key."""
    key: str  # full key, only shown once


class UsageReportRequest(BaseModel):
    """Sent by the SDK to report call usage."""
    api_key: str
    session_id: str
    call_id: str = ""
    provider: str = ""
    duration_seconds: float = 0.0
    audio_bytes_in: int = 0
    audio_bytes_out: int = 0
    status: str = "completed"
    metadata: dict = Field(default_factory=dict)


class UsageSummary(BaseModel):
    """Aggregated usage data for dashboard."""
    total_minutes: float = 0.0
    total_calls: int = 0
    plan_minutes_limit: int = 100
    minutes_remaining: float = 100.0
    period_start: datetime | None = None
    period_end: datetime | None = None
    daily_usage: list[dict] = Field(default_factory=list)
    provider_breakdown: list[dict] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerResponse


# ──────────────────────────────────────────────────────────────────
# Agent API Schemas
# ──────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    """Create a new AI agent."""
    name: str = "New Agent"
    system_prompt: str = ""
    first_message: str = ""
    end_call_phrases: list[str] = Field(default_factory=list)
    stt_provider: str = "deepgram"
    stt_config: dict = Field(default_factory=dict)
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_config: dict = Field(default_factory=dict)
    tts_provider: str = "elevenlabs"
    tts_voice_id: str = ""
    tts_config: dict = Field(default_factory=dict)
    max_duration_seconds: int = 300
    interruption_enabled: bool = True
    tools: list[dict] = Field(default_factory=list)
    knowledge_base_id: str | None = None
    escalation_config: dict = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    """Update an existing AI agent. All fields optional."""
    name: str | None = None
    status: AgentStatus | None = None
    system_prompt: str | None = None
    first_message: str | None = None
    end_call_phrases: list[str] | None = None
    stt_provider: str | None = None
    stt_config: dict | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_config: dict | None = None
    tts_provider: str | None = None
    tts_voice_id: str | None = None
    tts_config: dict | None = None
    max_duration_seconds: int | None = None
    interruption_enabled: bool | None = None
    tools: list[dict] | None = None
    knowledge_base_id: str | None = None
    escalation_config: dict | None = None


class AgentResponse(BaseModel):
    """Agent data returned by the API."""
    id: str
    name: str
    status: AgentStatus
    system_prompt: str
    first_message: str
    end_call_phrases: list[str]
    stt_provider: str
    stt_config: dict
    llm_provider: str
    llm_model: str
    llm_config: dict
    tts_provider: str
    tts_voice_id: str
    tts_config: dict
    max_duration_seconds: int
    interruption_enabled: bool
    tools: list[dict]
    knowledge_base_id: str | None
    escalation_config: dict
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Compact agent for list views."""
    id: str
    name: str
    status: AgentStatus
    llm_provider: str
    llm_model: str
    tts_provider: str
    total_calls: int = 0
    avg_duration: float = 0.0
    created_at: datetime


class AgentStatsResponse(BaseModel):
    """Agent performance statistics."""
    agent_id: str
    agent_name: str
    total_calls: int = 0
    completed_calls: int = 0
    failed_calls: int = 0
    escalated_calls: int = 0
    avg_duration_seconds: float = 0.0
    total_duration_minutes: float = 0.0
    avg_sentiment: float | None = None
    resolution_rate: float = 0.0
    containment_rate: float = 0.0  # % handled without human
    total_cost_cents: int = 0
    calls_by_day: list[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Call API Schemas
# ──────────────────────────────────────────────────────────────────

class CallResponse(BaseModel):
    """Call data returned by the API."""
    id: str
    agent_id: str
    agent_name: str = ""
    direction: CallDirection
    from_number: str
    to_number: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: float
    status: CallStatus
    end_reason: str
    escalated_to_human: bool
    sentiment_score: float | None
    resolution: str
    cost_cents: int
    created_at: datetime


class CallDetailResponse(CallResponse):
    """Full call detail including transcript."""
    transcript: list[dict]
    recording_url: str
    metadata: dict
    tool_calls: list[dict] = Field(default_factory=list)


class CallListParams(BaseModel):
    """Query params for listing calls."""
    agent_id: str | None = None
    status: CallStatus | None = None
    direction: CallDirection | None = None
    search: str | None = None  # keyword search in transcript
    limit: int = 50
    offset: int = 0
