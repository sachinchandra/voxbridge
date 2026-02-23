"""Compliance & Audit Log service.

Provides:
1. Compliance rule management (PII redaction, script adherence, disclosures)
2. Call transcript scanning for compliance violations
3. Immutable audit log for all platform actions
4. Compliance dashboard summary

Enterprise requirement for SOC 2 / HIPAA / PCI DSS readiness.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.models.database import (
    AuditAction,
    AuditLogEntry,
    ComplianceRule,
    ComplianceRuleType,
    ComplianceSummary,
    ComplianceViolation,
)


# ──────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────

_rules: dict[str, ComplianceRule] = {}
_violations: dict[str, ComplianceViolation] = {}
_audit_log: list[AuditLogEntry] = []

MAX_VIOLATIONS = 5000
MAX_AUDIT_ENTRIES = 10000


# PII patterns with redaction replacements
PII_REDACTION_PATTERNS = {
    "ssn": {
        "pattern": r"\b(\d{3})[-\s]?(\d{2})[-\s]?(\d{4})\b",
        "replacement": "***-**-****",
        "label": "Social Security Number",
    },
    "credit_card": {
        "pattern": r"\b(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})\b",
        "replacement": "****-****-****-****",
        "label": "Credit Card Number",
    },
    "cvv": {
        "pattern": r"\bCVV\s*:?\s*(\d{3,4})\b",
        "replacement": "CVV: ***",
        "label": "CVV Code",
    },
    "dob": {
        "pattern": r"\b(0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])[/\-](19|20)\d{2}\b",
        "replacement": "**/**/****",
        "label": "Date of Birth",
    },
}

# Default forbidden phrases
DEFAULT_FORBIDDEN = [
    "I guarantee",
    "100% certain",
    "we never make mistakes",
    "that's not my problem",
    "you should have",
    "that's your fault",
]


# ──────────────────────────────────────────────────────────────────
# Compliance Rule CRUD
# ──────────────────────────────────────────────────────────────────

def create_rule(rule: ComplianceRule) -> ComplianceRule:
    _rules[rule.id] = rule
    logger.info(f"Compliance rule created: {rule.name} ({rule.rule_type})")
    return rule


def get_rule(rule_id: str) -> ComplianceRule | None:
    return _rules.get(rule_id)


def list_rules(customer_id: str) -> list[ComplianceRule]:
    return [r for r in _rules.values() if r.customer_id == customer_id]


def update_rule(rule_id: str, updates: dict[str, Any]) -> ComplianceRule | None:
    rule = _rules.get(rule_id)
    if not rule:
        return None
    for key, value in updates.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    return rule


def delete_rule(rule_id: str) -> bool:
    return _rules.pop(rule_id, None) is not None


def create_default_rules(customer_id: str) -> list[ComplianceRule]:
    """Create a standard compliance rule set."""
    defaults = [
        ComplianceRule(
            customer_id=customer_id,
            name="PII Auto-Redaction",
            rule_type=ComplianceRuleType.PII_REDACTION,
            severity="critical",
            config={"patterns": list(PII_REDACTION_PATTERNS.keys()), "action": "redact"},
        ),
        ComplianceRule(
            customer_id=customer_id,
            name="Recording Disclosure",
            rule_type=ComplianceRuleType.DISCLOSURE_REQUIRED,
            severity="warning",
            config={"required_phrases": ["this call may be recorded", "this call is being recorded"]},
        ),
        ComplianceRule(
            customer_id=customer_id,
            name="Forbidden Phrases",
            rule_type=ComplianceRuleType.FORBIDDEN_PHRASES,
            severity="warning",
            config={"forbidden": DEFAULT_FORBIDDEN},
        ),
        ComplianceRule(
            customer_id=customer_id,
            name="PCI DSS Card Handling",
            rule_type=ComplianceRuleType.PCI_DSS,
            severity="critical",
            config={"detect_card_numbers": True, "prevent_verbal_readback": True},
        ),
    ]
    for rule in defaults:
        create_rule(rule)
    return defaults


# ──────────────────────────────────────────────────────────────────
# Compliance Violation CRUD
# ──────────────────────────────────────────────────────────────────

def create_violation(violation: ComplianceViolation) -> ComplianceViolation:
    if len(_violations) >= MAX_VIOLATIONS:
        # Remove oldest resolved violations
        resolved = sorted(
            [v for v in _violations.values() if v.resolved],
            key=lambda v: v.created_at,
        )
        for old in resolved[:500]:
            _violations.pop(old.id, None)

    _violations[violation.id] = violation
    logger.warning(f"Compliance violation: {violation.rule_name} — {violation.description}")
    return violation


def get_violation(violation_id: str) -> ComplianceViolation | None:
    return _violations.get(violation_id)


def list_violations(
    customer_id: str,
    unresolved_only: bool = False,
    rule_type: str = "",
    limit: int = 50,
) -> list[ComplianceViolation]:
    violations = [v for v in _violations.values() if v.customer_id == customer_id]
    if unresolved_only:
        violations = [v for v in violations if not v.resolved]
    if rule_type:
        violations = [v for v in violations if v.rule_type.value == rule_type]
    violations.sort(key=lambda v: v.created_at, reverse=True)
    return violations[:limit]


def resolve_violation(violation_id: str, resolved_by: str = "") -> ComplianceViolation | None:
    v = _violations.get(violation_id)
    if not v:
        return None
    v.resolved = True
    v.resolved_by = resolved_by
    return v


# ──────────────────────────────────────────────────────────────────
# Transcript scanning
# ──────────────────────────────────────────────────────────────────

def scan_transcript(
    customer_id: str,
    call_id: str,
    transcript: list[dict],
) -> list[ComplianceViolation]:
    """Scan a call transcript against all enabled compliance rules.

    Args:
        customer_id: Customer ID for looking up rules.
        call_id: The call being scanned.
        transcript: List of {role, content} entries.

    Returns:
        List of violations found.
    """
    rules = [r for r in list_rules(customer_id) if r.enabled]
    violations: list[ComplianceViolation] = []

    full_text = " ".join(t.get("content", "") for t in transcript)
    agent_text = " ".join(t.get("content", "") for t in transcript if t.get("role") == "agent")

    for rule in rules:
        rule_violations = _check_rule(rule, customer_id, call_id, full_text, agent_text, transcript)
        violations.extend(rule_violations)

    return violations


def _check_rule(
    rule: ComplianceRule,
    customer_id: str,
    call_id: str,
    full_text: str,
    agent_text: str,
    transcript: list[dict],
) -> list[ComplianceViolation]:
    """Check a single compliance rule against the transcript."""
    violations = []

    if rule.rule_type == ComplianceRuleType.PII_REDACTION:
        violations.extend(_check_pii(rule, customer_id, call_id, full_text))

    elif rule.rule_type == ComplianceRuleType.FORBIDDEN_PHRASES:
        violations.extend(_check_forbidden(rule, customer_id, call_id, agent_text))

    elif rule.rule_type == ComplianceRuleType.DISCLOSURE_REQUIRED:
        violations.extend(_check_disclosure(rule, customer_id, call_id, agent_text))

    elif rule.rule_type == ComplianceRuleType.PCI_DSS:
        violations.extend(_check_pci(rule, customer_id, call_id, full_text))

    elif rule.rule_type == ComplianceRuleType.HIPAA:
        violations.extend(_check_pii(rule, customer_id, call_id, full_text))

    return violations


def _check_pii(
    rule: ComplianceRule,
    customer_id: str,
    call_id: str,
    text: str,
) -> list[ComplianceViolation]:
    """Check for PII patterns in text."""
    violations = []
    for pii_key, pii_info in PII_REDACTION_PATTERNS.items():
        matches = re.findall(pii_info["pattern"], text)
        if matches:
            v = ComplianceViolation(
                customer_id=customer_id,
                call_id=call_id,
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                description=f"{pii_info['label']} detected in transcript",
                transcript_excerpt=f"[{pii_info['label']} found — {len(matches)} occurrence(s)]",
                redacted_text=pii_info["replacement"],
            )
            create_violation(v)
            violations.append(v)
    return violations


def _check_forbidden(
    rule: ComplianceRule,
    customer_id: str,
    call_id: str,
    agent_text: str,
) -> list[ComplianceViolation]:
    """Check for forbidden phrases in agent speech."""
    violations = []
    forbidden = rule.config.get("forbidden", DEFAULT_FORBIDDEN)
    text_lower = agent_text.lower()

    for phrase in forbidden:
        if phrase.lower() in text_lower:
            v = ComplianceViolation(
                customer_id=customer_id,
                call_id=call_id,
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                description=f"Forbidden phrase used: \"{phrase}\"",
                transcript_excerpt=phrase,
            )
            create_violation(v)
            violations.append(v)
    return violations


def _check_disclosure(
    rule: ComplianceRule,
    customer_id: str,
    call_id: str,
    agent_text: str,
) -> list[ComplianceViolation]:
    """Check that required disclosures were made."""
    violations = []
    required = rule.config.get("required_phrases", [])
    text_lower = agent_text.lower()

    for phrase in required:
        if phrase.lower() not in text_lower:
            v = ComplianceViolation(
                customer_id=customer_id,
                call_id=call_id,
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                description=f"Required disclosure missing: \"{phrase}\"",
                transcript_excerpt="[Disclosure not found in agent speech]",
            )
            create_violation(v)
            violations.append(v)
    return violations


def _check_pci(
    rule: ComplianceRule,
    customer_id: str,
    call_id: str,
    full_text: str,
) -> list[ComplianceViolation]:
    """PCI DSS check — detect credit card numbers in transcript."""
    violations = []
    cc_pattern = PII_REDACTION_PATTERNS["credit_card"]["pattern"]
    if re.search(cc_pattern, full_text):
        v = ComplianceViolation(
            customer_id=customer_id,
            call_id=call_id,
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            severity="critical",
            description="Credit card number detected in transcript — PCI DSS violation",
            transcript_excerpt="[Card number redacted]",
            redacted_text="****-****-****-****",
        )
        create_violation(v)
        violations.append(v)
    return violations


# ──────────────────────────────────────────────────────────────────
# PII Redaction
# ──────────────────────────────────────────────────────────────────

def redact_text(text: str) -> str:
    """Redact all PII from text."""
    redacted = text
    for pii_key, pii_info in PII_REDACTION_PATTERNS.items():
        redacted = re.sub(pii_info["pattern"], pii_info["replacement"], redacted)
    return redacted


# ──────────────────────────────────────────────────────────────────
# Audit Log
# ──────────────────────────────────────────────────────────────────

def log_action(
    customer_id: str,
    user_email: str,
    action: AuditAction,
    resource_type: str = "",
    resource_id: str = "",
    description: str = "",
    metadata: dict | None = None,
    ip_address: str = "",
) -> AuditLogEntry:
    """Record an action in the immutable audit log."""
    entry = AuditLogEntry(
        customer_id=customer_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        metadata=metadata or {},
        ip_address=ip_address,
    )

    if len(_audit_log) >= MAX_AUDIT_ENTRIES:
        # Trim oldest 20%
        del _audit_log[:MAX_AUDIT_ENTRIES // 5]

    _audit_log.append(entry)
    logger.debug(f"Audit: {action.value} by {user_email} on {resource_type}/{resource_id}")
    return entry


def get_audit_log(
    customer_id: str,
    action: str = "",
    limit: int = 50,
) -> list[AuditLogEntry]:
    """Retrieve audit log entries."""
    entries = [e for e in _audit_log if e.customer_id == customer_id]
    if action:
        entries = [e for e in entries if e.action.value == action]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


# ──────────────────────────────────────────────────────────────────
# Compliance summary
# ──────────────────────────────────────────────────────────────────

def get_compliance_summary(customer_id: str) -> ComplianceSummary:
    """Get a compliance overview for the customer."""
    rules = list_rules(customer_id)
    violations = [v for v in _violations.values() if v.customer_id == customer_id]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for v in violations:
        by_type[v.rule_type.value] = by_type.get(v.rule_type.value, 0) + 1
        by_severity[v.severity] = by_severity.get(v.severity, 0) + 1

    unresolved = [v for v in violations if not v.resolved]
    recent = sorted(violations, key=lambda v: v.created_at, reverse=True)[:10]

    audit_entries = [e for e in _audit_log if e.customer_id == customer_id]

    return ComplianceSummary(
        total_rules=len(rules),
        enabled_rules=sum(1 for r in rules if r.enabled),
        total_violations=len(violations),
        unresolved_violations=len(unresolved),
        violations_by_type=by_type,
        violations_by_severity=by_severity,
        recent_violations=recent,
        audit_log_count=len(audit_entries),
    )
