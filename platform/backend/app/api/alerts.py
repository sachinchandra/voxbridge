"""Alerts API — manage alert rules and view triggered alerts.

Endpoints:
    POST   /alerts/rules                Create alert rule
    GET    /alerts/rules                List alert rules
    PATCH  /alerts/rules/{id}           Update rule
    DELETE /alerts/rules/{id}           Delete rule
    POST   /alerts/rules/defaults       Create default rule set
    GET    /alerts                      List alerts
    GET    /alerts/summary              Alert summary (counts by severity)
    POST   /alerts/{id}/acknowledge     Acknowledge an alert
    POST   /alerts/acknowledge-all      Acknowledge all alerts
    POST   /alerts/evaluate             Manually trigger rule evaluation
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import AlertRule, AlertType, AlertSeverity
from app.services import alerts as alert_svc
from app.middleware.auth import get_current_customer_id

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── Request schemas ──────────────────────────────────────────────

class CreateRuleRequest(BaseModel):
    name: str
    alert_type: str = "high_volume"
    severity: str = "warning"
    enabled: bool = True
    config: dict = {}
    notify_email: bool = True
    notify_webhook: str = ""


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    severity: str | None = None
    config: dict | None = None
    notify_email: bool | None = None
    notify_webhook: str | None = None


class EvaluateRequest(BaseModel):
    metrics: dict = {}


# ── Rule endpoints ───────────────────────────────────────────────

@router.post("/rules")
async def create_rule(
    req: CreateRuleRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Create a new alert rule."""
    rule = AlertRule(
        customer_id=customer_id,
        name=req.name,
        alert_type=AlertType(req.alert_type),
        severity=AlertSeverity(req.severity),
        enabled=req.enabled,
        config=req.config,
        notify_email=req.notify_email,
        notify_webhook=req.notify_webhook,
    )
    alert_svc.create_rule(rule)
    return rule.model_dump()


@router.get("/rules")
async def list_rules(customer_id: str = Depends(get_current_customer_id)):
    """List all alert rules."""
    rules = alert_svc.list_rules(customer_id)
    return [r.model_dump() for r in rules]


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    req: UpdateRuleRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Update an alert rule."""
    rule = alert_svc.get_rule(rule_id)
    if not rule or rule.customer_id != customer_id:
        raise HTTPException(404, "Rule not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "severity" in updates:
        updates["severity"] = AlertSeverity(updates["severity"])
    updated = alert_svc.update_rule(rule_id, updates)
    return updated.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Delete an alert rule."""
    rule = alert_svc.get_rule(rule_id)
    if not rule or rule.customer_id != customer_id:
        raise HTTPException(404, "Rule not found")
    alert_svc.delete_rule(rule_id)
    return {"deleted": True}


@router.post("/rules/defaults")
async def create_default_rules(customer_id: str = Depends(get_current_customer_id)):
    """Create a set of sensible default alert rules."""
    rules = alert_svc.create_default_rules(customer_id)
    return {"created": len(rules), "rules": [r.model_dump() for r in rules]}


# ── Alert endpoints ──────────────────────────────────────────────

@router.get("")
async def list_alerts(
    unacknowledged: bool = False,
    severity: str | None = None,
    limit: int = 50,
    customer_id: str = Depends(get_current_customer_id),
):
    """List triggered alerts."""
    alerts = alert_svc.list_alerts(customer_id, unacknowledged, severity, limit)
    return [a.model_dump() for a in alerts]


@router.get("/summary")
async def get_summary(customer_id: str = Depends(get_current_customer_id)):
    """Get alert summary with counts by severity."""
    summary = alert_svc.get_alert_summary(customer_id)
    return summary.model_dump()


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Acknowledge a single alert."""
    alert = alert_svc.get_alert(alert_id)
    if not alert or alert.customer_id != customer_id:
        raise HTTPException(404, "Alert not found")
    alert_svc.acknowledge_alert(alert_id)
    return {"acknowledged": True}


@router.post("/acknowledge-all")
async def acknowledge_all(customer_id: str = Depends(get_current_customer_id)):
    """Acknowledge all unacknowledged alerts."""
    count = alert_svc.acknowledge_all(customer_id)
    return {"acknowledged": count}


@router.post("/evaluate")
async def evaluate_rules(
    req: EvaluateRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Manually evaluate all rules against provided metrics."""
    triggered = alert_svc.evaluate_all_rules(customer_id, req.metrics)
    return {
        "evaluated": len(alert_svc.list_rules(customer_id)),
        "triggered": len(triggered),
        "alerts": [a.model_dump() for a in triggered],
    }
