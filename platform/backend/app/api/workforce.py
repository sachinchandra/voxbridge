"""Sprint 10 — Workforce Management API.

Human agent management, escalation queues, volume forecasting,
containment tracking, and ROI calculation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_customer
from app.models.database import (
    Customer,
    HumanAgent,
    HumanAgentStatus,
    EscalationQueue,
    EscalationPriority,
    EscalationStatus,
)
from app.services import workforce as wf_svc

router = APIRouter(prefix="/workforce", tags=["Workforce Management"])


# ── Request schemas ───────────────────────────────────────────────


class CreateHumanAgentRequest(BaseModel):
    name: str
    email: str = ""
    skills: list[str] = Field(default_factory=list)
    department_id: str = ""
    shift_start: str = ""
    shift_end: str = ""


class UpdateHumanAgentRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    skills: list[str] | None = None
    department_id: str | None = None
    shift_start: str | None = None
    shift_end: str | None = None


class SetAgentStatusRequest(BaseModel):
    status: HumanAgentStatus


class CreateEscalationRequest(BaseModel):
    call_id: str
    department_id: str = ""
    caller_number: str = ""
    caller_name: str = ""
    priority: EscalationPriority = EscalationPriority.NORMAL
    reason: str = ""
    ai_summary: str = ""


class AssignEscalationRequest(BaseModel):
    human_agent_id: str


class GenerateForecastRequest(BaseModel):
    date: str  # YYYY-MM-DD
    historical_calls: list[dict] | None = None
    containment_rate: float = 0.80
    calls_per_agent_per_hour: int = 4


class ROIRequest(BaseModel):
    human_agent_hourly_rate_cents: int = 2000
    calls_per_agent_per_hour: int = 4
    total_monthly_calls: int = 10000
    containment_rate: float = 0.80
    avg_call_duration_minutes: float = 5.0
    ai_cost_per_minute_cents: int = 6


class MetricsRequest(BaseModel):
    period_start: str
    period_end: str
    total_calls: int = 0
    ai_handled: int = 0
    human_handled: int = 0
    avg_wait_time_seconds: float = 0.0
    avg_handle_time_seconds: float = 0.0


# ── Human Agent endpoints ─────────────────────────────────────────


@router.post("/agents")
async def create_agent(
    body: CreateHumanAgentRequest,
    customer: Customer = Depends(get_current_customer),
):
    agent = wf_svc.create_human_agent(
        customer_id=customer.id,
        name=body.name,
        email=body.email,
        skills=body.skills,
        department_id=body.department_id,
        shift_start=body.shift_start,
        shift_end=body.shift_end,
    )
    return agent.model_dump()


@router.get("/agents")
async def list_agents(
    status: HumanAgentStatus | None = None,
    department_id: str | None = None,
    customer: Customer = Depends(get_current_customer),
):
    agents = wf_svc.list_human_agents(customer.id, status=status, department_id=department_id)
    return [a.model_dump() for a in agents]


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    body: UpdateHumanAgentRequest,
    customer: Customer = Depends(get_current_customer),
):
    agent = wf_svc.update_human_agent(agent_id, **body.model_dump(exclude_none=True))
    if not agent:
        raise HTTPException(404, "Human agent not found")
    return agent.model_dump()


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    customer: Customer = Depends(get_current_customer),
):
    if not wf_svc.delete_human_agent(agent_id):
        raise HTTPException(404, "Human agent not found")
    return {"deleted": True}


@router.patch("/agents/{agent_id}/status")
async def set_status(
    agent_id: str,
    body: SetAgentStatusRequest,
    customer: Customer = Depends(get_current_customer),
):
    agent = wf_svc.set_agent_status(agent_id, body.status)
    if not agent:
        raise HTTPException(404, "Human agent not found")
    return agent.model_dump()


# ── Escalation Queue endpoints ────────────────────────────────────


@router.post("/escalations")
async def create_escalation(
    body: CreateEscalationRequest,
    customer: Customer = Depends(get_current_customer),
):
    esc = wf_svc.enqueue_escalation(
        customer_id=customer.id,
        call_id=body.call_id,
        department_id=body.department_id,
        caller_number=body.caller_number,
        caller_name=body.caller_name,
        priority=body.priority,
        reason=body.reason,
        ai_summary=body.ai_summary,
    )
    return esc.model_dump()


@router.get("/escalations")
async def list_escalations(
    status: EscalationStatus | None = None,
    department_id: str | None = None,
    customer: Customer = Depends(get_current_customer),
):
    escs = wf_svc.list_escalations(customer.id, status=status, department_id=department_id)
    return [e.model_dump() for e in escs]


@router.post("/escalations/{esc_id}/assign")
async def assign_escalation(
    esc_id: str,
    body: AssignEscalationRequest,
    customer: Customer = Depends(get_current_customer),
):
    esc = wf_svc.assign_escalation(esc_id, body.human_agent_id)
    if not esc:
        raise HTTPException(400, "Cannot assign — escalation not waiting or agent not available")
    return esc.model_dump()


@router.post("/escalations/{esc_id}/auto-assign")
async def auto_assign(
    esc_id: str,
    customer: Customer = Depends(get_current_customer),
):
    esc = wf_svc.auto_assign_escalation(esc_id, customer.id)
    if not esc:
        raise HTTPException(400, "No available agents or escalation not in waiting state")
    return esc.model_dump()


@router.post("/escalations/{esc_id}/resolve")
async def resolve_escalation(
    esc_id: str,
    customer: Customer = Depends(get_current_customer),
):
    esc = wf_svc.resolve_escalation(esc_id)
    if not esc:
        raise HTTPException(400, "Cannot resolve this escalation")
    return esc.model_dump()


@router.get("/queue-status")
async def queue_status(customer: Customer = Depends(get_current_customer)):
    return wf_svc.get_queue_status(customer.id)


# ── Forecasting endpoints ─────────────────────────────────────────


@router.post("/forecast/generate")
async def generate_forecast(
    body: GenerateForecastRequest,
    customer: Customer = Depends(get_current_customer),
):
    forecasts = wf_svc.generate_forecast(
        customer_id=customer.id,
        date=body.date,
        historical_calls=body.historical_calls,
        containment_rate=body.containment_rate,
        calls_per_agent_per_hour=body.calls_per_agent_per_hour,
    )
    return [f.model_dump() for f in forecasts]


@router.get("/forecast")
async def get_forecast(
    date: str,
    customer: Customer = Depends(get_current_customer),
):
    forecasts = wf_svc.get_forecasts(customer.id, date)
    return [f.model_dump() for f in forecasts]


# ── Metrics & ROI endpoints ───────────────────────────────────────


@router.get("/metrics")
async def get_metrics(
    period_start: str,
    period_end: str,
    customer: Customer = Depends(get_current_customer),
):
    stored = [
        m for m in wf_svc._metrics.values()
        if m.customer_id == customer.id
        and m.period_start >= period_start
        and m.period_end <= period_end
    ]
    return [m.model_dump() for m in stored]


@router.post("/metrics")
async def create_metrics(
    body: MetricsRequest,
    customer: Customer = Depends(get_current_customer),
):
    metrics = wf_svc.calculate_metrics(
        customer_id=customer.id,
        period_start=body.period_start,
        period_end=body.period_end,
        total_calls=body.total_calls,
        ai_handled=body.ai_handled,
        human_handled=body.human_handled,
        avg_wait_time_seconds=body.avg_wait_time_seconds,
        avg_handle_time_seconds=body.avg_handle_time_seconds,
    )
    return metrics.model_dump()


@router.get("/containment-trend")
async def containment_trend(
    weeks: int = 8,
    customer: Customer = Depends(get_current_customer),
):
    return wf_svc.get_containment_trend(customer.id, weeks)


@router.post("/roi")
async def calculate_roi(
    body: ROIRequest,
    customer: Customer = Depends(get_current_customer),
):
    roi = wf_svc.calculate_roi(
        customer_id=customer.id,
        human_agent_hourly_rate_cents=body.human_agent_hourly_rate_cents,
        calls_per_agent_per_hour=body.calls_per_agent_per_hour,
        total_monthly_calls=body.total_monthly_calls,
        containment_rate=body.containment_rate,
        avg_call_duration_minutes=body.avg_call_duration_minutes,
        ai_cost_per_minute_cents=body.ai_cost_per_minute_cents,
    )
    return roi.model_dump()


@router.get("/dashboard")
async def dashboard(customer: Customer = Depends(get_current_customer)):
    return wf_svc.get_dashboard(customer.id).model_dump()
