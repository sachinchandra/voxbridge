"""In-memory event bus for real-time event broadcasting.

Scoped per customer_id — events published to a customer only reach
subscribers for that same customer.  Keeps a rolling history buffer
of the last MAX_HISTORY events per customer for reconnection catch-up.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ── Event Types ──────────────────────────────────────────────────

class EventType(str, Enum):
    CALL_STARTED = "call.started"
    CALL_ENDED = "call.ended"
    CALL_STATUS_CHANGED = "call.status_changed"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    ESCALATION_CREATED = "escalation.created"
    ESCALATION_ASSIGNED = "escalation.assigned"
    ESCALATION_RESOLVED = "escalation.resolved"
    ALERT_FIRED = "alert.fired"
    VIOLATION_DETECTED = "violation.detected"
    METRIC_UPDATED = "metric.updated"


# ── Event Structure ──────────────────────────────────────────────

def _make_event(event_type: str, customer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": event_type,
        "customer_id": customer_id,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Stores ───────────────────────────────────────────────────────

MAX_HISTORY = 50

# customer_id → list[event]
_event_history: dict[str, list[dict[str, Any]]] = {}

# customer_id → set[asyncio.Queue]
_subscribers: dict[str, set[asyncio.Queue]] = {}


# ── Publish / Subscribe ─────────────────────────────────────────

def publish(customer_id: str, event_type: str | EventType, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish an event to all subscribers for a customer.

    Returns the constructed event dict.
    """
    evt_type = event_type.value if isinstance(event_type, EventType) else event_type
    event = _make_event(evt_type, customer_id, payload or {})

    # Append to history, trim to MAX_HISTORY
    history = _event_history.setdefault(customer_id, [])
    history.append(event)
    if len(history) > MAX_HISTORY:
        _event_history[customer_id] = history[-MAX_HISTORY:]

    # Broadcast to all async subscribers (non-blocking put_nowait)
    for queue in _subscribers.get(customer_id, set()).copy():
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # slow consumer — drop event rather than block

    return event


def subscribe(customer_id: str, maxsize: int = 256) -> asyncio.Queue:
    """Create an async queue that receives events for *customer_id*.

    The caller should eventually call unsubscribe() to clean up.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
    _subscribers.setdefault(customer_id, set()).add(queue)
    return queue


def unsubscribe(customer_id: str, queue: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    subs = _subscribers.get(customer_id)
    if subs:
        subs.discard(queue)
        if not subs:
            del _subscribers[customer_id]


# ── History ──────────────────────────────────────────────────────

def get_recent_events(customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the last *limit* events for a customer (newest first)."""
    history = _event_history.get(customer_id, [])
    return list(reversed(history[-limit:]))


def get_events_since(customer_id: str, since_iso: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return events newer than *since_iso* (ISO 8601 timestamp)."""
    history = _event_history.get(customer_id, [])
    result = [e for e in history if e["timestamp"] > since_iso]
    return result[-limit:]


# ── Introspection ────────────────────────────────────────────────

def subscriber_count(customer_id: str) -> int:
    """Number of active subscribers for a customer."""
    return len(_subscribers.get(customer_id, set()))


def total_subscribers() -> int:
    """Total subscribers across all customers."""
    return sum(len(s) for s in _subscribers.values())


# ── Cleanup ──────────────────────────────────────────────────────

def clear_customer(customer_id: str) -> None:
    """Remove all history and subscribers for a customer."""
    _event_history.pop(customer_id, None)
    _subscribers.pop(customer_id, None)


def clear_all() -> None:
    """Clear everything (for tests)."""
    _event_history.clear()
    _subscribers.clear()
