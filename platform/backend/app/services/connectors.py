"""Contact Center Connector service — integrate with existing platforms.

Manages connections to enterprise contact center platforms (Genesys, Amazon
Connect, Avaya, Cisco, etc.) so VoxBridge can gradually take over call
handling without rip-and-replace migration.

The connector framework provides:
1. Configuration management (credentials, endpoints)
2. Connection health monitoring
3. Call routing integration (map external queues to VoxBridge departments)
4. Event logging for audit trail

Each connector type maps to an existing VoxBridge serializer:
- Genesys → GenesysSerializer
- Amazon Connect → AmazonConnectSerializer
- Avaya → AvayaSerializer
- Cisco → CiscoSerializer
- Twilio → TwilioSerializer
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.models.database import (
    Connector,
    ConnectorEvent,
    ConnectorStatus,
    ConnectorType,
)


# ──────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────

_connectors: dict[str, Connector] = {}
_events: dict[str, list[ConnectorEvent]] = {}  # connector_id → events

MAX_EVENTS_PER_CONNECTOR = 100


# ──────────────────────────────────────────────────────────────────
# Connector CRUD
# ──────────────────────────────────────────────────────────────────

def create_connector(connector: Connector) -> Connector:
    _connectors[connector.id] = connector
    _events[connector.id] = []
    log_event(connector.id, "created", f"Connector '{connector.name}' created")
    return connector


def get_connector(connector_id: str) -> Connector | None:
    return _connectors.get(connector_id)


def list_connectors(customer_id: str) -> list[Connector]:
    return [c for c in _connectors.values() if c.customer_id == customer_id]


def update_connector(connector_id: str, updates: dict[str, Any]) -> Connector | None:
    conn = _connectors.get(connector_id)
    if not conn:
        return None
    for key, value in updates.items():
        if hasattr(conn, key):
            setattr(conn, key, value)
    conn.updated_at = datetime.now(timezone.utc)
    return conn


def delete_connector(connector_id: str) -> bool:
    removed = _connectors.pop(connector_id, None)
    _events.pop(connector_id, None)
    return removed is not None


# ──────────────────────────────────────────────────────────────────
# Connection management
# ──────────────────────────────────────────────────────────────────

def activate_connector(connector_id: str) -> Connector | None:
    """Activate a connector (validate config and connect)."""
    conn = _connectors.get(connector_id)
    if not conn:
        return None

    # Validate required config fields per type
    errors = validate_config(conn)
    if errors:
        conn.status = ConnectorStatus.ERROR
        conn.error_message = "; ".join(errors)
        log_event(connector_id, "error", f"Validation failed: {conn.error_message}")
        return conn

    conn.status = ConnectorStatus.ACTIVE
    conn.error_message = ""
    conn.last_active_at = datetime.now(timezone.utc)
    log_event(connector_id, "connected", f"Connector '{conn.name}' activated")
    logger.info(f"Connector {conn.name} ({conn.connector_type}) activated")
    return conn


def deactivate_connector(connector_id: str) -> Connector | None:
    """Deactivate a connector."""
    conn = _connectors.get(connector_id)
    if not conn:
        return None
    conn.status = ConnectorStatus.INACTIVE
    log_event(connector_id, "disconnected", f"Connector '{conn.name}' deactivated")
    return conn


def validate_config(connector: Connector) -> list[str]:
    """Validate connector configuration. Returns list of error messages."""
    errors: list[str] = []
    config = connector.config

    required_fields: dict[ConnectorType, list[str]] = {
        ConnectorType.GENESYS: ["org_id", "client_id", "client_secret", "region"],
        ConnectorType.AMAZON_CONNECT: ["instance_id", "region"],
        ConnectorType.AVAYA: ["host", "port"],
        ConnectorType.CISCO: ["finesse_url"],
        ConnectorType.TWILIO: ["account_sid", "auth_token"],
        ConnectorType.FIVE9: ["domain", "username"],
        ConnectorType.GENERIC_SIP: ["sip_server"],
    }

    fields = required_fields.get(connector.connector_type, [])
    for field in fields:
        if not config.get(field):
            errors.append(f"Missing required field: {field}")

    return errors


# ──────────────────────────────────────────────────────────────────
# Queue/Department mapping
# ──────────────────────────────────────────────────────────────────

def map_queue_to_department(
    connector_id: str,
    external_queue_id: str,
    department_id: str,
) -> Connector | None:
    """Map an external queue/skill to a VoxBridge department."""
    conn = _connectors.get(connector_id)
    if not conn:
        return None
    conn.department_mappings[external_queue_id] = department_id
    log_event(connector_id, "mapping_updated", f"Queue {external_queue_id} → Dept {department_id}")
    return conn


def resolve_department(connector_id: str, external_queue_id: str) -> str | None:
    """Look up which VoxBridge department handles calls from an external queue."""
    conn = _connectors.get(connector_id)
    if not conn:
        return None
    return conn.department_mappings.get(external_queue_id)


# ──────────────────────────────────────────────────────────────────
# Event logging
# ──────────────────────────────────────────────────────────────────

def log_event(connector_id: str, event_type: str, message: str, metadata: dict | None = None) -> ConnectorEvent:
    """Log a connector event."""
    event = ConnectorEvent(
        connector_id=connector_id,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )
    if connector_id not in _events:
        _events[connector_id] = []
    events = _events[connector_id]
    events.append(event)
    # Trim to max
    if len(events) > MAX_EVENTS_PER_CONNECTOR:
        _events[connector_id] = events[-MAX_EVENTS_PER_CONNECTOR:]
    return event


def get_events(connector_id: str, limit: int = 50) -> list[ConnectorEvent]:
    events = _events.get(connector_id, [])
    return list(reversed(events[-limit:]))


# ──────────────────────────────────────────────────────────────────
# Call routing through connector
# ──────────────────────────────────────────────────────────────────

def route_incoming_call(
    connector_id: str,
    external_queue_id: str,
    caller_number: str,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Handle an incoming call from an external contact center.

    Maps the external queue to a VoxBridge department and returns
    the routing information needed to connect the call.
    """
    conn = _connectors.get(connector_id)
    if not conn or conn.status != ConnectorStatus.ACTIVE:
        return {"error": "Connector not active", "routed": False}

    dept_id = resolve_department(connector_id, external_queue_id)
    if not dept_id:
        log_event(connector_id, "routing_failed", f"No mapping for queue {external_queue_id}")
        return {"error": f"No department mapping for queue {external_queue_id}", "routed": False}

    conn.total_calls_routed += 1
    conn.last_active_at = datetime.now(timezone.utc)

    log_event(connector_id, "call_routed", f"Call from {caller_number} → Dept {dept_id}", {
        "caller": caller_number,
        "queue": external_queue_id,
        "department_id": dept_id,
    })

    return {
        "routed": True,
        "department_id": dept_id,
        "connector_id": connector_id,
        "connector_type": conn.connector_type,
        "caller_number": caller_number,
    }


# ──────────────────────────────────────────────────────────────────
# Connector health check
# ──────────────────────────────────────────────────────────────────

def get_health(connector_id: str) -> dict[str, Any]:
    """Get connector health status."""
    conn = _connectors.get(connector_id)
    if not conn:
        return {"healthy": False, "error": "Connector not found"}

    return {
        "healthy": conn.status == ConnectorStatus.ACTIVE,
        "status": conn.status,
        "name": conn.name,
        "type": conn.connector_type,
        "total_calls_routed": conn.total_calls_routed,
        "last_active_at": conn.last_active_at.isoformat() if conn.last_active_at else None,
        "error": conn.error_message,
    }
