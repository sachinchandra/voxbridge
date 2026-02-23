"""Conversation Flow API — visual call flow builder.

Endpoints:
    POST   /flows                   Create a new flow
    GET    /flows                   List flows for customer
    GET    /flows/{id}              Get flow details
    PATCH  /flows/{id}              Update flow (nodes, edges, name)
    DELETE /flows/{id}              Delete flow
    POST   /flows/{id}/activate     Set as active flow for its agent
    POST   /flows/{id}/test         Simulate flow with test inputs
    POST   /flows/{id}/version      Create a versioned snapshot for A/B testing
    GET    /flows/{id}/versions     List versions
    POST   /flows/default           Create a default starter flow
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import ConversationFlow, FlowNode, FlowEdge
from app.services import flow_engine as fe
from app.middleware.auth import get_current_customer

router = APIRouter(prefix="/flows", tags=["flows"])


# ── Request schemas ──────────────────────────────────────────────

class CreateFlowRequest(BaseModel):
    agent_id: str = ""
    name: str = "New Flow"
    description: str = ""
    nodes: list[dict] = []
    edges: list[dict] = []


class UpdateFlowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None


class TestFlowRequest(BaseModel):
    inputs: list[str] = []  # simulated user messages


class CreateVersionRequest(BaseModel):
    name: str = "Variant A"
    traffic_percent: int = 50


# ── Endpoints ────────────────────────────────────────────────────

@router.post("")
async def create_flow(
    req: CreateFlowRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Create a new conversation flow."""
    nodes = [FlowNode(**n) for n in req.nodes] if req.nodes else []
    edges = [FlowEdge(**e) for e in req.edges] if req.edges else []

    flow = ConversationFlow(
        customer_id=customer_id,
        agent_id=req.agent_id,
        name=req.name,
        description=req.description,
        nodes=nodes,
        edges=edges,
    )
    fe.save_flow(flow)
    return flow.model_dump()


@router.get("")
async def list_flows(customer_id: str = Depends(get_current_customer)):
    """List all conversation flows."""
    flows = fe.list_flows(customer_id)
    return [
        {
            "id": f.id,
            "agent_id": f.agent_id,
            "name": f.name,
            "description": f.description,
            "is_active": f.is_active,
            "version": f.version,
            "node_count": len(f.nodes),
            "edge_count": len(f.edges),
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
        }
        for f in flows
    ]


@router.get("/{flow_id}")
async def get_flow(flow_id: str, customer_id: str = Depends(get_current_customer)):
    """Get full flow details including nodes and edges."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")
    return flow.model_dump()


@router.patch("/{flow_id}")
async def update_flow(
    flow_id: str,
    req: UpdateFlowRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Update a flow's name, description, nodes, or edges."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")

    if req.name is not None:
        flow.name = req.name
    if req.description is not None:
        flow.description = req.description
    if req.nodes is not None:
        flow.nodes = [FlowNode(**n) for n in req.nodes]
    if req.edges is not None:
        flow.edges = [FlowEdge(**e) for e in req.edges]
    flow.version += 1

    fe.save_flow(flow)
    return flow.model_dump()


@router.delete("/{flow_id}")
async def delete_flow(flow_id: str, customer_id: str = Depends(get_current_customer)):
    """Delete a conversation flow."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")
    fe.delete_flow(flow_id)
    return {"deleted": True}


@router.post("/{flow_id}/activate")
async def activate_flow(flow_id: str, customer_id: str = Depends(get_current_customer)):
    """Set a flow as the active flow for its agent."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")

    # Validate before activating
    errors = fe.validate_flow(flow)
    if errors:
        raise HTTPException(400, {"errors": errors})

    # Deactivate other flows for same agent
    for f in fe.list_flows(customer_id):
        if f.agent_id == flow.agent_id:
            f.is_active = False
    flow.is_active = True
    fe.save_flow(flow)
    return {"activated": True, "flow_id": flow_id}


@router.post("/{flow_id}/test")
async def test_flow(
    flow_id: str,
    req: TestFlowRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Simulate executing a flow with test inputs."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")

    result = fe.execute_flow(flow, req.inputs)
    return result.model_dump()


@router.post("/{flow_id}/version")
async def create_version(
    flow_id: str,
    req: CreateVersionRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Create a versioned snapshot of the current flow for A/B testing."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")

    from app.models.database import FlowVersion
    version = FlowVersion(
        flow_id=flow_id,
        version=flow.version,
        name=req.name,
        nodes=flow.nodes.copy(),
        edges=flow.edges.copy(),
        traffic_percent=req.traffic_percent,
    )
    fe.save_version(flow_id, version)
    return version.model_dump()


@router.get("/{flow_id}/versions")
async def list_versions(flow_id: str, customer_id: str = Depends(get_current_customer)):
    """List all versions of a flow."""
    flow = fe.get_flow(flow_id)
    if not flow or flow.customer_id != customer_id:
        raise HTTPException(404, "Flow not found")

    versions = fe.get_versions(flow_id)
    return [v.model_dump() for v in versions]


@router.post("/default")
async def create_default(
    req: CreateFlowRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Create a default starter flow for quick setup."""
    flow = fe.create_default_flow(customer_id, req.agent_id, req.name)
    fe.save_flow(flow)
    return flow.model_dump()
