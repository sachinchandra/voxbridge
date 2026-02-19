"""Tests for Sprint 6: Analytics, QA, Polish.

Tests cover:
- QA score models (CallQAScore, QAScoreResponse, QASummary)
- Analytics detail model
- QA scorer service (scoring, PII detection, anger detection)
- Template-based scoring logic
"""

import pytest
from datetime import datetime, timezone

from app.models.database import (
    CallQAScore,
    QAScoreResponse,
    QASummary,
    AnalyticsDetail,
    Call,
    CallDirection,
    CallStatus,
)
from app.services.qa_scorer import (
    score_call,
    _detect_pii,
    _detect_anger,
    _score_accuracy,
    _score_tone,
    _score_resolution,
    _score_compliance,
    _generate_summary,
    _generate_suggestions,
    _empty_score,
)


# ──────────────────────────────────────────────────────────────────
# QA Score Model Tests
# ──────────────────────────────────────────────────────────────────

class TestCallQAScore:
    def test_defaults(self):
        score = CallQAScore(call_id="call-1", customer_id="cust-1", agent_id="agent-1")
        assert score.call_id == "call-1"
        assert score.accuracy_score == 0
        assert score.tone_score == 0
        assert score.resolution_score == 0
        assert score.compliance_score == 0
        assert score.overall_score == 0
        assert score.pii_detected is False
        assert score.angry_caller is False
        assert score.flagged is False
        assert score.flag_reasons == []
        assert score.summary == ""
        assert score.improvement_suggestions == []

    def test_custom_scores(self):
        score = CallQAScore(
            call_id="call-2",
            customer_id="cust-1",
            agent_id="agent-1",
            accuracy_score=85,
            tone_score=90,
            resolution_score=80,
            compliance_score=95,
            overall_score=87,
            pii_detected=True,
            angry_caller=True,
            flagged=True,
            flag_reasons=["PII detected", "Angry caller"],
            summary="Call had issues.",
            improvement_suggestions=["Add guardrails"],
        )
        assert score.overall_score == 87
        assert score.pii_detected is True
        assert len(score.flag_reasons) == 2


class TestQAScoreResponse:
    def test_all_fields(self):
        now = datetime.now(timezone.utc)
        resp = QAScoreResponse(
            id="qa-1",
            call_id="call-1",
            agent_id="agent-1",
            accuracy_score=80,
            tone_score=75,
            resolution_score=90,
            compliance_score=85,
            overall_score=82,
            pii_detected=False,
            angry_caller=False,
            flagged=False,
            flag_reasons=[],
            summary="Good call.",
            improvement_suggestions=[],
            created_at=now,
        )
        assert resp.overall_score == 82
        assert resp.flagged is False


class TestQASummary:
    def test_defaults(self):
        summary = QASummary()
        assert summary.total_scored == 0
        assert summary.avg_overall == 0.0
        assert summary.flagged_count == 0
        assert summary.score_distribution == []

    def test_with_data(self):
        summary = QASummary(
            total_scored=100,
            avg_overall=78.5,
            avg_accuracy=80.0,
            avg_tone=75.0,
            avg_resolution=82.0,
            avg_compliance=77.0,
            flagged_count=5,
            pii_count=2,
            angry_count=3,
            score_distribution=[{"range": "81-100", "count": 60}],
            top_flag_reasons=[{"reason": "Low score", "count": 3}],
        )
        assert summary.total_scored == 100
        assert summary.avg_overall == 78.5
        assert len(summary.score_distribution) == 1


class TestAnalyticsDetail:
    def test_defaults(self):
        ad = AnalyticsDetail()
        assert ad.total_calls == 0
        assert ad.sentiment_positive == 0
        assert ad.calls_by_hour == []
        assert ad.agent_rankings == []

    def test_with_data(self):
        ad = AnalyticsDetail(
            total_calls=500,
            ai_handled=400,
            escalated=100,
            containment_rate=80.0,
            avg_duration_seconds=180.5,
            total_cost_cents=3000,
            total_cost_dollars=30.0,
            sentiment_positive=250,
            sentiment_neutral=150,
            sentiment_negative=100,
            resolved=350,
            abandoned=50,
        )
        assert ad.containment_rate == 80.0
        assert ad.sentiment_positive == 250
        assert ad.resolved == 350


# ──────────────────────────────────────────────────────────────────
# PII Detection Tests
# ──────────────────────────────────────────────────────────────────

class TestPIIDetection:
    def test_no_pii(self):
        detected, types = _detect_pii("hello how can I help you today?")
        assert detected is False
        assert types == []

    def test_ssn_detection(self):
        detected, types = _detect_pii("my social security number is 123-45-6789")
        assert detected is True
        assert "SSN" in types

    def test_credit_card_16_digits(self):
        detected, types = _detect_pii("my card number is 4111111111111111")
        assert detected is True
        assert "Credit Card" in types

    def test_credit_card_formatted(self):
        detected, types = _detect_pii("card: 4111 1111 1111 1111")
        assert detected is True
        assert "Credit Card" in types

    def test_no_false_positives_on_short_numbers(self):
        detected, types = _detect_pii("order number 12345")
        assert detected is False


# ──────────────────────────────────────────────────────────────────
# Anger Detection Tests
# ──────────────────────────────────────────────────────────────────

class TestAngerDetection:
    def test_no_anger(self):
        assert _detect_anger("i need help with my order please") is False

    def test_angry_keywords(self):
        assert _detect_anger("this is ridiculous and unacceptable") is True

    def test_frustrated_caller(self):
        assert _detect_anger("i am so frustrated and fed up with this") is True

    def test_single_keyword_not_enough(self):
        # Need 2+ indicators
        assert _detect_anger("this is terrible") is False

    def test_lawsuit_threat(self):
        assert _detect_anger("this is ridiculous i will sue you") is True


# ──────────────────────────────────────────────────────────────────
# Scoring Function Tests
# ──────────────────────────────────────────────────────────────────

class TestScoreAccuracy:
    def test_resolved_call(self):
        transcript = [
            {"role": "assistant", "content": "Hello, how can I help?"},
            {"role": "user", "content": "What's my order status?"},
            {"role": "assistant", "content": "Your order is shipped."},
            {"role": "user", "content": "Thanks!"},
        ]
        score = _score_accuracy(transcript, "resolved", False)
        assert score >= 80  # Base + resolution bonus

    def test_abandoned_call(self):
        transcript = [
            {"role": "assistant", "content": "Hello?"},
        ]
        score = _score_accuracy(transcript, "abandoned", False)
        assert score <= 50  # Penalties for short + abandoned

    def test_escalated_call(self):
        transcript = [
            {"role": "assistant", "content": "Hello."},
            {"role": "user", "content": "I want a manager."},
            {"role": "assistant", "content": "Let me transfer you."},
        ]
        score = _score_accuracy(transcript, "escalated", True)
        assert score >= 50


class TestScoreTone:
    def test_polite_agent(self):
        score = _score_tone("thank you for calling, i am happy to help you today. certainly, of course!", None)
        assert score >= 80

    def test_negative_tone(self):
        score = _score_tone("unfortunately we cannot help. it is impossible. unable to process.", None)
        assert score < 75

    def test_positive_sentiment_boost(self):
        score_neutral = _score_tone("hello there", None)
        score_positive = _score_tone("hello there", 0.8)
        assert score_positive > score_neutral


class TestScoreResolution:
    def test_resolved(self):
        score = _score_resolution("thank you that was very helpful", "resolved", False)
        assert score >= 85

    def test_abandoned(self):
        score = _score_resolution("forget it this is useless", "abandoned", False)
        assert score <= 30

    def test_escalated(self):
        score = _score_resolution("i need to speak with someone", "escalated", True)
        assert score <= 50


class TestScoreCompliance:
    def test_no_prompt(self):
        score = _score_compliance("i can help you", "")
        assert score == 80  # Default

    def test_concise_agent(self):
        score = _score_compliance("short answer", "Be concise and brief.")
        assert score >= 80

    def test_verbose_agent_with_concise_prompt(self):
        long_text = "a " * 1500  # Very long response
        score = _score_compliance(long_text, "Be concise and brief.")
        assert score < 80


# ──────────────────────────────────────────────────────────────────
# Full Score Call Tests
# ──────────────────────────────────────────────────────────────────

class TestScoreCall:
    def test_empty_transcript(self):
        result = score_call([], "resolved", False, None, "")
        assert result["overall_score"] == 0
        assert result["flagged"] is True
        assert "No transcript" in result["flag_reasons"][0]

    def test_good_call(self):
        transcript = [
            {"role": "assistant", "content": "Thank you for calling! How can I help you today?"},
            {"role": "user", "content": "I'd like to check on my order."},
            {"role": "assistant", "content": "Of course! Let me look that up for you. Your order #1234 shipped yesterday."},
            {"role": "user", "content": "That's great, thank you so much!"},
            {"role": "assistant", "content": "Happy to help! Is there anything else?"},
            {"role": "user", "content": "No, that's all. Thanks!"},
        ]
        result = score_call(transcript, "resolved", False, 0.8, "Be helpful and friendly.")
        assert result["overall_score"] >= 60
        assert result["pii_detected"] is False
        assert result["angry_caller"] is False

    def test_flagged_call_with_pii(self):
        transcript = [
            {"role": "user", "content": "My SSN is 123-45-6789"},
            {"role": "assistant", "content": "I see your SSN 123-45-6789, let me check."},
        ]
        result = score_call(transcript, "resolved", False, None, "")
        assert result["pii_detected"] is True
        assert result["flagged"] is True
        assert any("PII" in r for r in result["flag_reasons"])

    def test_angry_caller_flagged(self):
        transcript = [
            {"role": "user", "content": "This is ridiculous and unacceptable! I want to speak to a supervisor!"},
            {"role": "assistant", "content": "I understand your frustration."},
        ]
        result = score_call(transcript, "escalated", True, -0.8, "")
        assert result["angry_caller"] is True
        assert result["flagged"] is True

    def test_escalated_is_flagged(self):
        transcript = [
            {"role": "assistant", "content": "Hello."},
            {"role": "user", "content": "Transfer me."},
            {"role": "assistant", "content": "Transferring now."},
        ]
        result = score_call(transcript, "escalated", True, None, "")
        assert result["flagged"] is True
        assert any("escalated" in r.lower() for r in result["flag_reasons"])


# ──────────────────────────────────────────────────────────────────
# Summary and Suggestions Tests
# ──────────────────────────────────────────────────────────────────

class TestSummaryGeneration:
    def test_high_quality(self):
        transcript = [{"role": "assistant", "content": "Hi"}, {"role": "user", "content": "Hello"}]
        summary = _generate_summary(transcript, "resolved", False, 85, [])
        assert "High quality" in summary
        assert "resolved" in summary.lower()

    def test_flagged_summary(self):
        transcript = [{"role": "assistant", "content": "Hi"}]
        summary = _generate_summary(transcript, "abandoned", False, 30, ["Low score", "Abandoned"])
        assert "Flagged" in summary


class TestSuggestionGeneration:
    def test_no_suggestions_for_good_scores(self):
        suggestions = _generate_suggestions(80, 80, 80, 80, False, False)
        assert len(suggestions) == 0

    def test_accuracy_suggestion(self):
        suggestions = _generate_suggestions(40, 80, 80, 80, False, False)
        assert len(suggestions) == 1
        assert "accuracy" in suggestions[0].lower()

    def test_pii_suggestion(self):
        suggestions = _generate_suggestions(80, 80, 80, 80, True, False)
        assert any("PII" in s for s in suggestions)

    def test_multiple_suggestions(self):
        suggestions = _generate_suggestions(30, 30, 30, 30, True, True)
        assert len(suggestions) >= 4


class TestEmptyScore:
    def test_empty_score_is_flagged(self):
        result = _empty_score()
        assert result["overall_score"] == 0
        assert result["flagged"] is True
        assert "No transcript" in result["flag_reasons"][0]
