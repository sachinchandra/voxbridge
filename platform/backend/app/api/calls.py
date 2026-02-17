"""Call management API routes.

Provides call history, call detail with transcript, and call search.
Calls are created by the platform pipeline (not directly by users),
but users view and search them via these endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth import get_current_customer
from app.models.database import (
    CallDetailResponse,
    CallDirection,
    CallResponse,
    CallStatus,
    Customer,
)
from app.services.database import (
    get_agent,
    get_call,
    get_tool_calls_for_call,
    list_calls,
)

router = APIRouter(prefix="/calls", tags=["Calls"])


def _call_to_response(call, agent_name: str = "") -> CallResponse:
    """Convert a Call model to a CallResponse."""
    return CallResponse(
        id=call.id,
        agent_id=call.agent_id,
        agent_name=agent_name,
        direction=call.direction,
        from_number=call.from_number,
        to_number=call.to_number,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        status=call.status,
        end_reason=call.end_reason,
        escalated_to_human=call.escalated_to_human,
        sentiment_score=call.sentiment_score,
        resolution=call.resolution,
        cost_cents=call.cost_cents,
        created_at=call.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# List / Search
# ──────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
async def list_all_calls(
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    call_status: CallStatus | None = Query(None, alias="status", description="Filter by call status"),
    direction: CallDirection | None = Query(None, description="Filter by direction"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    customer: Customer = Depends(get_current_customer),
):
    """List calls with optional filters. Returns paginated results."""
    calls, total = list_calls(
        customer_id=customer.id,
        agent_id=agent_id,
        status=call_status.value if call_status else None,
        direction=direction.value if direction else None,
        limit=limit,
        offset=offset,
    )

    # Build a cache of agent names for the response
    agent_names: dict[str, str] = {}
    for call in calls:
        if call.agent_id not in agent_names:
            agent = get_agent(call.agent_id, customer.id)
            agent_names[call.agent_id] = agent.name if agent else "Unknown"

    return {
        "calls": [
            _call_to_response(c, agent_names.get(c.agent_id, "Unknown"))
            for c in calls
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ──────────────────────────────────────────────────────────────────
# Detail
# ──────────────────────────────────────────────────────────────────

@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call_detail(
    call_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get full call detail including transcript and tool calls."""
    call = get_call(call_id, customer.id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )

    # Get agent name
    agent = get_agent(call.agent_id, customer.id)
    agent_name = agent.name if agent else "Unknown"

    # Get tool calls for this call
    tool_calls = get_tool_calls_for_call(call_id)
    tool_call_dicts = [
        {
            "id": tc.id,
            "function_name": tc.function_name,
            "arguments": tc.arguments,
            "result": tc.result,
            "duration_ms": tc.duration_ms,
            "created_at": tc.created_at.isoformat(),
        }
        for tc in tool_calls
    ]

    return CallDetailResponse(
        id=call.id,
        agent_id=call.agent_id,
        agent_name=agent_name,
        direction=call.direction,
        from_number=call.from_number,
        to_number=call.to_number,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        status=call.status,
        end_reason=call.end_reason,
        escalated_to_human=call.escalated_to_human,
        sentiment_score=call.sentiment_score,
        resolution=call.resolution,
        cost_cents=call.cost_cents,
        created_at=call.created_at,
        transcript=call.transcript,
        recording_url=call.recording_url,
        metadata=call.metadata,
        tool_calls=tool_call_dicts,
    )


# ──────────────────────────────────────────────────────────────────
# Summary (dashboard overview)
# ──────────────────────────────────────────────────────────────────

@router.get("/summary/overview")
async def get_calls_overview(
    customer: Customer = Depends(get_current_customer),
):
    """Get a high-level calls overview for the dashboard.

    Returns total calls, AI containment rate, avg duration,
    and total cost for the current billing period.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get all calls this period (up to 10K for stats)
    calls, total = list_calls(customer.id, limit=10000, offset=0)

    # Filter to current period
    period_calls = [
        c for c in calls
        if c.created_at >= period_start
    ]

    total_calls = len(period_calls)
    if total_calls == 0:
        return {
            "total_calls": 0,
            "ai_handled": 0,
            "escalated": 0,
            "containment_rate": 0.0,
            "avg_duration_seconds": 0.0,
            "total_cost_cents": 0,
            "total_cost_dollars": 0.0,
        }

    ai_handled = sum(1 for c in period_calls if not c.escalated_to_human)
    escalated = sum(1 for c in period_calls if c.escalated_to_human)
    avg_dur = sum(c.duration_seconds for c in period_calls) / total_calls
    total_cost = sum(c.cost_cents for c in period_calls)

    return {
        "total_calls": total_calls,
        "ai_handled": ai_handled,
        "escalated": escalated,
        "containment_rate": round(ai_handled / total_calls * 100, 1),
        "avg_duration_seconds": round(avg_dur, 1),
        "total_cost_cents": total_cost,
        "total_cost_dollars": round(total_cost / 100, 2),
    }
