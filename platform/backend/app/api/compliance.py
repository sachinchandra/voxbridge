"""Compliance & Audit Log API.

Endpoints:
    POST   /compliance/rules                   Create compliance rule
    GET    /compliance/rules                   List rules
    PATCH  /compliance/rules/{id}              Update rule
    DELETE /compliance/rules/{id}              Delete rule
    POST   /compliance/rules/defaults          Create default rule set

    POST   /compliance/scan                    Scan a transcript for violations
    GET    /compliance/violations              List violations
    POST   /compliance/violations/{id}/resolve Resolve a violation
    GET    /compliance/summary                 Compliance overview

    POST   /compliance/redact                  Redact PII from text

    GET    /compliance/audit-log               Get audit log
    POST   /compliance/audit-log               Log an action
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import AuditAction, ComplianceRule, ComplianceRuleType
from app.services import compliance as comp_svc
from app.middleware.auth import get_current_customer_id

router = APIRouter(prefix="/compliance", tags=["compliance"])


# -- Request schemas ----------------------------------------------------------

class CreateRuleRequest(BaseModel):
    name: str
    rule_type: str = "pii_redaction"
    severity: str = "warning"
    config: dict = {}
    enabled: bool = True


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    severity: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class ScanRequest(BaseModel):
    call_id: str = ""
    transcript: list[dict] = []     # [{role: "agent"|"caller", content: "..."}]


class RedactRequest(BaseModel):
    text: str = ""


class LogActionRequest(BaseModel):
    action: str = "login"
    resource_type: str = ""
    resource_id: str = ""
    description: str = ""
    metadata: dict = {}


# -- Compliance Rules ---------------------------------------------------------

@router.post("/rules")
async def create_rule(
    req: CreateRuleRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Create a compliance rule."""
    rule = ComplianceRule(
        customer_id=customer_id,
        name=req.name,
        rule_type=ComplianceRuleType(req.rule_type),
        severity=req.severity,
        config=req.config,
        enabled=req.enabled,
    )
    comp_svc.create_rule(rule)
    return rule.model_dump()


@router.get("/rules")
async def list_rules(customer_id: str = Depends(get_current_customer_id)):
    """List all compliance rules."""
    rules = comp_svc.list_rules(customer_id)
    return [r.model_dump() for r in rules]


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    req: UpdateRuleRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Update a compliance rule."""
    rule = comp_svc.get_rule(rule_id)
    if not rule or rule.customer_id != customer_id:
        raise HTTPException(404, "Rule not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = comp_svc.update_rule(rule_id, updates)
    return updated.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Delete a compliance rule."""
    rule = comp_svc.get_rule(rule_id)
    if not rule or rule.customer_id != customer_id:
        raise HTTPException(404, "Rule not found")
    comp_svc.delete_rule(rule_id)
    return {"deleted": True}


@router.post("/rules/defaults")
async def create_default_rules(customer_id: str = Depends(get_current_customer_id)):
    """Create a standard compliance rule set."""
    rules = comp_svc.create_default_rules(customer_id)
    return {"created": len(rules), "rules": [r.model_dump() for r in rules]}


# -- Transcript Scanning ------------------------------------------------------

@router.post("/scan")
async def scan_transcript(
    req: ScanRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Scan a call transcript for compliance violations."""
    violations = comp_svc.scan_transcript(customer_id, req.call_id, req.transcript)
    return {
        "violations_found": len(violations),
        "violations": [v.model_dump() for v in violations],
    }


# -- Violations ---------------------------------------------------------------

@router.get("/violations")
async def list_violations(
    unresolved_only: bool = False,
    rule_type: str = "",
    limit: int = 50,
    customer_id: str = Depends(get_current_customer_id),
):
    """List compliance violations."""
    violations = comp_svc.list_violations(customer_id, unresolved_only, rule_type, limit)
    return [v.model_dump() for v in violations]


@router.post("/violations/{violation_id}/resolve")
async def resolve_violation(
    violation_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Mark a violation as resolved."""
    v = comp_svc.get_violation(violation_id)
    if not v or v.customer_id != customer_id:
        raise HTTPException(404, "Violation not found")
    resolved = comp_svc.resolve_violation(violation_id, "dashboard_user")
    return {"resolved": True, "violation_id": violation_id}


# -- PII Redaction ------------------------------------------------------------

@router.post("/redact")
async def redact_text(
    req: RedactRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Redact PII from text."""
    redacted = comp_svc.redact_text(req.text)
    return {"original_length": len(req.text), "redacted": redacted}


# -- Summary ------------------------------------------------------------------

@router.get("/summary")
async def get_summary(customer_id: str = Depends(get_current_customer_id)):
    """Get compliance overview."""
    summary = comp_svc.get_compliance_summary(customer_id)
    return summary.model_dump()


# -- Audit Log ----------------------------------------------------------------

@router.get("/audit-log")
async def get_audit_log(
    action: str = "",
    limit: int = 50,
    customer_id: str = Depends(get_current_customer_id),
):
    """Get audit log entries."""
    entries = comp_svc.get_audit_log(customer_id, action, limit)
    return [e.model_dump() for e in entries]


@router.post("/audit-log")
async def log_action(
    req: LogActionRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Manually log an audit action."""
    entry = comp_svc.log_action(
        customer_id=customer_id,
        user_email="dashboard_user",
        action=AuditAction(req.action),
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        description=req.description,
        metadata=req.metadata,
    )
    return entry.model_dump()
