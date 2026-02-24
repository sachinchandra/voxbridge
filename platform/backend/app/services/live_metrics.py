"""Live metrics aggregation service.

Provides real-time snapshots by combining data from:
  - Active calls tracker (updated by event hooks)
  - Workforce in-memory stores (agents, escalations)
  - Event bus history
  - WebSocket manager connection counts
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from app.services import event_bus, ws_manager, workforce as wf_svc


# ── Active Calls Tracker ─────────────────────────────────────────
# Maintained by event hooks in existing services.

# call_id → {customer_id, agent_id, agent_name, direction, from_number,
#             to_number, started_at, status}
_active_calls: dict[str, dict[str, Any]] = {}

# customer_id → {total_today, ai_handled_today, escalated_today}
_daily_counters: dict[str, dict[str, int]] = {}

# customer_id → list[timestamp] for calls-per-minute calculation
_call_timestamps: dict[str, list[str]] = {}


def track_call_started(
    call_id: str,
    customer_id: str,
    agent_id: str = "",
    agent_name: str = "",
    direction: str = "inbound",
    from_number: str = "",
    to_number: str = "",
) -> None:
    """Record a call as active."""
    _active_calls[call_id] = {
        "call_id": call_id,
        "customer_id": customer_id,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "direction": direction,
        "from_number": from_number,
        "to_number": to_number,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
    }

    counters = _daily_counters.setdefault(customer_id, {"total_today": 0, "ai_handled_today": 0, "escalated_today": 0})
    counters["total_today"] += 1

    ts_list = _call_timestamps.setdefault(customer_id, [])
    ts_list.append(datetime.now(timezone.utc).isoformat())
    # Trim to last hour
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _call_timestamps[customer_id] = [t for t in ts_list if t > cutoff]


def track_call_ended(call_id: str, escalated: bool = False) -> None:
    """Remove a call from active tracking."""
    info = _active_calls.pop(call_id, None)
    if info:
        customer_id = info["customer_id"]
        counters = _daily_counters.setdefault(customer_id, {"total_today": 0, "ai_handled_today": 0, "escalated_today": 0})
        if escalated:
            counters["escalated_today"] += 1
        else:
            counters["ai_handled_today"] += 1


def track_call_status(call_id: str, status: str) -> None:
    """Update the status of an active call."""
    if call_id in _active_calls:
        _active_calls[call_id]["status"] = status


# ── Snapshot ─────────────────────────────────────────────────────

def get_live_snapshot(customer_id: str) -> dict[str, Any]:
    """Aggregate real-time metrics from all sources."""

    # Active calls for this customer
    customer_calls = [c for c in _active_calls.values() if c["customer_id"] == customer_id]

    # Daily counters
    counters = _daily_counters.get(customer_id, {"total_today": 0, "ai_handled_today": 0, "escalated_today": 0})

    # Containment rate
    total_today = counters["total_today"]
    ai_handled = counters["ai_handled_today"]
    containment_rate = ai_handled / total_today if total_today > 0 else 0.0

    # Workforce data
    all_agents = wf_svc.list_human_agents(customer_id)
    active_agents = len([a for a in all_agents if a.status in ("available", "busy")])

    # Queue
    queue_status = wf_svc.get_queue_status(customer_id)

    # Calls per minute (rolling 5-min window)
    now = datetime.now(timezone.utc)
    five_min_ago = (now - timedelta(minutes=5)).isoformat()
    recent_ts = [t for t in _call_timestamps.get(customer_id, []) if t > five_min_ago]
    calls_per_minute = round(len(recent_ts) / 5.0, 2) if recent_ts else 0.0

    # WebSocket connections
    ws_count = ws_manager.connection_count(customer_id)

    # Recent events
    recent_events = event_bus.get_recent_events(customer_id, limit=15)

    return {
        "active_calls": len(customer_calls),
        "calls_today": total_today,
        "ai_contained_today": ai_handled,
        "escalated_today": counters["escalated_today"],
        "containment_rate": round(containment_rate, 4),
        "active_agents": active_agents,
        "total_agents": len(all_agents),
        "queue_depth": queue_status.get("waiting", 0),
        "avg_wait_seconds": round(queue_status.get("avg_wait_time_seconds", 0.0), 1),
        "calls_per_minute": calls_per_minute,
        "ws_connections": ws_count,
        "recent_events": recent_events,
        "timestamp": now.isoformat(),
    }


def get_active_calls(customer_id: str) -> list[dict[str, Any]]:
    """Return list of currently active calls for a customer."""
    return [
        {**c, "duration_seconds": _elapsed_seconds(c["started_at"])}
        for c in _active_calls.values()
        if c["customer_id"] == customer_id
    ]


def get_agent_presence(customer_id: str) -> list[dict[str, Any]]:
    """Return all human agents with their live status."""
    agents = wf_svc.list_human_agents(customer_id)
    return [
        {
            "id": a.id,
            "name": a.name,
            "status": a.status,
            "department_id": a.department_id,
            "current_call_id": a.current_call_id,
            "calls_handled_today": a.calls_handled_today,
            "busy_minutes_today": a.busy_minutes_today,
        }
        for a in agents
    ]


def _elapsed_seconds(started_iso: str) -> float:
    """Seconds elapsed since an ISO timestamp."""
    try:
        started = datetime.fromisoformat(started_iso)
        delta = datetime.now(timezone.utc) - started
        return round(delta.total_seconds(), 1)
    except Exception:
        return 0.0


# ── Cleanup ──────────────────────────────────────────────────────

def reset_daily_counters(customer_id: str | None = None) -> None:
    """Reset daily counters (called at midnight or for tests)."""
    if customer_id:
        _daily_counters.pop(customer_id, None)
    else:
        _daily_counters.clear()


def clear_all() -> None:
    """Clear all tracking data (for tests)."""
    _active_calls.clear()
    _daily_counters.clear()
    _call_timestamps.clear()
