"""Supabase database service.

Wraps all Supabase operations into clean async functions.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

from loguru import logger

from app.config import settings
from app.models.database import (
    Agent,
    AgentStatus,
    ApiKey,
    ApiKeyStatus,
    Call,
    CallStatus,
    Customer,
    PhoneNumber,
    PlanTier,
    Subscription,
    ToolCall,
    UsageRecord,
)

try:
    from supabase import create_client, Client
    _supabase: Client | None = None
except ImportError:
    _supabase = None


def get_client() -> Client:
    """Get or create the Supabase client."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    return _supabase


def _hash_key(key: str) -> str:
    """Hash an API key with SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def _generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, key_hash, key_prefix)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"vxb_{raw}"
    key_hash = _hash_key(full_key)
    key_prefix = full_key[:12]
    return full_key, key_hash, key_prefix


# ──────────────────────────────────────────────────────────────────
# Customer operations
# ──────────────────────────────────────────────────────────────────

def create_customer(email: str, name: str, password_hash: str) -> Customer:
    """Create a new customer."""
    client = get_client()
    customer = Customer(email=email, name=name, password_hash=password_hash)
    data = customer.model_dump()
    data["created_at"] = data["created_at"].isoformat()
    data["updated_at"] = data["updated_at"].isoformat()

    result = client.table("customers").insert(data).execute()
    return Customer(**result.data[0])


def get_customer_by_email(email: str) -> Customer | None:
    """Lookup customer by email."""
    client = get_client()
    result = client.table("customers").select("*").eq("email", email).execute()
    if result.data:
        return Customer(**result.data[0])
    return None


def get_customer_by_id(customer_id: str) -> Customer | None:
    """Lookup customer by ID."""
    client = get_client()
    result = client.table("customers").select("*").eq("id", customer_id).execute()
    if result.data:
        return Customer(**result.data[0])
    return None


def update_customer_plan(customer_id: str, plan: PlanTier) -> Customer | None:
    """Update a customer's plan tier."""
    client = get_client()
    result = (
        client.table("customers")
        .update({"plan": plan.value, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", customer_id)
        .execute()
    )
    if result.data:
        return Customer(**result.data[0])
    return None


def update_customer_stripe_id(customer_id: str, stripe_customer_id: str) -> None:
    """Set Stripe customer ID."""
    client = get_client()
    client.table("customers").update(
        {"stripe_customer_id": stripe_customer_id, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", customer_id).execute()


# ──────────────────────────────────────────────────────────────────
# API Key operations
# ──────────────────────────────────────────────────────────────────

def create_api_key(customer_id: str, name: str = "Default") -> tuple[ApiKey, str]:
    """Create a new API key. Returns (api_key_record, full_key_string)."""
    client = get_client()
    full_key, key_hash, key_prefix = _generate_api_key()

    api_key = ApiKey(
        customer_id=customer_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
    )
    data = api_key.model_dump()
    data["created_at"] = data["created_at"].isoformat()
    if data.get("last_used_at"):
        data["last_used_at"] = data["last_used_at"].isoformat()

    result = client.table("api_keys").insert(data).execute()
    return ApiKey(**result.data[0]), full_key


def get_api_keys_for_customer(customer_id: str) -> list[ApiKey]:
    """List all API keys for a customer."""
    client = get_client()
    result = (
        client.table("api_keys")
        .select("*")
        .eq("customer_id", customer_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [ApiKey(**row) for row in result.data]


def validate_api_key(key: str) -> tuple[ApiKey | None, Customer | None]:
    """Validate an API key. Returns (api_key, customer) or (None, None)."""
    client = get_client()
    key_hash = _hash_key(key)

    result = (
        client.table("api_keys")
        .select("*")
        .eq("key_hash", key_hash)
        .eq("status", "active")
        .execute()
    )

    if not result.data:
        return None, None

    api_key = ApiKey(**result.data[0])

    # Update last_used_at
    client.table("api_keys").update(
        {"last_used_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", api_key.id).execute()

    customer = get_customer_by_id(api_key.customer_id)
    return api_key, customer


def revoke_api_key(api_key_id: str, customer_id: str) -> bool:
    """Revoke an API key."""
    client = get_client()
    result = (
        client.table("api_keys")
        .update({"status": ApiKeyStatus.REVOKED.value})
        .eq("id", api_key_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    return len(result.data) > 0


# ──────────────────────────────────────────────────────────────────
# Usage tracking
# ──────────────────────────────────────────────────────────────────

def record_usage(
    customer_id: str,
    api_key_id: str,
    session_id: str,
    call_id: str = "",
    provider: str = "",
    duration_seconds: float = 0.0,
    audio_bytes_in: int = 0,
    audio_bytes_out: int = 0,
    status: str = "completed",
    metadata: dict | None = None,
) -> UsageRecord:
    """Record a usage event from the SDK."""
    client = get_client()
    record = UsageRecord(
        customer_id=customer_id,
        api_key_id=api_key_id,
        session_id=session_id,
        call_id=call_id,
        provider=provider,
        duration_seconds=duration_seconds,
        audio_bytes_in=audio_bytes_in,
        audio_bytes_out=audio_bytes_out,
        status=status,
        metadata=metadata or {},
    )
    data = record.model_dump()
    data["created_at"] = data["created_at"].isoformat()
    data["started_at"] = data["started_at"].isoformat()
    if data.get("ended_at"):
        data["ended_at"] = data["ended_at"].isoformat()

    result = client.table("usage_records").insert(data).execute()
    return UsageRecord(**result.data[0])


def get_usage_for_customer(
    customer_id: str,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[UsageRecord]:
    """Get usage records for a customer in a date range."""
    client = get_client()

    if start_date is None:
        # Default to current billing period (first of month)
        now = datetime.now(timezone.utc)
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if end_date is None:
        end_date = datetime.now(timezone.utc)

    result = (
        client.table("usage_records")
        .select("*")
        .eq("customer_id", customer_id)
        .gte("created_at", start_date.isoformat())
        .lte("created_at", end_date.isoformat())
        .order("created_at", desc=True)
        .execute()
    )
    return [UsageRecord(**row) for row in result.data]


def get_usage_summary(customer_id: str, plan: PlanTier) -> dict:
    """Get aggregated usage summary for dashboard."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    records = get_usage_for_customer(customer_id, period_start, now)

    total_seconds = sum(r.duration_seconds for r in records)
    total_minutes = total_seconds / 60.0
    total_calls = len(records)

    # Plan limits
    plan_limits = {
        PlanTier.FREE: settings.free_plan_minutes,
        PlanTier.PRO: settings.pro_plan_minutes,
        PlanTier.ENTERPRISE: settings.enterprise_plan_minutes,
    }
    limit = plan_limits.get(plan, 100)

    # Daily breakdown
    daily: dict[str, float] = {}
    for r in records:
        day = r.created_at.strftime("%Y-%m-%d")
        daily[day] = daily.get(day, 0) + r.duration_seconds / 60.0

    # Provider breakdown
    providers: dict[str, int] = {}
    for r in records:
        providers[r.provider] = providers.get(r.provider, 0) + 1

    return {
        "total_minutes": round(total_minutes, 2),
        "total_calls": total_calls,
        "plan_minutes_limit": limit,
        "minutes_remaining": round(max(0, limit - total_minutes), 2),
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "daily_usage": [{"date": k, "minutes": round(v, 2)} for k, v in sorted(daily.items())],
        "provider_breakdown": [{"provider": k, "calls": v} for k, v in providers.items()],
    }


def check_usage_limit(customer_id: str, plan: PlanTier) -> tuple[bool, float]:
    """Check if customer is within their usage limit. Returns (allowed, remaining_minutes)."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    records = get_usage_for_customer(customer_id, period_start, now)

    total_seconds = sum(r.duration_seconds for r in records)
    total_minutes = total_seconds / 60.0

    plan_limits = {
        PlanTier.FREE: settings.free_plan_minutes,
        PlanTier.PRO: settings.pro_plan_minutes,
        PlanTier.ENTERPRISE: settings.enterprise_plan_minutes,
    }
    limit = plan_limits.get(plan, 100)
    remaining = limit - total_minutes

    return remaining > 0, round(remaining, 2)


# ──────────────────────────────────────────────────────────────────
# Subscription operations
# ──────────────────────────────────────────────────────────────────

def create_subscription(
    customer_id: str,
    stripe_subscription_id: str,
    plan: PlanTier,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> Subscription:
    """Create a subscription record."""
    client = get_client()
    sub = Subscription(
        customer_id=customer_id,
        stripe_subscription_id=stripe_subscription_id,
        plan=plan,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
    )
    data = sub.model_dump()
    data["created_at"] = data["created_at"].isoformat()
    if data.get("current_period_start"):
        data["current_period_start"] = data["current_period_start"].isoformat()
    if data.get("current_period_end"):
        data["current_period_end"] = data["current_period_end"].isoformat()

    result = client.table("subscriptions").insert(data).execute()
    return Subscription(**result.data[0])


def get_active_subscription(customer_id: str) -> Subscription | None:
    """Get active subscription for a customer."""
    client = get_client()
    result = (
        client.table("subscriptions")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return Subscription(**result.data[0])
    return None


# ──────────────────────────────────────────────────────────────────
# Agent operations
# ──────────────────────────────────────────────────────────────────

def create_agent(customer_id: str, data: dict) -> Agent:
    """Create a new AI agent."""
    client = get_client()
    agent = Agent(customer_id=customer_id, **data)
    row = agent.model_dump()
    row["created_at"] = row["created_at"].isoformat()
    row["updated_at"] = row["updated_at"].isoformat()
    # JSONB fields need to be serializable (already are as list/dict)
    result = client.table("agents").insert(row).execute()
    return Agent(**result.data[0])


def get_agent(agent_id: str, customer_id: str) -> Agent | None:
    """Get a single agent by ID, scoped to customer."""
    client = get_client()
    result = (
        client.table("agents")
        .select("*")
        .eq("id", agent_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if result.data:
        return Agent(**result.data[0])
    return None


def list_agents(customer_id: str) -> list[Agent]:
    """List all agents for a customer."""
    client = get_client()
    result = (
        client.table("agents")
        .select("*")
        .eq("customer_id", customer_id)
        .neq("status", "archived")
        .order("created_at", desc=True)
        .execute()
    )
    return [Agent(**row) for row in result.data]


def update_agent(agent_id: str, customer_id: str, updates: dict) -> Agent | None:
    """Update an agent. Only non-None fields are applied."""
    client = get_client()
    # Filter out None values
    changes = {k: v for k, v in updates.items() if v is not None}
    if not changes:
        return get_agent(agent_id, customer_id)

    changes["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = (
        client.table("agents")
        .update(changes)
        .eq("id", agent_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if result.data:
        return Agent(**result.data[0])
    return None


def delete_agent(agent_id: str, customer_id: str) -> bool:
    """Soft-delete an agent by setting status to archived."""
    client = get_client()
    result = (
        client.table("agents")
        .update({
            "status": AgentStatus.ARCHIVED.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", agent_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    return len(result.data) > 0


def count_agents(customer_id: str) -> int:
    """Count active (non-archived) agents for a customer."""
    client = get_client()
    result = (
        client.table("agents")
        .select("id", count="exact")
        .eq("customer_id", customer_id)
        .neq("status", "archived")
        .execute()
    )
    return result.count or 0


# ──────────────────────────────────────────────────────────────────
# Call operations
# ──────────────────────────────────────────────────────────────────

def create_call(data: dict) -> Call:
    """Create a call record."""
    client = get_client()
    call = Call(**data)
    row = call.model_dump()
    row["created_at"] = row["created_at"].isoformat()
    row["started_at"] = row["started_at"].isoformat()
    if row.get("ended_at"):
        row["ended_at"] = row["ended_at"].isoformat()
    result = client.table("calls").insert(row).execute()
    return Call(**result.data[0])


def get_call(call_id: str, customer_id: str) -> Call | None:
    """Get a single call by ID, scoped to customer."""
    client = get_client()
    result = (
        client.table("calls")
        .select("*")
        .eq("id", call_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if result.data:
        return Call(**result.data[0])
    return None


def list_calls(
    customer_id: str,
    agent_id: str | None = None,
    status: str | None = None,
    direction: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Call], int]:
    """List calls for a customer with optional filters. Returns (calls, total_count)."""
    client = get_client()
    query = (
        client.table("calls")
        .select("*", count="exact")
        .eq("customer_id", customer_id)
    )

    if agent_id:
        query = query.eq("agent_id", agent_id)
    if status:
        query = query.eq("status", status)
    if direction:
        query = query.eq("direction", direction)

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    result = query.execute()

    calls = [Call(**row) for row in result.data]
    total = result.count or len(calls)
    return calls, total


def update_call(call_id: str, updates: dict) -> Call | None:
    """Update a call record (used for in-progress updates)."""
    client = get_client()
    if "ended_at" in updates and updates["ended_at"]:
        updates["ended_at"] = updates["ended_at"].isoformat() if hasattr(updates["ended_at"], "isoformat") else updates["ended_at"]

    result = (
        client.table("calls")
        .update(updates)
        .eq("id", call_id)
        .execute()
    )
    if result.data:
        return Call(**result.data[0])
    return None


def get_calls_for_agent(
    agent_id: str,
    customer_id: str,
    start_date: datetime | None = None,
) -> list[Call]:
    """Get all calls for an agent, optionally filtered by start date."""
    client = get_client()
    query = (
        client.table("calls")
        .select("*")
        .eq("agent_id", agent_id)
        .eq("customer_id", customer_id)
    )
    if start_date:
        query = query.gte("created_at", start_date.isoformat())

    result = query.order("created_at", desc=True).execute()
    return [Call(**row) for row in result.data]


def get_agent_stats(agent_id: str, customer_id: str) -> dict:
    """Compute performance stats for an agent."""
    # Get all calls for this agent
    calls = get_calls_for_agent(agent_id, customer_id)

    total = len(calls)
    if total == 0:
        return {
            "total_calls": 0,
            "completed_calls": 0,
            "failed_calls": 0,
            "escalated_calls": 0,
            "avg_duration_seconds": 0.0,
            "total_duration_minutes": 0.0,
            "avg_sentiment": None,
            "resolution_rate": 0.0,
            "containment_rate": 0.0,
            "total_cost_cents": 0,
            "calls_by_day": [],
        }

    completed = sum(1 for c in calls if c.status == CallStatus.COMPLETED)
    failed = sum(1 for c in calls if c.status == CallStatus.FAILED)
    escalated = sum(1 for c in calls if c.escalated_to_human)
    total_duration = sum(c.duration_seconds for c in calls)
    total_cost = sum(c.cost_cents for c in calls)

    sentiments = [c.sentiment_score for c in calls if c.sentiment_score is not None]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

    resolved = sum(1 for c in calls if c.resolution == "resolved")
    resolution_rate = (resolved / total * 100) if total > 0 else 0.0
    containment_rate = ((total - escalated) / total * 100) if total > 0 else 0.0

    # Daily breakdown
    daily: dict[str, int] = {}
    for c in calls:
        day = c.created_at.strftime("%Y-%m-%d")
        daily[day] = daily.get(day, 0) + 1

    return {
        "total_calls": total,
        "completed_calls": completed,
        "failed_calls": failed,
        "escalated_calls": escalated,
        "avg_duration_seconds": round(total_duration / total, 2),
        "total_duration_minutes": round(total_duration / 60.0, 2),
        "avg_sentiment": round(avg_sentiment, 3) if avg_sentiment is not None else None,
        "resolution_rate": round(resolution_rate, 1),
        "containment_rate": round(containment_rate, 1),
        "total_cost_cents": total_cost,
        "calls_by_day": [{"date": k, "calls": v} for k, v in sorted(daily.items())],
    }


# ──────────────────────────────────────────────────────────────────
# Tool Call operations
# ──────────────────────────────────────────────────────────────────

def create_tool_call(data: dict) -> ToolCall:
    """Record a tool/function call made during a call."""
    client = get_client()
    tool_call = ToolCall(**data)
    row = tool_call.model_dump()
    row["created_at"] = row["created_at"].isoformat()
    result = client.table("tool_calls").insert(row).execute()
    return ToolCall(**result.data[0])


def get_tool_calls_for_call(call_id: str) -> list[ToolCall]:
    """Get all tool calls for a given call."""
    client = get_client()
    result = (
        client.table("tool_calls")
        .select("*")
        .eq("call_id", call_id)
        .order("created_at")
        .execute()
    )
    return [ToolCall(**row) for row in result.data]


# ──────────────────────────────────────────────────────────────────
# Phone Number operations
# ──────────────────────────────────────────────────────────────────

def create_phone_number(data: dict) -> PhoneNumber:
    """Create a phone number record."""
    client = get_client()
    phone = PhoneNumber(**data)
    row = phone.model_dump()
    row["created_at"] = row["created_at"].isoformat()
    result = client.table("phone_numbers").insert(row).execute()
    return PhoneNumber(**result.data[0])


def list_phone_numbers(customer_id: str) -> list[PhoneNumber]:
    """List all phone numbers for a customer."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .select("*")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    return [PhoneNumber(**row) for row in result.data]


def assign_phone_number(phone_id: str, customer_id: str, agent_id: str | None) -> PhoneNumber | None:
    """Assign or unassign a phone number to/from an agent."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .update({"agent_id": agent_id})
        .eq("id", phone_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if result.data:
        return PhoneNumber(**result.data[0])
    return None


def get_phone_number(phone_id: str, customer_id: str) -> PhoneNumber | None:
    """Get a single phone number by ID, scoped to customer."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .select("*")
        .eq("id", phone_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    if result.data:
        return PhoneNumber(**result.data[0])
    return None


def get_phone_number_by_number(phone_number: str) -> PhoneNumber | None:
    """Look up a phone number record by E.164 number (for inbound routing)."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .select("*")
        .eq("phone_number", phone_number)
        .eq("status", "active")
        .execute()
    )
    if result.data:
        return PhoneNumber(**result.data[0])
    return None


def release_phone_number(phone_id: str, customer_id: str) -> bool:
    """Mark a phone number as released."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .update({"status": "released", "agent_id": None})
        .eq("id", phone_id)
        .eq("customer_id", customer_id)
        .execute()
    )
    return len(result.data) > 0


def count_phone_numbers(customer_id: str) -> int:
    """Count active phone numbers for a customer."""
    client = get_client()
    result = (
        client.table("phone_numbers")
        .select("id", count="exact")
        .eq("customer_id", customer_id)
        .eq("status", "active")
        .execute()
    )
    return result.count or 0


# ──────────────────────────────────────────────────────────────────
# Cost calculation
# ──────────────────────────────────────────────────────────────────

def calculate_call_cost(duration_seconds: float, cost_per_minute_cents: int = 6) -> int:
    """Calculate call cost in cents based on duration.

    Args:
        duration_seconds: Call duration in seconds.
        cost_per_minute_cents: Cost per minute in cents (default: 6 = $0.06/min).

    Returns:
        Cost in cents (rounded up to nearest cent).
    """
    minutes = duration_seconds / 60.0
    cost = minutes * cost_per_minute_cents
    return max(1, int(cost + 0.5))  # minimum 1 cent, round half up
