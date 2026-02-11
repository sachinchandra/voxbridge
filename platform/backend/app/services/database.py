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
    ApiKey,
    ApiKeyStatus,
    Customer,
    PlanTier,
    Subscription,
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
