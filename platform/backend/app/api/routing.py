"""Routing API -- manage departments, routing rules, and classify calls.

Endpoints:
    POST   /routing/departments              Create department
    GET    /routing/departments              List departments
    GET    /routing/departments/{id}         Get department
    PATCH  /routing/departments/{id}         Update department
    DELETE /routing/departments/{id}         Delete department
    POST   /routing/departments/defaults     Create default departments

    POST   /routing/rules                    Create routing rule
    GET    /routing/rules                    List routing rules
    DELETE /routing/rules/{id}               Delete rule

    POST   /routing/classify                 Classify caller intent
    GET    /routing/config                   Get routing config summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import Department, RoutingRule
from app.services import intent_router as router_svc
from app.middleware.auth import get_current_customer

router = APIRouter(prefix="/routing", tags=["routing"])


# -- Request schemas ----------------------------------------------------------

class CreateDepartmentRequest(BaseModel):
    name: str
    description: str = ""
    agent_id: str = ""
    transfer_number: str = ""
    priority: int = 10
    is_default: bool = False
    enabled: bool = True
    intent_keywords: list[str] = []


class UpdateDepartmentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_id: str | None = None
    transfer_number: str | None = None
    priority: int | None = None
    is_default: bool | None = None
    enabled: bool | None = None
    intent_keywords: list[str] | None = None


class CreateRuleRequest(BaseModel):
    name: str
    department_id: str
    match_type: str = "keyword"       # keyword | regex | dtmf | intent_model
    match_value: str = ""
    priority: int = 10
    enabled: bool = True


class ClassifyRequest(BaseModel):
    text: str = ""
    dtmf_input: str = ""


# -- Department endpoints -----------------------------------------------------

@router.post("/departments")
async def create_department(
    req: CreateDepartmentRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Create a new department."""
    dept = Department(
        customer_id=customer_id,
        name=req.name,
        description=req.description,
        agent_id=req.agent_id,
        transfer_number=req.transfer_number,
        priority=req.priority,
        is_default=req.is_default,
        enabled=req.enabled,
        intent_keywords=req.intent_keywords,
    )
    router_svc.create_department(dept)
    return dept.model_dump()


@router.get("/departments")
async def list_departments(customer_id: str = Depends(get_current_customer)):
    """List all departments sorted by priority."""
    depts = router_svc.list_departments(customer_id)
    return [d.model_dump() for d in depts]


@router.get("/departments/{dept_id}")
async def get_department(
    dept_id: str,
    customer_id: str = Depends(get_current_customer),
):
    """Get a single department."""
    dept = router_svc.get_department(dept_id)
    if not dept or dept.customer_id != customer_id:
        raise HTTPException(404, "Department not found")
    return dept.model_dump()


@router.patch("/departments/{dept_id}")
async def update_department(
    dept_id: str,
    req: UpdateDepartmentRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Update a department."""
    dept = router_svc.get_department(dept_id)
    if not dept or dept.customer_id != customer_id:
        raise HTTPException(404, "Department not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = router_svc.update_department(dept_id, updates)
    return updated.model_dump()


@router.delete("/departments/{dept_id}")
async def delete_department(
    dept_id: str,
    customer_id: str = Depends(get_current_customer),
):
    """Delete a department."""
    dept = router_svc.get_department(dept_id)
    if not dept or dept.customer_id != customer_id:
        raise HTTPException(404, "Department not found")
    router_svc.delete_department(dept_id)
    return {"deleted": True}


@router.post("/departments/defaults")
async def create_default_departments(customer_id: str = Depends(get_current_customer)):
    """Create default departments (Sales, Support, Billing)."""
    depts = router_svc.create_default_departments(customer_id)
    return {"created": len(depts), "departments": [d.model_dump() for d in depts]}


# -- Routing Rule endpoints ---------------------------------------------------

@router.post("/rules")
async def create_rule(
    req: CreateRuleRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Create a routing rule."""
    rule = RoutingRule(
        customer_id=customer_id,
        name=req.name,
        department_id=req.department_id,
        match_type=req.match_type,
        match_value=req.match_value,
        priority=req.priority,
        enabled=req.enabled,
    )
    router_svc.create_rule(rule)
    return rule.model_dump()


@router.get("/rules")
async def list_rules(customer_id: str = Depends(get_current_customer)):
    """List all routing rules sorted by priority."""
    rules = router_svc.list_rules(customer_id)
    return [r.model_dump() for r in rules]


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    customer_id: str = Depends(get_current_customer),
):
    """Delete a routing rule."""
    rule = router_svc.get_rule(rule_id)
    if not rule or rule.customer_id != customer_id:
        raise HTTPException(404, "Rule not found")
    router_svc.delete_rule(rule_id)
    return {"deleted": True}


# -- Classification -----------------------------------------------------------

@router.post("/classify")
async def classify_call(
    req: ClassifyRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Classify caller intent and return routing result."""
    result = router_svc.route_call(req.text, customer_id, req.dtmf_input)
    return result.model_dump()


@router.get("/config")
async def get_routing_config(customer_id: str = Depends(get_current_customer)):
    """Get a summary of the routing configuration."""
    depts = router_svc.list_departments(customer_id)
    rules = router_svc.list_rules(customer_id)
    return {
        "departments": len(depts),
        "rules": len(rules),
        "default_department": next(
            (d.name for d in depts if d.is_default), depts[0].name if depts else None
        ),
        "department_list": [
            {"id": d.id, "name": d.name, "priority": d.priority, "enabled": d.enabled, "is_default": d.is_default}
            for d in depts
        ],
    }
