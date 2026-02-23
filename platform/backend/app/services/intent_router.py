"""Intent Router — classify caller intent and route to departments.

Replaces traditional IVR ("Press 1 for Sales, 2 for Support...") with
AI-based intent classification. The caller speaks naturally and the
router determines which department should handle the call.

Supports multiple classification strategies:
1. Keyword matching (fast, no API needed)
2. Regex patterns (flexible rules)
3. AI/NLP intent classification (most accurate, requires LLM)
4. DTMF fallback (traditional keypress routing)
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.models.database import (
    Department,
    RoutingResult,
    RoutingRule,
)


# ──────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────

_departments: dict[str, Department] = {}
_rules: dict[str, RoutingRule] = {}


# ──────────────────────────────────────────────────────────────────
# Department CRUD
# ──────────────────────────────────────────────────────────────────

def create_department(dept: Department) -> Department:
    _departments[dept.id] = dept
    logger.info(f"Department created: {dept.name}")
    return dept


def get_department(dept_id: str) -> Department | None:
    return _departments.get(dept_id)


def list_departments(customer_id: str) -> list[Department]:
    depts = [d for d in _departments.values() if d.customer_id == customer_id]
    return sorted(depts, key=lambda d: d.priority)


def update_department(dept_id: str, updates: dict[str, Any]) -> Department | None:
    dept = _departments.get(dept_id)
    if not dept:
        return None
    for key, value in updates.items():
        if hasattr(dept, key):
            setattr(dept, key, value)
    return dept


def delete_department(dept_id: str) -> bool:
    return _departments.pop(dept_id, None) is not None


# ──────────────────────────────────────────────────────────────────
# Routing Rule CRUD
# ──────────────────────────────────────────────────────────────────

def create_rule(rule: RoutingRule) -> RoutingRule:
    _rules[rule.id] = rule
    return rule


def get_rule(rule_id: str) -> RoutingRule | None:
    return _rules.get(rule_id)


def list_rules(customer_id: str) -> list[RoutingRule]:
    rules = [r for r in _rules.values() if r.customer_id == customer_id]
    return sorted(rules, key=lambda r: r.priority)


def delete_rule(rule_id: str) -> bool:
    return _rules.pop(rule_id, None) is not None


# ──────────────────────────────────────────────────────────────────
# Intent classification
# ──────────────────────────────────────────────────────────────────

def classify_by_keywords(
    text: str,
    departments: list[Department],
) -> RoutingResult | None:
    """Classify intent using keyword matching against department configs.

    Scores each department by counting keyword matches in the user's text.
    Returns the best match or None if no keywords match.
    """
    text_lower = text.lower()
    best_dept = None
    best_score = 0
    matched_keywords: list[str] = []

    for dept in departments:
        if not dept.enabled or not dept.intent_keywords:
            continue
        score = 0
        hits: list[str] = []
        for keyword in dept.intent_keywords:
            if keyword.lower() in text_lower:
                score += 1
                hits.append(keyword)
        if score > best_score:
            best_score = score
            best_dept = dept
            matched_keywords = hits

    if best_dept and best_score > 0:
        confidence = min(1.0, best_score / max(len(best_dept.intent_keywords), 1))
        return RoutingResult(
            department_id=best_dept.id,
            department_name=best_dept.name,
            agent_id=best_dept.agent_id,
            transfer_number=best_dept.transfer_number,
            confidence=round(confidence, 2),
            matched_keywords=matched_keywords,
        )
    return None


def classify_by_rules(
    text: str,
    rules: list[RoutingRule],
    departments: list[Department],
) -> RoutingResult | None:
    """Classify intent using routing rules (keyword, regex, dtmf)."""
    text_lower = text.lower().strip()
    dept_map = {d.id: d for d in departments}

    for rule in sorted(rules, key=lambda r: r.priority):
        if not rule.enabled:
            continue

        matched = False
        if rule.match_type == "keyword":
            keywords = [k.strip().lower() for k in rule.match_value.split(",")]
            matched = any(kw in text_lower for kw in keywords if kw)
        elif rule.match_type == "regex":
            try:
                matched = bool(re.search(rule.match_value, text_lower))
            except re.error:
                pass
        elif rule.match_type == "dtmf":
            matched = text_lower.strip() == rule.match_value.strip()
        elif rule.match_type == "intent_model":
            # Placeholder for ML-based classification
            matched = False

        if matched:
            dept = dept_map.get(rule.department_id)
            if dept:
                return RoutingResult(
                    department_id=dept.id,
                    department_name=dept.name,
                    agent_id=dept.agent_id,
                    transfer_number=dept.transfer_number,
                    confidence=0.8,
                    matched_rule=rule.id,
                    matched_keywords=[rule.match_value],
                )
    return None


def route_call(
    text: str,
    customer_id: str,
    dtmf_input: str = "",
) -> RoutingResult:
    """Route a call to a department based on caller input.

    Tries classification strategies in order:
    1. DTMF input (if provided)
    2. Routing rules (keyword/regex)
    3. Department keyword matching
    4. Fallback to default department

    Args:
        text: Caller's spoken input (transcribed).
        customer_id: Customer ID for looking up routing config.
        dtmf_input: Optional DTMF digits pressed.

    Returns:
        RoutingResult with the selected department.
    """
    departments = list_departments(customer_id)
    rules = list_rules(customer_id)

    if not departments:
        return RoutingResult(
            department_name="Default",
            confidence=0.0,
            fallback=True,
        )

    # 1. Try DTMF routing
    if dtmf_input:
        result = classify_by_rules(dtmf_input, rules, departments)
        if result:
            logger.info(f"DTMF routed to {result.department_name}")
            return result

    # 2. Try routing rules
    if text:
        result = classify_by_rules(text, rules, departments)
        if result:
            logger.info(f"Rule routed to {result.department_name}")
            return result

    # 3. Try keyword matching on departments
    if text:
        result = classify_by_keywords(text, departments)
        if result:
            logger.info(f"Keyword routed to {result.department_name}")
            return result

    # 4. Fall back to default department
    default = next((d for d in departments if d.is_default), departments[0])
    logger.info(f"Fallback routed to {default.name}")
    return RoutingResult(
        department_id=default.id,
        department_name=default.name,
        agent_id=default.agent_id,
        transfer_number=default.transfer_number,
        confidence=0.0,
        fallback=True,
    )


# ──────────────────────────────────────────────────────────────────
# Default departments factory
# ──────────────────────────────────────────────────────────────────

def create_default_departments(customer_id: str) -> list[Department]:
    """Create a standard set of departments for a new customer."""
    defaults = [
        Department(
            customer_id=customer_id,
            name="Sales",
            description="Handle inquiries about products, pricing, and purchases",
            priority=1,
            intent_keywords=["buy", "purchase", "price", "pricing", "quote", "cost", "plan", "upgrade", "demo", "trial"],
        ),
        Department(
            customer_id=customer_id,
            name="Support",
            description="Technical support and troubleshooting",
            priority=2,
            is_default=True,
            intent_keywords=["help", "problem", "issue", "broken", "not working", "error", "bug", "fix", "trouble", "support"],
        ),
        Department(
            customer_id=customer_id,
            name="Billing",
            description="Billing, payments, invoices, and refunds",
            priority=3,
            intent_keywords=["bill", "billing", "invoice", "payment", "charge", "refund", "cancel", "subscription"],
        ),
    ]
    for dept in defaults:
        create_department(dept)
    return defaults
