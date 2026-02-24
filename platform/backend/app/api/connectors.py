"""Connectors API -- manage contact center platform integrations.

Endpoints:
    POST   /connectors                       Create connector
    GET    /connectors                       List connectors
    GET    /connectors/{id}                  Get connector
    PATCH  /connectors/{id}                  Update connector
    DELETE /connectors/{id}                  Delete connector
    POST   /connectors/{id}/activate         Activate connector
    POST   /connectors/{id}/deactivate       Deactivate connector
    GET    /connectors/{id}/health           Health check
    GET    /connectors/{id}/events           List events
    POST   /connectors/{id}/map-queue        Map external queue to department
    POST   /connectors/{id}/route-call       Route incoming call
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import Connector, ConnectorType, ConnectorStatus
from app.services import connectors as conn_svc
from app.middleware.auth import get_current_customer_id

router = APIRouter(prefix="/connectors", tags=["connectors"])


# -- Request schemas ----------------------------------------------------------

class CreateConnectorRequest(BaseModel):
    name: str
    connector_type: str = "twilio"
    config: dict = {}


class UpdateConnectorRequest(BaseModel):
    name: str | None = None
    config: dict | None = None


class MapQueueRequest(BaseModel):
    external_queue_id: str
    department_id: str


class RouteCallRequest(BaseModel):
    external_queue_id: str
    caller_number: str
    metadata: dict = {}


# -- Connector CRUD ----------------------------------------------------------

@router.post("")
async def create_connector(
    req: CreateConnectorRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Create a new contact center connector."""
    conn = Connector(
        customer_id=customer_id,
        name=req.name,
        connector_type=ConnectorType(req.connector_type),
        status=ConnectorStatus.CONFIGURING,
        config=req.config,
    )
    conn_svc.create_connector(conn)
    return conn.model_dump()


@router.get("")
async def list_connectors(customer_id: str = Depends(get_current_customer_id)):
    """List all connectors for the current customer."""
    connectors = conn_svc.list_connectors(customer_id)
    return [c.model_dump() for c in connectors]


@router.get("/{connector_id}")
async def get_connector(
    connector_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Get a single connector."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")
    return conn.model_dump()


@router.patch("/{connector_id}")
async def update_connector(
    connector_id: str,
    req: UpdateConnectorRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Update connector settings."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = conn_svc.update_connector(connector_id, updates)
    return updated.model_dump()


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Delete a connector."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")
    conn_svc.delete_connector(connector_id)
    return {"deleted": True}


# -- Connection management ----------------------------------------------------

@router.post("/{connector_id}/activate")
async def activate_connector(
    connector_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Activate a connector (validates config and connects)."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")

    result = conn_svc.activate_connector(connector_id)
    if result and result.status == ConnectorStatus.ERROR:
        raise HTTPException(400, detail=result.error_message)
    return result.model_dump() if result else {"error": "Activation failed"}


@router.post("/{connector_id}/deactivate")
async def deactivate_connector(
    connector_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Deactivate a connector."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")

    result = conn_svc.deactivate_connector(connector_id)
    return result.model_dump() if result else {"error": "Deactivation failed"}


# -- Health & events ----------------------------------------------------------

@router.get("/{connector_id}/health")
async def get_health(
    connector_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Get connector health status."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")
    return conn_svc.get_health(connector_id)


@router.get("/{connector_id}/events")
async def list_events(
    connector_id: str,
    limit: int = 50,
    customer_id: str = Depends(get_current_customer_id),
):
    """List connector events (audit trail)."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")
    events = conn_svc.get_events(connector_id, limit)
    return [e.model_dump() for e in events]


# -- Queue mapping & call routing ---------------------------------------------

@router.post("/{connector_id}/map-queue")
async def map_queue(
    connector_id: str,
    req: MapQueueRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Map an external queue/skill to a VoxBridge department."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")

    result = conn_svc.map_queue_to_department(connector_id, req.external_queue_id, req.department_id)
    if not result:
        raise HTTPException(400, "Failed to map queue")
    return {"mapped": True, "external_queue_id": req.external_queue_id, "department_id": req.department_id}


@router.post("/{connector_id}/route-call")
async def route_call(
    connector_id: str,
    req: RouteCallRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Route an incoming call from an external platform."""
    conn = conn_svc.get_connector(connector_id)
    if not conn or conn.customer_id != customer_id:
        raise HTTPException(404, "Connector not found")

    result = conn_svc.route_incoming_call(
        connector_id, req.external_queue_id, req.caller_number, req.metadata,
    )
    if not result.get("routed"):
        raise HTTPException(400, detail=result.get("error", "Routing failed"))
    return result
