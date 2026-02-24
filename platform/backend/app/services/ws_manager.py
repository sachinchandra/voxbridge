"""WebSocket connection manager.

Tracks active WebSocket connections per customer_id, provides
broadcast helpers, and handles graceful cleanup on disconnect.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket

# ── Connection Registry ──────────────────────────────────────────

# customer_id → set[WebSocket]
_connections: dict[str, set[WebSocket]] = {}


async def connect(ws: WebSocket, customer_id: str) -> None:
    """Accept a WebSocket and register it for *customer_id*."""
    await ws.accept()
    _connections.setdefault(customer_id, set()).add(ws)


def disconnect(ws: WebSocket, customer_id: str) -> None:
    """Remove a WebSocket from the registry."""
    conns = _connections.get(customer_id)
    if conns:
        conns.discard(ws)
        if not conns:
            del _connections[customer_id]


async def broadcast(customer_id: str, message: dict[str, Any]) -> int:
    """Send a JSON message to all connections for *customer_id*.

    Returns the number of connections that were successfully sent to.
    Dead connections are automatically cleaned up.
    """
    conns = _connections.get(customer_id, set()).copy()
    sent = 0
    dead: list[WebSocket] = []

    payload = json.dumps(message)
    for ws in conns:
        try:
            await ws.send_text(payload)
            sent += 1
        except Exception:
            dead.append(ws)

    # Clean up dead connections
    for ws in dead:
        disconnect(ws, customer_id)

    return sent


async def send_personal(ws: WebSocket, message: dict[str, Any]) -> bool:
    """Send a JSON message to a single WebSocket.

    Returns True if successful, False if the connection is dead.
    """
    try:
        await ws.send_text(json.dumps(message))
        return True
    except Exception:
        return False


# ── Introspection ────────────────────────────────────────────────

def connection_count(customer_id: str) -> int:
    """Number of active connections for a customer."""
    return len(_connections.get(customer_id, set()))


def total_connections() -> int:
    """Total active WebSocket connections across all customers."""
    return sum(len(c) for c in _connections.values())


def active_customers() -> list[str]:
    """List of customer_ids with active connections."""
    return [cid for cid, conns in _connections.items() if conns]


# ── Cleanup ──────────────────────────────────────────────────────

async def disconnect_all(customer_id: str) -> int:
    """Close and remove all connections for a customer."""
    conns = _connections.pop(customer_id, set())
    count = 0
    for ws in conns:
        try:
            await ws.close()
            count += 1
        except Exception:
            pass
    return count


def clear_all() -> None:
    """Clear registry (for tests — does NOT close connections)."""
    _connections.clear()
