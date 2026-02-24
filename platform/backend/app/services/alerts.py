"""Alert service — monitor call metrics and trigger notifications.

Evaluates alert rules against real-time metrics and generates alerts
when thresholds are exceeded. Supports multiple alert types:
- Volume spikes
- Angry caller surges
- Low quality scores
- High escalation rates
- PII detections
- API/tool failures
- Cost thresholds

Alerts are stored in-memory (production would use DB + push notifications).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.models.database import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertSummary,
    AlertType,
)
from app.services import event_bus


# ──────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────

_rules: dict[str, AlertRule] = {}
_alerts: dict[str, Alert] = {}

MAX_ALERTS = 1000


# ──────────────────────────────────────────────────────────────────
# Rule CRUD
# ──────────────────────────────────────────────────────────────────

def create_rule(rule: AlertRule) -> AlertRule:
    _rules[rule.id] = rule
    logger.info(f"Alert rule created: {rule.name} ({rule.alert_type})")
    return rule


def get_rule(rule_id: str) -> AlertRule | None:
    return _rules.get(rule_id)


def list_rules(customer_id: str) -> list[AlertRule]:
    return [r for r in _rules.values() if r.customer_id == customer_id]


def update_rule(rule_id: str, updates: dict[str, Any]) -> AlertRule | None:
    rule = _rules.get(rule_id)
    if not rule:
        return None
    for key, value in updates.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    return rule


def delete_rule(rule_id: str) -> bool:
    return _rules.pop(rule_id, None) is not None


# ──────────────────────────────────────────────────────────────────
# Alert CRUD
# ──────────────────────────────────────────────────────────────────

def create_alert(alert: Alert) -> Alert:
    """Create and store a new alert."""
    # Evict oldest if at capacity
    if len(_alerts) >= MAX_ALERTS:
        oldest_key = min(_alerts, key=lambda k: _alerts[k].created_at)
        del _alerts[oldest_key]
    _alerts[alert.id] = alert
    logger.warning(f"ALERT [{alert.severity}]: {alert.title}")
    event_bus.publish(alert.customer_id, event_bus.EventType.ALERT_FIRED, {
        "alert_id": alert.id, "title": alert.title,
        "severity": alert.severity, "alert_type": alert.alert_type,
        "message": alert.message,
    })
    return alert


def get_alert(alert_id: str) -> Alert | None:
    return _alerts.get(alert_id)


def list_alerts(
    customer_id: str,
    unacknowledged_only: bool = False,
    severity: str | None = None,
    limit: int = 50,
) -> list[Alert]:
    alerts = [a for a in _alerts.values() if a.customer_id == customer_id]
    if unacknowledged_only:
        alerts = [a for a in alerts if not a.acknowledged]
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    alerts.sort(key=lambda a: a.created_at, reverse=True)
    return alerts[:limit]


def acknowledge_alert(alert_id: str) -> Alert | None:
    alert = _alerts.get(alert_id)
    if alert:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
    return alert


def acknowledge_all(customer_id: str) -> int:
    count = 0
    for alert in _alerts.values():
        if alert.customer_id == customer_id and not alert.acknowledged:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            count += 1
    return count


def get_alert_summary(customer_id: str) -> AlertSummary:
    alerts = [a for a in _alerts.values() if a.customer_id == customer_id]
    return AlertSummary(
        total=len(alerts),
        unacknowledged=sum(1 for a in alerts if not a.acknowledged),
        critical=sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
        warning=sum(1 for a in alerts if a.severity == AlertSeverity.WARNING),
        info=sum(1 for a in alerts if a.severity == AlertSeverity.INFO),
        recent=sorted(alerts, key=lambda a: a.created_at, reverse=True)[:10],
    )


# ──────────────────────────────────────────────────────────────────
# Alert evaluation engine
# ──────────────────────────────────────────────────────────────────

def evaluate_rule(
    rule: AlertRule,
    metrics: dict[str, Any],
) -> Alert | None:
    """Evaluate a single alert rule against current metrics.

    Args:
        rule: The alert rule to evaluate.
        metrics: Current metrics dict with keys like:
            - calls_in_window: int
            - angry_callers_in_window: int
            - avg_quality_score: float
            - escalation_rate: float (0-100)
            - pii_detected: bool
            - daily_cost_cents: int
            - api_failure_count: int

    Returns:
        An Alert if the rule triggered, None otherwise.
    """
    if not rule.enabled:
        return None

    triggered = False
    title = ""
    message = ""
    severity = rule.severity
    metadata: dict[str, Any] = {}

    if rule.alert_type == AlertType.HIGH_VOLUME:
        threshold = rule.config.get("threshold", 100)
        calls = metrics.get("calls_in_window", 0)
        if calls >= threshold:
            triggered = True
            title = f"High call volume: {calls} calls"
            message = f"Call volume ({calls}) exceeded threshold ({threshold}) in the monitoring window."
            metadata = {"calls": calls, "threshold": threshold}

    elif rule.alert_type == AlertType.ANGRY_CALLER_SPIKE:
        threshold = rule.config.get("threshold", 5)
        angry = metrics.get("angry_callers_in_window", 0)
        if angry >= threshold:
            triggered = True
            title = f"Angry caller spike: {angry} callers"
            message = f"{angry} angry callers detected, exceeding threshold of {threshold}."
            metadata = {"angry_callers": angry, "threshold": threshold}

    elif rule.alert_type == AlertType.LOW_QUALITY_SCORE:
        threshold = rule.config.get("threshold", 50)
        score = metrics.get("avg_quality_score", 100)
        if score <= threshold:
            triggered = True
            title = f"Low quality score: {score:.0f}"
            message = f"Average quality score ({score:.0f}) fell below threshold ({threshold})."
            severity = AlertSeverity.CRITICAL if score < 30 else severity
            metadata = {"score": score, "threshold": threshold}

    elif rule.alert_type == AlertType.HIGH_ESCALATION_RATE:
        threshold = rule.config.get("threshold_percent", 40)
        min_calls = rule.config.get("min_calls", 10)
        rate = metrics.get("escalation_rate", 0)
        total = metrics.get("calls_in_window", 0)
        if total >= min_calls and rate >= threshold:
            triggered = True
            title = f"High escalation rate: {rate:.0f}%"
            message = f"Escalation rate ({rate:.0f}%) exceeded threshold ({threshold}%) with {total} calls."
            metadata = {"rate": rate, "threshold": threshold, "total_calls": total}

    elif rule.alert_type == AlertType.PII_DETECTED:
        if metrics.get("pii_detected", False):
            triggered = True
            title = "PII detected in call"
            message = "Personal identifiable information was detected in a call transcript."
            severity = AlertSeverity.CRITICAL
            metadata = {"call_id": metrics.get("call_id", "")}

    elif rule.alert_type == AlertType.AGENT_DOWN:
        if metrics.get("agent_error", False):
            triggered = True
            title = f"Agent error: {metrics.get('agent_name', 'Unknown')}"
            message = f"Agent failed to respond: {metrics.get('error_message', 'Unknown error')}"
            severity = AlertSeverity.CRITICAL
            metadata = {"agent_id": metrics.get("agent_id", "")}

    elif rule.alert_type == AlertType.API_FAILURE:
        failures = metrics.get("api_failure_count", 0)
        threshold = rule.config.get("threshold", 3)
        if failures >= threshold:
            triggered = True
            title = f"API failures: {failures} in window"
            message = f"Tool/API call failures ({failures}) exceeded threshold ({threshold})."
            metadata = {"failures": failures}

    elif rule.alert_type == AlertType.COST_THRESHOLD:
        daily_limit = rule.config.get("daily_limit_cents", 10000)
        daily_cost = metrics.get("daily_cost_cents", 0)
        if daily_cost >= daily_limit:
            triggered = True
            title = f"Cost threshold reached: ${daily_cost / 100:.2f}"
            message = f"Daily cost (${daily_cost / 100:.2f}) reached limit (${daily_limit / 100:.2f})."
            severity = AlertSeverity.CRITICAL
            metadata = {"cost_cents": daily_cost, "limit_cents": daily_limit}

    if triggered:
        return Alert(
            customer_id=rule.customer_id,
            rule_id=rule.id,
            alert_type=rule.alert_type,
            severity=severity,
            title=title,
            message=message,
            metadata=metadata,
        )

    return None


def evaluate_all_rules(customer_id: str, metrics: dict[str, Any]) -> list[Alert]:
    """Evaluate all enabled rules for a customer and create alerts."""
    rules = list_rules(customer_id)
    triggered: list[Alert] = []
    for rule in rules:
        alert = evaluate_rule(rule, metrics)
        if alert:
            create_alert(alert)
            triggered.append(alert)
    return triggered


# ──────────────────────────────────────────────────────────────────
# Default rules factory
# ──────────────────────────────────────────────────────────────────

def create_default_rules(customer_id: str) -> list[AlertRule]:
    """Create a sensible set of default alert rules for a new customer."""
    defaults = [
        AlertRule(
            customer_id=customer_id,
            name="High Call Volume",
            alert_type=AlertType.HIGH_VOLUME,
            severity=AlertSeverity.WARNING,
            config={"threshold": 100, "window_minutes": 60},
        ),
        AlertRule(
            customer_id=customer_id,
            name="Angry Caller Spike",
            alert_type=AlertType.ANGRY_CALLER_SPIKE,
            severity=AlertSeverity.WARNING,
            config={"threshold": 5, "window_minutes": 30},
        ),
        AlertRule(
            customer_id=customer_id,
            name="Low Quality Score",
            alert_type=AlertType.LOW_QUALITY_SCORE,
            severity=AlertSeverity.CRITICAL,
            config={"threshold": 50},
        ),
        AlertRule(
            customer_id=customer_id,
            name="High Escalation Rate",
            alert_type=AlertType.HIGH_ESCALATION_RATE,
            severity=AlertSeverity.WARNING,
            config={"threshold_percent": 40, "min_calls": 10},
        ),
        AlertRule(
            customer_id=customer_id,
            name="PII Detection",
            alert_type=AlertType.PII_DETECTED,
            severity=AlertSeverity.CRITICAL,
            config={},
        ),
        AlertRule(
            customer_id=customer_id,
            name="Daily Cost Limit",
            alert_type=AlertType.COST_THRESHOLD,
            severity=AlertSeverity.WARNING,
            config={"daily_limit_cents": 10000},
        ),
    ]
    for rule in defaults:
        create_rule(rule)
    return defaults
