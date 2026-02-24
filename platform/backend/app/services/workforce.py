"""Sprint 10 — Workforce Management service.

Hybrid AI + Human workforce: human agent management, escalation queues,
volume forecasting, containment tracking, and ROI calculation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from app.models.database import (
    HumanAgent,
    HumanAgentStatus,
    EscalationQueue,
    EscalationPriority,
    EscalationStatus,
    StaffingForecast,
    WorkforceMetrics,
    ROIEstimate,
    WorkforceDashboard,
)
from app.services import event_bus

# ── In-memory stores ──────────────────────────────────────────────

_human_agents: dict[str, HumanAgent] = {}
_escalations: dict[str, EscalationQueue] = {}
_forecasts: dict[str, StaffingForecast] = {}
_metrics: dict[str, WorkforceMetrics] = {}


# ── Human Agent Management ────────────────────────────────────────


def create_human_agent(customer_id: str, **kwargs) -> HumanAgent:
    agent = HumanAgent(customer_id=customer_id, **kwargs)
    _human_agents[agent.id] = agent
    return agent


def list_human_agents(
    customer_id: str,
    status: HumanAgentStatus | None = None,
    department_id: str | None = None,
) -> list[HumanAgent]:
    agents = [a for a in _human_agents.values() if a.customer_id == customer_id]
    if status:
        agents = [a for a in agents if a.status == status]
    if department_id:
        agents = [a for a in agents if a.department_id == department_id]
    return sorted(agents, key=lambda a: a.name)


def get_human_agent(agent_id: str) -> HumanAgent | None:
    return _human_agents.get(agent_id)


def update_human_agent(agent_id: str, **kwargs) -> HumanAgent | None:
    agent = _human_agents.get(agent_id)
    if not agent:
        return None
    for k, v in kwargs.items():
        if hasattr(agent, k) and v is not None:
            setattr(agent, k, v)
    return agent


def delete_human_agent(agent_id: str) -> bool:
    return _human_agents.pop(agent_id, None) is not None


def set_agent_status(agent_id: str, status: HumanAgentStatus) -> HumanAgent | None:
    agent = _human_agents.get(agent_id)
    if not agent:
        return None
    old_status = agent.status
    agent.status = status
    if status == HumanAgentStatus.OFFLINE:
        agent.current_call_id = None
    # Emit event
    event_bus.publish(agent.customer_id, event_bus.EventType.AGENT_STATUS_CHANGED, {
        "agent_id": agent.id, "agent_name": agent.name,
        "old_status": old_status, "new_status": status,
    })
    return agent


def get_agent_utilization(agent_id: str) -> float:
    """Return utilization as a percentage (0-100)."""
    agent = _human_agents.get(agent_id)
    if not agent or not agent.shift_start or not agent.shift_end:
        return 0.0
    try:
        sh, sm = map(int, agent.shift_start.split(":"))
        eh, em = map(int, agent.shift_end.split(":"))
        shift_minutes = (eh * 60 + em) - (sh * 60 + sm)
        if shift_minutes <= 0:
            return 0.0
        return min(100.0, round((agent.busy_minutes_today / shift_minutes) * 100, 1))
    except (ValueError, ZeroDivisionError):
        return 0.0


# ── Escalation Queue ──────────────────────────────────────────────


def enqueue_escalation(customer_id: str, **kwargs) -> EscalationQueue:
    esc = EscalationQueue(customer_id=customer_id, **kwargs)
    _escalations[esc.id] = esc
    event_bus.publish(customer_id, event_bus.EventType.ESCALATION_CREATED, {
        "escalation_id": esc.id, "call_id": esc.call_id,
        "priority": esc.priority, "reason": esc.reason,
    })
    return esc


def list_escalations(
    customer_id: str,
    status: EscalationStatus | None = None,
    department_id: str | None = None,
) -> list[EscalationQueue]:
    escs = [e for e in _escalations.values() if e.customer_id == customer_id]
    if status:
        escs = [e for e in escs if e.status == status]
    if department_id:
        escs = [e for e in escs if e.department_id == department_id]
    return sorted(escs, key=lambda e: e.created_at, reverse=True)


def get_escalation(esc_id: str) -> EscalationQueue | None:
    return _escalations.get(esc_id)


def assign_escalation(esc_id: str, human_agent_id: str) -> EscalationQueue | None:
    esc = _escalations.get(esc_id)
    if not esc or esc.status != EscalationStatus.WAITING:
        return None
    agent = _human_agents.get(human_agent_id)
    if not agent or agent.status != HumanAgentStatus.AVAILABLE:
        return None
    now = datetime.now(timezone.utc)
    esc.status = EscalationStatus.ASSIGNED
    esc.human_agent_id = human_agent_id
    esc.assigned_at = now
    esc.wait_time_seconds = (now - esc.created_at).total_seconds()
    # Mark agent busy
    agent.status = HumanAgentStatus.BUSY
    agent.current_call_id = esc.call_id
    event_bus.publish(esc.customer_id, event_bus.EventType.ESCALATION_ASSIGNED, {
        "escalation_id": esc.id, "agent_id": agent.id, "agent_name": agent.name,
        "wait_time_seconds": esc.wait_time_seconds,
    })
    return esc


def auto_assign_escalation(esc_id: str, customer_id: str) -> EscalationQueue | None:
    """Assign to the least-busy available agent with matching skills."""
    esc = _escalations.get(esc_id)
    if not esc or esc.status != EscalationStatus.WAITING:
        return None
    available = [
        a for a in _human_agents.values()
        if a.customer_id == customer_id
        and a.status == HumanAgentStatus.AVAILABLE
        and (not esc.department_id or a.department_id == esc.department_id)
    ]
    if not available:
        return None
    # Pick agent with fewest calls today
    best = min(available, key=lambda a: a.calls_handled_today)
    return assign_escalation(esc_id, best.id)


def resolve_escalation(esc_id: str) -> EscalationQueue | None:
    esc = _escalations.get(esc_id)
    if not esc or esc.status not in (EscalationStatus.WAITING, EscalationStatus.ASSIGNED):
        return None
    now = datetime.now(timezone.utc)
    esc.status = EscalationStatus.RESOLVED
    esc.resolved_at = now
    if esc.assigned_at:
        esc.handle_time_seconds = (now - esc.assigned_at).total_seconds()
    # Free up the human agent
    if esc.human_agent_id:
        agent = _human_agents.get(esc.human_agent_id)
        if agent:
            agent.status = HumanAgentStatus.AVAILABLE
            agent.current_call_id = None
            agent.calls_handled_today += 1
            agent.busy_minutes_today += esc.handle_time_seconds / 60.0
    event_bus.publish(esc.customer_id, event_bus.EventType.ESCALATION_RESOLVED, {
        "escalation_id": esc.id, "handle_time_seconds": esc.handle_time_seconds,
    })
    return esc


def abandon_escalation(esc_id: str) -> EscalationQueue | None:
    esc = _escalations.get(esc_id)
    if not esc or esc.status != EscalationStatus.WAITING:
        return None
    now = datetime.now(timezone.utc)
    esc.status = EscalationStatus.ABANDONED
    esc.wait_time_seconds = (now - esc.created_at).total_seconds()
    return esc


def get_queue_status(customer_id: str) -> dict:
    escs = [e for e in _escalations.values() if e.customer_id == customer_id]
    waiting = [e for e in escs if e.status == EscalationStatus.WAITING]
    assigned = [e for e in escs if e.status == EscalationStatus.ASSIGNED]
    resolved = [e for e in escs if e.status == EscalationStatus.RESOLVED]
    abandoned = [e for e in escs if e.status == EscalationStatus.ABANDONED]

    avg_wait = 0.0
    if resolved:
        avg_wait = sum(e.wait_time_seconds for e in resolved) / len(resolved)

    return {
        "waiting": len(waiting),
        "assigned": len(assigned),
        "resolved_today": len(resolved),
        "abandoned_today": len(abandoned),
        "avg_wait_time_seconds": round(avg_wait, 1),
        "longest_waiting_seconds": max(
            ((datetime.now(timezone.utc) - e.created_at).total_seconds() for e in waiting),
            default=0.0,
        ),
    }


# ── Volume Forecasting ────────────────────────────────────────────


def generate_forecast(
    customer_id: str,
    date: str,
    historical_calls: list[dict] | None = None,
    containment_rate: float = 0.80,
    calls_per_agent_per_hour: int = 4,
    target_wait_seconds: int = 60,
) -> list[StaffingForecast]:
    """Generate hourly staffing forecast for a given date.

    If historical_calls is provided, use it. Otherwise generate
    a realistic weekday pattern.
    """
    forecasts = []
    if historical_calls:
        # Group by hour and average
        by_hour: dict[int, list[int]] = {h: [] for h in range(24)}
        for record in historical_calls:
            by_hour[record.get("hour", 0)].append(record.get("volume", 0))
        hourly_volumes = {
            h: int(sum(vols) / len(vols)) if vols else 0
            for h, vols in by_hour.items()
        }
    else:
        # Default weekday pattern (realistic contact center curve)
        hourly_volumes = {
            0: 5, 1: 3, 2: 2, 3: 2, 4: 3, 5: 8,
            6: 15, 7: 30, 8: 55, 9: 75, 10: 85, 11: 80,
            12: 60, 13: 70, 14: 75, 15: 70, 16: 55, 17: 40,
            18: 25, 19: 18, 20: 12, 21: 10, 22: 8, 23: 6,
        }

    for hour in range(24):
        volume = hourly_volumes.get(hour, 0)
        ai_handled = int(volume * containment_rate)
        escalations = volume - ai_handled
        recommended = max(1, -(-escalations // calls_per_agent_per_hour))  # ceil division
        confidence = 0.85 if historical_calls else 0.65

        fc = StaffingForecast(
            customer_id=customer_id,
            date=date,
            hour=hour,
            predicted_volume=volume,
            predicted_ai_handled=ai_handled,
            predicted_escalations=escalations,
            recommended_staff=recommended,
            confidence=confidence,
        )
        _forecasts[fc.id] = fc
        forecasts.append(fc)

    return forecasts


def get_forecasts(customer_id: str, date: str) -> list[StaffingForecast]:
    return sorted(
        [f for f in _forecasts.values() if f.customer_id == customer_id and f.date == date],
        key=lambda f: f.hour,
    )


# ── Metrics & ROI ─────────────────────────────────────────────────


def calculate_metrics(
    customer_id: str,
    period_start: str,
    period_end: str,
    total_calls: int = 0,
    ai_handled: int = 0,
    human_handled: int = 0,
    avg_wait_time_seconds: float = 0.0,
    avg_handle_time_seconds: float = 0.0,
    ai_cost_per_minute_cents: int = 6,
) -> WorkforceMetrics:
    containment = ai_handled / total_calls if total_calls > 0 else 0.0
    escalation = human_handled / total_calls if total_calls > 0 else 0.0
    # Cost savings: compare AI cost vs estimated human cost
    # Assume 5 min avg call, human cost $20/hr = 33 cents/min
    human_cost_per_min = 33
    ai_mins = ai_handled * 5
    savings = ai_mins * (human_cost_per_min - ai_cost_per_minute_cents)

    metrics = WorkforceMetrics(
        customer_id=customer_id,
        period_start=period_start,
        period_end=period_end,
        total_calls=total_calls,
        ai_handled=ai_handled,
        human_handled=human_handled,
        containment_rate=round(containment, 4),
        avg_wait_time_seconds=avg_wait_time_seconds,
        avg_handle_time_seconds=avg_handle_time_seconds,
        escalation_rate=round(escalation, 4),
        cost_savings_cents=max(0, savings),
    )
    _metrics[metrics.id] = metrics
    return metrics


def get_containment_trend(customer_id: str, weeks: int = 8) -> list[dict]:
    """Return weekly containment rates. Uses stored metrics or generates sample data."""
    stored = sorted(
        [m for m in _metrics.values() if m.customer_id == customer_id],
        key=lambda m: m.period_start,
    )
    if stored:
        return [
            {
                "period": m.period_start,
                "containment_rate": m.containment_rate,
                "total_calls": m.total_calls,
            }
            for m in stored[-weeks:]
        ]
    # Sample trend showing improvement over time
    import random
    base_rate = 0.65
    trend = []
    for i in range(weeks):
        rate = min(0.95, base_rate + i * 0.03 + random.uniform(-0.02, 0.02))
        week_start = (datetime.now(timezone.utc) - timedelta(weeks=weeks - i)).strftime("%Y-%m-%d")
        trend.append({
            "period": week_start,
            "containment_rate": round(rate, 3),
            "total_calls": random.randint(800, 1500),
        })
    return trend


def calculate_roi(
    customer_id: str,
    human_agent_hourly_rate_cents: int = 2000,   # $20/hr
    calls_per_agent_per_hour: int = 4,
    total_monthly_calls: int = 10000,
    containment_rate: float = 0.80,
    avg_call_duration_minutes: float = 5.0,
    ai_cost_per_minute_cents: int = 6,
) -> ROIEstimate:
    """Calculate monthly ROI of AI vs full-human operation."""
    # Human-only cost: all calls handled by humans
    calls_per_agent_per_month = calls_per_agent_per_hour * 8 * 22  # 8hr/day, 22 days
    agents_needed = max(1, -(-total_monthly_calls // calls_per_agent_per_month))
    human_monthly_cost = agents_needed * human_agent_hourly_rate_cents * 8 * 22

    # AI hybrid cost: AI handles containment_rate, humans handle the rest
    ai_calls = int(total_monthly_calls * containment_rate)
    human_calls = total_monthly_calls - ai_calls
    ai_cost = int(ai_calls * avg_call_duration_minutes * ai_cost_per_minute_cents)
    remaining_agents = max(1, -(-human_calls // calls_per_agent_per_month))
    remaining_human_cost = remaining_agents * human_agent_hourly_rate_cents * 8 * 22
    hybrid_cost = ai_cost + remaining_human_cost

    monthly_savings = human_monthly_cost - hybrid_cost
    savings_pct = (monthly_savings / human_monthly_cost * 100) if human_monthly_cost > 0 else 0.0

    return ROIEstimate(
        human_cost_per_month_cents=human_monthly_cost,
        ai_cost_per_month_cents=hybrid_cost,
        monthly_savings_cents=max(0, monthly_savings),
        annual_savings_cents=max(0, monthly_savings * 12),
        savings_percentage=round(savings_pct, 1),
        calls_per_month=total_monthly_calls,
        containment_rate=containment_rate,
    )


# ── Dashboard Aggregation ─────────────────────────────────────────


def get_dashboard(customer_id: str) -> WorkforceDashboard:
    agents = list_human_agents(customer_id)
    active = [a for a in agents if a.status in (HumanAgentStatus.AVAILABLE, HumanAgentStatus.BUSY)]
    queue = get_queue_status(customer_id)
    trend = get_containment_trend(customer_id)
    recent_esc = list_escalations(customer_id)[:5]

    status_counts: dict[str, int] = {}
    for a in agents:
        status_counts[a.status.value] = status_counts.get(a.status.value, 0) + 1

    current_containment = trend[-1]["containment_rate"] if trend else 0.0
    current_escalation = 1.0 - current_containment

    return WorkforceDashboard(
        active_human_agents=len(active),
        total_human_agents=len(agents),
        queue_length=queue["waiting"],
        avg_wait_time_seconds=queue["avg_wait_time_seconds"],
        containment_rate=current_containment,
        containment_trend=trend,
        escalation_rate=round(current_escalation, 3),
        cost_savings_this_month_cents=0,  # Would come from metrics
        agents_by_status=status_counts,
        recent_escalations=recent_esc,
    )
