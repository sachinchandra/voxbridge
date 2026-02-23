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


# ──────────────────────────────────────────────────────────────────
# Phone Number API Schemas
# ──────────────────────────────────────────────────────────────────

class PhoneNumberSearchRequest(BaseModel):
    """Search for available phone numbers."""
    country: str = "US"
    area_code: str | None = None
    contains: str | None = None  # number pattern search
    limit: int = 10


class PhoneNumberSearchResult(BaseModel):
    """A single available phone number from search results."""
    phone_number: str
    friendly_name: str = ""
    country: str = "US"
    region: str = ""
    capabilities: list[str] = Field(default_factory=lambda: ["voice"])
    monthly_cost_cents: int = 100  # ~$1/month


class PhoneNumberBuyRequest(BaseModel):
    """Buy a phone number and optionally assign to an agent."""
    phone_number: str  # E.164 format
    agent_id: str | None = None


class PhoneNumberResponse(BaseModel):
    """Phone number data returned by the API."""
    id: str
    phone_number: str
    provider: str
    country: str
    capabilities: list[str]
    status: PhoneNumberStatus
    agent_id: str | None
    agent_name: str = ""
    created_at: datetime


class PhoneNumberUpdate(BaseModel):
    """Update a phone number (reassign agent)."""
    agent_id: str | None = None


# ──────────────────────────────────────────────────────────────────
# Outbound Call API Schemas
# ──────────────────────────────────────────────────────────────────

class OutboundCallRequest(BaseModel):
    """Request to initiate an outbound call."""
    agent_id: str
    to: str  # E.164 phone number
    from_number_id: str | None = None  # specific phone number to call from
    metadata: dict = Field(default_factory=dict)


class OutboundCallResponse(BaseModel):
    """Response after initiating an outbound call."""
    call_id: str
    status: CallStatus
    from_number: str
    to_number: str
    agent_id: str
    agent_name: str = ""


# ──────────────────────────────────────────────────────────────────
# Webhook Schemas
# ──────────────────────────────────────────────────────────────────

class InboundCallWebhook(BaseModel):
    """Data from inbound call webhook (Twilio format)."""
    CallSid: str = ""
    From: str = ""
    To: str = ""
    Direction: str = "inbound"
    CallStatus: str = ""
    AccountSid: str = ""


# ──────────────────────────────────────────────────────────────────
# Knowledge Base Models + Schemas
# ──────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeBase(BaseModel):
    """A knowledge base for RAG — a collection of documents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    name: str = "New Knowledge Base"
    description: str = ""
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 512
    chunk_overlap: int = 50
    document_count: int = 0
    total_chunks: int = 0
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Document(BaseModel):
    """A document within a knowledge base."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    knowledge_base_id: str
    customer_id: str
    filename: str = ""
    content_type: str = ""  # text/plain, application/pdf, etc.
    source_url: str = ""
    file_size_bytes: int = 0
    chunk_count: int = 0
    status: DocumentStatus = DocumentStatus.PROCESSING
    error_message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentChunk(BaseModel):
    """An embedded chunk of a document for vector search."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    knowledge_base_id: str
    chunk_index: int = 0
    content: str = ""
    embedding: list[float] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)  # page, section, etc.
    token_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# KB API Schemas

class KnowledgeBaseCreate(BaseModel):
    """Create a knowledge base."""
    name: str = "New Knowledge Base"
    description: str = ""
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 512
    chunk_overlap: int = 50


class KnowledgeBaseUpdate(BaseModel):
    """Update a knowledge base."""
    name: str | None = None
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    """Knowledge base API response."""
    id: str
    name: str
    description: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    document_count: int
    total_chunks: int
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    """Document API response."""
    id: str
    knowledge_base_id: str
    filename: str
    content_type: str
    source_url: str
    file_size_bytes: int
    chunk_count: int
    status: DocumentStatus
    error_message: str
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    id: str
    filename: str
    status: DocumentStatus
    message: str = "Document queued for processing"


class VectorSearchResult(BaseModel):
    """A single vector search result."""
    chunk_id: str
    document_id: str
    content: str
    similarity: float
    metadata: dict = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────
# Quality Assurance Models
# ──────────────────────────────────────────────────────────────────

class CallQAScore(BaseModel):
    """Automated QA score for a call."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    call_id: str
    customer_id: str
    agent_id: str
    # Individual scores (0-100)
    accuracy_score: int = 0  # Did AI provide correct information?
    tone_score: int = 0  # Was the tone appropriate?
    resolution_score: int = 0  # Was the issue resolved?
    compliance_score: int = 0  # Did AI follow the script/rules?
    overall_score: int = 0  # Weighted average
    # Flags
    pii_detected: bool = False  # PII exposed in transcript?
    angry_caller: bool = False  # Caller was angry/frustrated?
    flagged: bool = False  # Needs human review?
    flag_reasons: list[str] = Field(default_factory=list)
    # AI-generated summary
    summary: str = ""
    improvement_suggestions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QAScoreResponse(BaseModel):
    """QA score API response."""
    id: str
    call_id: str
    agent_id: str
    accuracy_score: int
    tone_score: int
    resolution_score: int
    compliance_score: int
    overall_score: int
    pii_detected: bool
    angry_caller: bool
    flagged: bool
    flag_reasons: list[str]
    summary: str
    improvement_suggestions: list[str]
    created_at: datetime


class QASummary(BaseModel):
    """QA summary for the dashboard."""
    total_scored: int = 0
    avg_overall: float = 0.0
    avg_accuracy: float = 0.0
    avg_tone: float = 0.0
    avg_resolution: float = 0.0
    avg_compliance: float = 0.0
    flagged_count: int = 0
    pii_count: int = 0
    angry_count: int = 0
    score_distribution: list[dict] = Field(default_factory=list)  # [{range, count}]
    top_flag_reasons: list[dict] = Field(default_factory=list)  # [{reason, count}]


class AnalyticsDetail(BaseModel):
    """Enhanced analytics response with sentiment, peak hours, etc."""
    total_calls: int = 0
    ai_handled: int = 0
    escalated: int = 0
    containment_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    total_cost_cents: int = 0
    total_cost_dollars: float = 0.0
    # Sentiment breakdown
    sentiment_positive: int = 0
    sentiment_neutral: int = 0
    sentiment_negative: int = 0
    # Peak hours (0-23 → call count)
    calls_by_hour: list[dict] = Field(default_factory=list)
    # Escalation reasons
    escalation_reasons: list[dict] = Field(default_factory=list)
    # Resolution breakdown
    resolved: int = 0
    abandoned: int = 0
    # Calls by day (for trends)
    calls_by_day: list[dict] = Field(default_factory=list)
    # Agent leaderboard
    agent_rankings: list[dict] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────
# Playground models
# ──────────────────────────────────────────────────────────────────

class PlaygroundMessage(BaseModel):
    """A single message in a playground test session."""
    role: str = "user"  # user | assistant | system | tool
    content: str = ""
    timestamp: float = 0.0
    tool_call: dict | None = None  # {name, arguments, result, duration_ms}
    latency_ms: int = 0  # Time to generate this message


class PlaygroundSession(BaseModel):
    """An in-browser test conversation with an AI agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    agent_id: str = ""
    agent_name: str = ""
    messages: list[PlaygroundMessage] = Field(default_factory=list)
    status: str = "active"  # active | completed | error
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    total_turns: int = 0
    total_tokens: int = 0
    estimated_cost_cents: int = 0
    error: str = ""


class PlaygroundRequest(BaseModel):
    """Request to send a message in a playground session."""
    message: str = ""
    session_id: str | None = None  # None = start new session


class PlaygroundResponse(BaseModel):
    """Response from a playground turn."""
    session_id: str
    reply: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    done: bool = False
    latency_ms: int = 0
    tokens_used: int = 0


# ──────────────────────────────────────────────────────────────────
# QA Email models
# ──────────────────────────────────────────────────────────────────

class QAWeeklyReport(BaseModel):
    """Weekly QA summary email data."""
    customer_id: str = ""
    customer_email: str = ""
    customer_name: str = ""
    period_start: str = ""
    period_end: str = ""
    total_calls_scored: int = 0
    avg_overall_score: float = 0.0
    avg_accuracy: float = 0.0
    avg_tone: float = 0.0
    avg_resolution: float = 0.0
    avg_compliance: float = 0.0
    flagged_calls: int = 0
    pii_detections: int = 0
    angry_callers: int = 0
    top_issues: list[str] = Field(default_factory=list)
    top_agents: list[dict] = Field(default_factory=list)  # [{name, score, calls}]
    improvement_areas: list[str] = Field(default_factory=list)
    score_trend: str = "stable"  # improving | stable | declining


# ──────────────────────────────────────────────────────────────────
# Conversation Flow models
# ──────────────────────────────────────────────────────────────────

class FlowNodeType(str, Enum):
    START = "start"
    MESSAGE = "message"          # AI speaks a scripted message
    LISTEN = "listen"            # Wait for user input
    AI_RESPOND = "ai_respond"    # Free-form AI response using LLM
    CONDITION = "condition"      # Branch based on intent/keyword/sentiment
    TOOL_CALL = "tool_call"      # Execute a function/API call
    TRANSFER = "transfer"        # Escalate to human
    END = "end"


class FlowNode(BaseModel):
    """A single node in a conversation flow."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: FlowNodeType = FlowNodeType.MESSAGE
    label: str = ""
    # Position for visual canvas
    x: float = 0.0
    y: float = 0.0
    # Config varies by type
    config: dict = Field(default_factory=dict)
    # config examples:
    #   message: {text: "Hello! How can I help?"}
    #   listen: {timeout_seconds: 10, no_input_node_id: "..."}
    #   ai_respond: {system_prompt_override: "", max_tokens: 200}
    #   condition: {rules: [{match: "refund|return", target_node_id: "..."}, {match: "*", target_node_id: "..."}]}
    #   tool_call: {tool_name: "check_order", input_map: {"order_id": "{{user_input}}"}}
    #   transfer: {target_number: "+1...", context_summary: true}


class FlowEdge(BaseModel):
    """Connection between two nodes."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    label: str = ""  # edge label for condition branches
    condition: str = ""  # optional: keyword match, intent, default


class ConversationFlow(BaseModel):
    """A complete conversation flow (visual decision tree)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    agent_id: str = ""
    name: str = ""
    description: str = ""
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    is_active: bool = False
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class FlowVersion(BaseModel):
    """Versioned snapshot of a flow for A/B testing."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flow_id: str = ""
    version: int = 1
    name: str = ""  # e.g. "Variant A", "Variant B"
    nodes: list[FlowNode] = Field(default_factory=list)
    edges: list[FlowEdge] = Field(default_factory=list)
    traffic_percent: int = 100  # 0-100, for A/B split
    calls_count: int = 0
    avg_resolution_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FlowTestResult(BaseModel):
    """Result of simulating a flow with test input."""
    flow_id: str = ""
    version: int = 1
    path: list[str] = Field(default_factory=list)  # node IDs traversed
    messages: list[dict] = Field(default_factory=list)  # conversation transcript
    completed: bool = False
    end_reason: str = ""  # completed | transfer | timeout | error
    duration_ms: int = 0


# ──────────────────────────────────────────────────────────────────
# Alert models
# ──────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    HIGH_VOLUME = "high_volume"
    ANGRY_CALLER_SPIKE = "angry_caller_spike"
    LOW_QUALITY_SCORE = "low_quality_score"
    HIGH_ESCALATION_RATE = "high_escalation_rate"
    PII_DETECTED = "pii_detected"
    AGENT_DOWN = "agent_down"
    API_FAILURE = "api_failure"
    COST_THRESHOLD = "cost_threshold"


class AlertRule(BaseModel):
    """A customer-defined alert trigger rule."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    name: str = ""
    alert_type: AlertType = AlertType.HIGH_VOLUME
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    # Threshold config
    config: dict = Field(default_factory=dict)
    # config examples:
    #   high_volume: {threshold: 100, window_minutes: 60}
    #   angry_caller_spike: {threshold: 5, window_minutes: 30}
    #   low_quality_score: {threshold: 50, agent_id: "optional"}
    #   high_escalation_rate: {threshold_percent: 40, min_calls: 10}
    #   pii_detected: {}  (always triggers)
    #   cost_threshold: {daily_limit_cents: 10000}
    # Notification channels
    notify_email: bool = True
    notify_webhook: str = ""  # optional webhook URL
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class Alert(BaseModel):
    """A triggered alert instance."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    rule_id: str = ""
    alert_type: AlertType = AlertType.HIGH_VOLUME
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = ""
    message: str = ""
    metadata: dict = Field(default_factory=dict)  # context data
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}


class AlertSummary(BaseModel):
    """Dashboard summary of alerts."""
    total: int = 0
    unacknowledged: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    recent: list[Alert] = Field(default_factory=list)
