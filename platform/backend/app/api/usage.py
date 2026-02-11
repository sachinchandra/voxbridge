"""Usage tracking API routes.

Two types of endpoints:
1. SDK-facing: POST /usage/report (authenticated via API key)
2. Dashboard-facing: GET /usage/summary (authenticated via JWT)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_customer
from app.models.database import Customer, UsageReportRequest, UsageSummary
from app.services.database import (
    check_usage_limit,
    get_usage_summary,
    record_usage,
    validate_api_key,
)

router = APIRouter(prefix="/usage", tags=["Usage"])


@router.post("/report", status_code=status.HTTP_201_CREATED)
async def report_usage(body: UsageReportRequest):
    """Report call usage from the SDK. Authenticated via API key (not JWT).

    Called automatically by the VoxBridge SDK at the end of each call.
    """
    # Validate API key
    api_key, customer = validate_api_key(body.api_key)
    if api_key is None or customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check usage limits
    allowed, remaining = check_usage_limit(customer.id, customer.plan)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Usage limit exceeded. Plan: {customer.plan.value}, remaining: {remaining} minutes",
        )

    # Record usage
    record = record_usage(
        customer_id=customer.id,
        api_key_id=api_key.id,
        session_id=body.session_id,
        call_id=body.call_id,
        provider=body.provider,
        duration_seconds=body.duration_seconds,
        audio_bytes_in=body.audio_bytes_in,
        audio_bytes_out=body.audio_bytes_out,
        status=body.status,
        metadata=body.metadata,
    )

    return {"status": "recorded", "id": record.id, "minutes_remaining": remaining}


@router.post("/validate-key")
async def validate_key(body: dict):
    """Validate an API key and return plan info. Called by SDK on startup."""
    key = body.get("api_key", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required",
        )

    api_key, customer = validate_api_key(key)
    if api_key is None or customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    allowed, remaining = check_usage_limit(customer.id, customer.plan)

    return {
        "valid": True,
        "customer_id": customer.id,
        "plan": customer.plan.value,
        "minutes_remaining": remaining,
        "allowed": allowed,
    }


@router.get("/summary", response_model=UsageSummary)
async def usage_summary(customer: Customer = Depends(get_current_customer)):
    """Get usage summary for the dashboard."""
    summary = get_usage_summary(customer.id, customer.plan)
    return UsageSummary(**summary)


@router.get("/history")
async def usage_history(
    limit: int = 50,
    customer: Customer = Depends(get_current_customer),
):
    """Get recent usage records for the dashboard."""
    from app.services.database import get_usage_for_customer

    records = get_usage_for_customer(customer.id)
    records = records[:limit]

    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "call_id": r.call_id,
            "provider": r.provider,
            "duration_seconds": r.duration_seconds,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
