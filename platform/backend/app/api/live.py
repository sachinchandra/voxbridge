"""Live monitoring REST endpoints — initial load + polling fallback.

These endpoints provide the same data that the WebSocket streams,
but as traditional GET requests for initial page load and for
clients that cannot use WebSocket.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.middleware.auth import get_current_customer
from app.models.database import Customer
from app.services import live_metrics, event_bus

router = APIRouter(prefix="/live", tags=["Live Monitoring"])


@router.get("/dashboard")
def live_dashboard(customer: Customer = Depends(get_current_customer)) -> dict[str, Any]:
    """Real-time dashboard snapshot.

    Returns aggregated live metrics: active calls, queue depth,
    agent presence, containment rate, recent events, etc.
    """
    return live_metrics.get_live_snapshot(customer.id)


@router.get("/events")
def live_events(
    since: str | None = Query(None, description="ISO 8601 timestamp — return events after this time"),
    limit: int = Query(20, ge=1, le=100),
    customer: Customer = Depends(get_current_customer),
) -> list[dict[str, Any]]:
    """Recent events for polling fallback.

    If *since* is provided, returns only events newer than that timestamp.
    Otherwise returns the last *limit* events.
    """
    if since:
        return event_bus.get_events_since(customer.id, since, limit=limit)
    return event_bus.get_recent_events(customer.id, limit=limit)


@router.get("/active-calls")
def live_active_calls(customer: Customer = Depends(get_current_customer)) -> list[dict[str, Any]]:
    """List of currently in-progress calls with live duration."""
    return live_metrics.get_active_calls(customer.id)


@router.get("/agent-presence")
def live_agent_presence(customer: Customer = Depends(get_current_customer)) -> list[dict[str, Any]]:
    """All human agents with their live status."""
    return live_metrics.get_agent_presence(customer.id)
