"""Sprint 9 tests — Agent Assist + Compliance & Audit Log.

Tests cover:
  - Assist session models
  - Assist session CRUD
  - Transcript processing + suggestion generation
  - PII detection
  - Sentiment detection
  - Response suggestions
  - Accept / dismiss suggestions
  - Call summary generation
  - Assist summary stats

  - Compliance rule models
  - Compliance rule CRUD + defaults
  - PII redaction
  - Transcript scanning (PII, forbidden phrases, disclosures, PCI)
  - Violation CRUD + resolution
  - Audit log
  - Compliance summary
"""

import pytest

from app.models.database import (
    AssistSession,
    AssistSessionStatus,
    AssistSuggestion,
    SuggestionType,
    ComplianceRule,
    ComplianceRuleType,
    ComplianceViolation,
    AuditAction,
    AuditLogEntry,
)
from app.services import agent_assist as assist_svc
from app.services import compliance as comp_svc


CUSTOMER_ID = "cust_test_sprint9"


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear all in-memory stores before each test."""
    assist_svc._sessions.clear()
    comp_svc._rules.clear()
    comp_svc._violations.clear()
    comp_svc._audit_log.clear()
    yield
    assist_svc._sessions.clear()
    comp_svc._rules.clear()
    comp_svc._violations.clear()
    comp_svc._audit_log.clear()


# ──────────────────────────────────────────────────────────────────
# Agent Assist Model tests
# ──────────────────────────────────────────────────────────────────

class TestAssistModels:
    def test_assist_session_defaults(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assert s.status == AssistSessionStatus.ACTIVE
        assert s.suggestions == []
        assert s.transcript == []
        assert s.caller_sentiment == "neutral"
        assert s.pii_detected is False

    def test_suggestion_defaults(self):
        s = AssistSuggestion(session_id="s1", content="Try saying hello")
        assert s.type == SuggestionType.RESPONSE
        assert s.accepted is None
        assert s.confidence == 0.0

    def test_suggestion_types(self):
        for st in SuggestionType:
            s = AssistSuggestion(session_id="s1", type=st)
            assert s.type == st


# ──────────────────────────────────────────────────────────────────
# Assist Session CRUD tests
# ──────────────────────────────────────────────────────────────────

class TestAssistSessionCRUD:
    def test_create_session(self):
        s = AssistSession(customer_id=CUSTOMER_ID, call_id="call_1", human_agent_name="Alice")
        result = assist_svc.create_session(s)
        assert result.human_agent_name == "Alice"
        assert assist_svc.get_session(s.id) is not None

    def test_list_sessions(self):
        assist_svc.create_session(AssistSession(customer_id=CUSTOMER_ID))
        assist_svc.create_session(AssistSession(customer_id=CUSTOMER_ID))
        assist_svc.create_session(AssistSession(customer_id="other"))
        assert len(assist_svc.list_sessions(CUSTOMER_ID)) == 2

    def test_list_active_only(self):
        s1 = AssistSession(customer_id=CUSTOMER_ID)
        s2 = AssistSession(customer_id=CUSTOMER_ID, status=AssistSessionStatus.COMPLETED)
        assist_svc.create_session(s1)
        assist_svc.create_session(s2)
        active = assist_svc.list_sessions(CUSTOMER_ID, active_only=True)
        assert len(active) == 1

    def test_end_session(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.add_transcript_entry(s.id, "caller", "Hello")
        result = assist_svc.end_session(s.id)
        assert result.status == AssistSessionStatus.COMPLETED
        assert result.ended_at is not None
        assert result.call_summary != ""

    def test_end_nonexistent_session(self):
        assert assist_svc.end_session("nonexistent") is None

    def test_delete_session(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assert assist_svc.delete_session(s.id) is True
        assert assist_svc.get_session(s.id) is None


# ──────────────────────────────────────────────────────────────────
# PII detection tests
# ──────────────────────────────────────────────────────────────────

class TestPIIDetection:
    def test_detect_ssn(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "My SSN is 123-45-6789")
        compliance = [su for su in suggestions if su.type == SuggestionType.COMPLIANCE]
        assert len(compliance) >= 1
        assert s.pii_detected is True

    def test_detect_credit_card(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "My card is 4111 1111 1111 1111")
        compliance = [su for su in suggestions if su.type == SuggestionType.COMPLIANCE]
        assert len(compliance) >= 1

    def test_no_pii(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I just wanted to say hello")
        compliance = [su for su in suggestions if su.type == SuggestionType.COMPLIANCE]
        assert len(compliance) == 0
        assert s.pii_detected is False


# ──────────────────────────────────────────────────────────────────
# Sentiment detection tests
# ──────────────────────────────────────────────────────────────────

class TestSentimentDetection:
    def test_detect_negative_sentiment(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(
            s.id, "caller", "This is ridiculous! I'm furious! This is the worst service ever!"
        )
        sentiment = [su for su in suggestions if su.type == SuggestionType.SENTIMENT]
        assert len(sentiment) >= 1
        assert s.caller_sentiment == "negative"

    def test_mild_negative(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I'm frustrated with this")
        assert s.caller_sentiment == "negative"

    def test_neutral_sentiment(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.add_transcript_entry(s.id, "caller", "I'd like to check my order status")
        assert s.caller_sentiment == "neutral"


# ──────────────────────────────────────────────────────────────────
# Response suggestion tests
# ──────────────────────────────────────────────────────────────────

class TestResponseSuggestions:
    def test_order_status_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I want to track my order")
        responses = [su for su in suggestions if su.type == SuggestionType.RESPONSE]
        assert len(responses) >= 1
        assert any("order" in r.content.lower() for r in responses)

    def test_refund_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I need a refund")
        responses = [su for su in suggestions if su.type == SuggestionType.RESPONSE]
        assert len(responses) >= 1

    def test_knowledge_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "How do I reset my password?")
        knowledge = [su for su in suggestions if su.type == SuggestionType.KNOWLEDGE]
        assert len(knowledge) >= 1

    def test_cancel_action_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I want to cancel my subscription")
        actions = [su for su in suggestions if su.type == SuggestionType.ACTION]
        assert len(actions) >= 1

    def test_no_suggestions_for_agent(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        # Agent speech shouldn't generate response suggestions (but may generate PII checks)
        suggestions = assist_svc.add_transcript_entry(s.id, "agent", "Let me help you with that")
        responses = [su for su in suggestions if su.type == SuggestionType.RESPONSE]
        assert len(responses) == 0

    def test_no_suggestions_for_ended_session(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.end_session(s.id)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "Hello")
        assert len(suggestions) == 0


# ──────────────────────────────────────────────────────────────────
# Accept / dismiss tests
# ──────────────────────────────────────────────────────────────────

class TestAcceptDismiss:
    def test_accept_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I need help with a problem")
        if suggestions:
            result = assist_svc.accept_suggestion(s.id, suggestions[0].id)
            assert result.accepted is True
            assert s.suggestions_accepted == 1

    def test_dismiss_suggestion(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        suggestions = assist_svc.add_transcript_entry(s.id, "caller", "I need help with a problem")
        if suggestions:
            result = assist_svc.dismiss_suggestion(s.id, suggestions[0].id)
            assert result.accepted is False
            assert s.suggestions_dismissed == 1

    def test_accept_nonexistent(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assert assist_svc.accept_suggestion(s.id, "fake_id") is None


# ──────────────────────────────────────────────────────────────────
# Call summary tests
# ──────────────────────────────────────────────────────────────────

class TestCallSummary:
    def test_generate_summary(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.add_transcript_entry(s.id, "caller", "I need help with my order")
        assist_svc.add_transcript_entry(s.id, "agent", "Sure, let me look that up")
        assist_svc.end_session(s.id)
        assert "2 exchanges" in s.call_summary

    def test_generate_next_steps_with_pii(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.add_transcript_entry(s.id, "caller", "My SSN is 123-45-6789")
        assist_svc.end_session(s.id)
        assert any("PII" in step for step in s.next_steps)

    def test_generate_next_steps_negative(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        assist_svc.add_transcript_entry(s.id, "caller", "This is terrible! Worst service! Unacceptable! I'm furious!")
        assist_svc.end_session(s.id)
        assert any("follow up" in step.lower() for step in s.next_steps)

    def test_empty_transcript_summary(self):
        s = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s)
        summary = assist_svc.generate_call_summary(s)
        assert "No transcript" in summary


# ──────────────────────────────────────────────────────────────────
# Assist summary stats tests
# ──────────────────────────────────────────────────────────────────

class TestAssistSummary:
    def test_empty_summary(self):
        summary = assist_svc.get_assist_summary(CUSTOMER_ID)
        assert summary.total_sessions == 0
        assert summary.acceptance_rate == 0.0

    def test_summary_with_sessions(self):
        s1 = AssistSession(customer_id=CUSTOMER_ID)
        s2 = AssistSession(customer_id=CUSTOMER_ID)
        assist_svc.create_session(s1)
        assist_svc.create_session(s2)
        assist_svc.add_transcript_entry(s1.id, "caller", "I need help")
        assist_svc.add_transcript_entry(s2.id, "caller", "I need a refund")
        summary = assist_svc.get_assist_summary(CUSTOMER_ID)
        assert summary.total_sessions == 2
        assert summary.active_sessions == 2
        assert summary.total_suggestions > 0


# ──────────────────────────────────────────────────────────────────
# Compliance Rule model tests
# ──────────────────────────────────────────────────────────────────

class TestComplianceModels:
    def test_compliance_rule_defaults(self):
        r = ComplianceRule(customer_id=CUSTOMER_ID, name="Test")
        assert r.rule_type == ComplianceRuleType.PII_REDACTION
        assert r.enabled is True
        assert r.severity == "warning"

    def test_compliance_violation_defaults(self):
        v = ComplianceViolation(customer_id=CUSTOMER_ID)
        assert v.resolved is False
        assert v.severity == "warning"

    def test_audit_log_entry_defaults(self):
        e = AuditLogEntry(customer_id=CUSTOMER_ID, action=AuditAction.LOGIN)
        assert e.action == AuditAction.LOGIN
        assert e.metadata == {}

    def test_all_rule_types(self):
        for rt in ComplianceRuleType:
            r = ComplianceRule(customer_id=CUSTOMER_ID, rule_type=rt)
            assert r.rule_type == rt

    def test_all_audit_actions(self):
        for aa in AuditAction:
            e = AuditLogEntry(customer_id=CUSTOMER_ID, action=aa)
            assert e.action == aa


# ──────────────────────────────────────────────────────────────────
# Compliance Rule CRUD tests
# ──────────────────────────────────────────────────────────────────

class TestComplianceRuleCRUD:
    def test_create_rule(self):
        r = ComplianceRule(customer_id=CUSTOMER_ID, name="PII Rule")
        result = comp_svc.create_rule(r)
        assert result.name == "PII Rule"
        assert comp_svc.get_rule(r.id) is not None

    def test_list_rules(self):
        comp_svc.create_rule(ComplianceRule(customer_id=CUSTOMER_ID, name="R1"))
        comp_svc.create_rule(ComplianceRule(customer_id=CUSTOMER_ID, name="R2"))
        comp_svc.create_rule(ComplianceRule(customer_id="other", name="R3"))
        assert len(comp_svc.list_rules(CUSTOMER_ID)) == 2

    def test_update_rule(self):
        r = ComplianceRule(customer_id=CUSTOMER_ID, name="Old Name")
        comp_svc.create_rule(r)
        updated = comp_svc.update_rule(r.id, {"name": "New Name", "enabled": False})
        assert updated.name == "New Name"
        assert updated.enabled is False

    def test_delete_rule(self):
        r = ComplianceRule(customer_id=CUSTOMER_ID, name="To Delete")
        comp_svc.create_rule(r)
        assert comp_svc.delete_rule(r.id) is True
        assert comp_svc.get_rule(r.id) is None

    def test_create_defaults(self):
        rules = comp_svc.create_default_rules(CUSTOMER_ID)
        assert len(rules) == 4
        types = [r.rule_type for r in rules]
        assert ComplianceRuleType.PII_REDACTION in types
        assert ComplianceRuleType.DISCLOSURE_REQUIRED in types
        assert ComplianceRuleType.FORBIDDEN_PHRASES in types
        assert ComplianceRuleType.PCI_DSS in types


# ──────────────────────────────────────────────────────────────────
# PII Redaction tests
# ──────────────────────────────────────────────────────────────────

class TestPIIRedaction:
    def test_redact_ssn(self):
        result = comp_svc.redact_text("My SSN is 123-45-6789")
        assert "***-**-****" in result
        assert "123-45-6789" not in result

    def test_redact_credit_card(self):
        result = comp_svc.redact_text("My card is 4111 1111 1111 1111")
        assert "****-****-****-****" in result

    def test_redact_multiple(self):
        result = comp_svc.redact_text("SSN: 123-45-6789 and card: 4111-1111-1111-1111")
        assert "***-**-****" in result
        assert "****-****-****-****" in result

    def test_no_redaction_needed(self):
        text = "Hello, how are you?"
        result = comp_svc.redact_text(text)
        assert result == text


# ──────────────────────────────────────────────────────────────────
# Transcript scanning tests
# ──────────────────────────────────────────────────────────────────

class TestTranscriptScanning:
    def test_scan_pii(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "caller", "content": "My SSN is 123-45-6789"},
            {"role": "agent", "content": "Got it, let me look that up"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_1", transcript)
        pii_violations = [v for v in violations if v.rule_type == ComplianceRuleType.PII_REDACTION]
        assert len(pii_violations) >= 1

    def test_scan_forbidden_phrases(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "agent", "content": "I guarantee this will work perfectly"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_2", transcript)
        forbidden = [v for v in violations if v.rule_type == ComplianceRuleType.FORBIDDEN_PHRASES]
        assert len(forbidden) >= 1
        assert "I guarantee" in forbidden[0].description

    def test_scan_missing_disclosure(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "agent", "content": "Hello, how can I help you?"},
            {"role": "caller", "content": "I need help"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_3", transcript)
        disclosure = [v for v in violations if v.rule_type == ComplianceRuleType.DISCLOSURE_REQUIRED]
        assert len(disclosure) >= 1
        assert "disclosure missing" in disclosure[0].description.lower()

    def test_scan_disclosure_present(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "agent", "content": "This call may be recorded and this call is being recorded for quality purposes"},
            {"role": "caller", "content": "Okay"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_4", transcript)
        disclosure = [v for v in violations if v.rule_type == ComplianceRuleType.DISCLOSURE_REQUIRED]
        assert len(disclosure) == 0

    def test_scan_pci_dss(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "caller", "content": "My card number is 4111 1111 1111 1111"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_5", transcript)
        pci = [v for v in violations if v.rule_type == ComplianceRuleType.PCI_DSS]
        assert len(pci) >= 1
        assert "PCI DSS" in pci[0].description

    def test_scan_clean_transcript(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        transcript = [
            {"role": "agent", "content": "This call is being recorded. How can I help?"},
            {"role": "caller", "content": "I'd like to check my order status"},
            {"role": "agent", "content": "Let me look that up for you"},
        ]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_6", transcript)
        # Should only have violations if any — this transcript is clean
        forbidden = [v for v in violations if v.rule_type == ComplianceRuleType.FORBIDDEN_PHRASES]
        assert len(forbidden) == 0

    def test_scan_no_rules(self):
        # No rules = no violations
        transcript = [{"role": "caller", "content": "My SSN is 123-45-6789"}]
        violations = comp_svc.scan_transcript(CUSTOMER_ID, "call_7", transcript)
        assert len(violations) == 0


# ──────────────────────────────────────────────────────────────────
# Violation CRUD tests
# ──────────────────────────────────────────────────────────────────

class TestViolationCRUD:
    def test_create_violation(self):
        v = ComplianceViolation(
            customer_id=CUSTOMER_ID,
            call_id="call_1",
            rule_name="PII Rule",
            description="SSN detected",
        )
        result = comp_svc.create_violation(v)
        assert result.description == "SSN detected"
        assert comp_svc.get_violation(v.id) is not None

    def test_list_violations(self):
        comp_svc.create_violation(ComplianceViolation(customer_id=CUSTOMER_ID, description="V1"))
        comp_svc.create_violation(ComplianceViolation(customer_id=CUSTOMER_ID, description="V2"))
        comp_svc.create_violation(ComplianceViolation(customer_id="other", description="V3"))
        assert len(comp_svc.list_violations(CUSTOMER_ID)) == 2

    def test_list_unresolved_only(self):
        comp_svc.create_violation(ComplianceViolation(customer_id=CUSTOMER_ID, description="V1"))
        v2 = ComplianceViolation(customer_id=CUSTOMER_ID, description="V2", resolved=True)
        comp_svc.create_violation(v2)
        unresolved = comp_svc.list_violations(CUSTOMER_ID, unresolved_only=True)
        assert len(unresolved) == 1

    def test_resolve_violation(self):
        v = ComplianceViolation(customer_id=CUSTOMER_ID, description="To resolve")
        comp_svc.create_violation(v)
        resolved = comp_svc.resolve_violation(v.id, "admin@company.com")
        assert resolved.resolved is True
        assert resolved.resolved_by == "admin@company.com"


# ──────────────────────────────────────────────────────────────────
# Audit Log tests
# ──────────────────────────────────────────────────────────────────

class TestAuditLog:
    def test_log_action(self):
        entry = comp_svc.log_action(
            customer_id=CUSTOMER_ID,
            user_email="admin@test.com",
            action=AuditAction.AGENT_CREATE,
            resource_type="agent",
            resource_id="agent_123",
            description="Created new agent",
        )
        assert entry.action == AuditAction.AGENT_CREATE
        assert entry.user_email == "admin@test.com"

    def test_get_audit_log(self):
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.LOGIN, description="Logged in")
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.AGENT_CREATE, description="Made agent")
        comp_svc.log_action("other", "x@y.com", AuditAction.LOGIN)
        entries = comp_svc.get_audit_log(CUSTOMER_ID)
        assert len(entries) == 2

    def test_filter_by_action(self):
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.LOGIN)
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.AGENT_CREATE)
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.LOGIN)
        entries = comp_svc.get_audit_log(CUSTOMER_ID, action="login")
        assert len(entries) == 2

    def test_audit_log_limit(self):
        for i in range(20):
            comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.LOGIN, description=f"Login {i}")
        entries = comp_svc.get_audit_log(CUSTOMER_ID, limit=5)
        assert len(entries) == 5


# ──────────────────────────────────────────────────────────────────
# Compliance Summary tests
# ──────────────────────────────────────────────────────────────────

class TestComplianceSummary:
    def test_empty_summary(self):
        summary = comp_svc.get_compliance_summary(CUSTOMER_ID)
        assert summary.total_rules == 0
        assert summary.total_violations == 0

    def test_summary_with_data(self):
        comp_svc.create_default_rules(CUSTOMER_ID)
        comp_svc.create_violation(ComplianceViolation(
            customer_id=CUSTOMER_ID,
            rule_type=ComplianceRuleType.PII_REDACTION,
            severity="critical",
        ))
        comp_svc.create_violation(ComplianceViolation(
            customer_id=CUSTOMER_ID,
            rule_type=ComplianceRuleType.FORBIDDEN_PHRASES,
            severity="warning",
        ))
        comp_svc.log_action(CUSTOMER_ID, "a@b.com", AuditAction.LOGIN)

        summary = comp_svc.get_compliance_summary(CUSTOMER_ID)
        assert summary.total_rules == 4
        assert summary.enabled_rules == 4
        assert summary.total_violations == 2
        assert summary.unresolved_violations == 2
        assert summary.violations_by_severity.get("critical") == 1
        assert summary.violations_by_severity.get("warning") == 1
        assert summary.audit_log_count == 1
