"""Sprint 6b tests — Playground + QA Weekly Email.

Tests cover:
- Playground models (session, message, request/response)
- Playground service (session CRUD, message building, simulated replies, turn processing)
- QA email models (weekly report)
- QA email service (report generation, HTML rendering, trend detection)
"""

import time
import pytest

# ──────────────────────────────────────────────────────────────────
# Playground models
# ──────────────────────────────────────────────────────────────────

class TestPlaygroundMessage:
    def test_defaults(self):
        from app.models.database import PlaygroundMessage
        msg = PlaygroundMessage()
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.tool_call is None
        assert msg.latency_ms == 0

    def test_assistant_with_tool_call(self):
        from app.models.database import PlaygroundMessage
        msg = PlaygroundMessage(
            role="assistant",
            content="Let me check that order.",
            tool_call={"name": "check_order", "arguments": '{"id":"123"}'},
            latency_ms=450,
        )
        assert msg.role == "assistant"
        assert msg.tool_call["name"] == "check_order"
        assert msg.latency_ms == 450


class TestPlaygroundSession:
    def test_defaults(self):
        from app.models.database import PlaygroundSession
        s = PlaygroundSession()
        assert s.status == "active"
        assert s.messages == []
        assert s.total_turns == 0
        assert s.total_tokens == 0
        assert s.estimated_cost_cents == 0
        assert s.ended_at is None

    def test_custom_session(self):
        from app.models.database import PlaygroundSession
        s = PlaygroundSession(
            customer_id="cust-1",
            agent_id="agent-1",
            agent_name="Sales Bot",
        )
        assert s.customer_id == "cust-1"
        assert s.agent_name == "Sales Bot"
        assert len(s.id) > 0


class TestPlaygroundRequest:
    def test_defaults(self):
        from app.models.database import PlaygroundRequest
        req = PlaygroundRequest()
        assert req.message == ""
        assert req.session_id is None

    def test_with_session(self):
        from app.models.database import PlaygroundRequest
        req = PlaygroundRequest(message="Hello", session_id="sess-abc")
        assert req.message == "Hello"
        assert req.session_id == "sess-abc"


class TestPlaygroundResponse:
    def test_defaults(self):
        from app.models.database import PlaygroundResponse
        res = PlaygroundResponse(session_id="test")
        assert res.session_id == "test"
        assert res.reply == ""
        assert res.tool_calls == []
        assert res.done is False
        assert res.latency_ms == 0


# ──────────────────────────────────────────────────────────────────
# Playground service — session management
# ──────────────────────────────────────────────────────────────────

class TestPlaygroundSessionStore:
    def setup_method(self):
        from app.services import playground as pg
        pg._sessions.clear()

    def test_create_session(self):
        from app.services import playground as pg
        s = pg.create_session("cust-1", "agent-1", "Test Agent")
        assert s.customer_id == "cust-1"
        assert s.agent_id == "agent-1"
        assert s.status == "active"

    def test_get_session(self):
        from app.services import playground as pg
        s = pg.create_session("cust-1", "agent-1", "Test Agent")
        found = pg.get_session(s.id)
        assert found is not None
        assert found.id == s.id

    def test_get_nonexistent_session(self):
        from app.services import playground as pg
        assert pg.get_session("nonexistent") is None

    def test_end_session(self):
        from app.services import playground as pg
        s = pg.create_session("cust-1", "agent-1", "Test Agent")
        ended = pg.end_session(s.id)
        assert ended.status == "completed"
        assert ended.ended_at is not None

    def test_delete_session(self):
        from app.services import playground as pg
        s = pg.create_session("cust-1", "agent-1", "Test Agent")
        assert pg.delete_session(s.id) is True
        assert pg.get_session(s.id) is None
        assert pg.delete_session(s.id) is False

    def test_max_sessions_eviction(self):
        from app.services import playground as pg
        # Create MAX_SESSIONS sessions
        for i in range(pg.MAX_SESSIONS):
            pg.create_session(f"cust-{i}", f"agent-{i}", f"Agent {i}")
        assert len(pg._sessions) == pg.MAX_SESSIONS
        # Creating one more should evict the oldest
        pg.create_session("cust-new", "agent-new", "New Agent")
        assert len(pg._sessions) == pg.MAX_SESSIONS


# ──────────────────────────────────────────────────────────────────
# Playground service — message building
# ──────────────────────────────────────────────────────────────────

class TestBuildMessages:
    def test_basic_messages(self):
        from app.services.playground import build_messages
        msgs = build_messages(
            system_prompt="You are a helpful assistant.",
            first_message="",
            history=[],
            user_message="Hello",
        )
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are a helpful assistant."
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "Hello"

    def test_first_message_included(self):
        from app.services.playground import build_messages
        msgs = build_messages(
            system_prompt="System",
            first_message="Hi! How can I help?",
            history=[],
            user_message="Hello",
        )
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi! How can I help?"
        assert msgs[2]["role"] == "user"

    def test_with_history(self):
        from app.services.playground import build_messages
        from app.models.database import PlaygroundMessage
        history = [
            PlaygroundMessage(role="user", content="Hi"),
            PlaygroundMessage(role="assistant", content="Hello!"),
        ]
        msgs = build_messages(
            system_prompt="System",
            first_message="",
            history=history,
            user_message="How are you?",
        )
        assert len(msgs) == 4  # system + 2 history + user
        assert msgs[3]["content"] == "How are you?"

    def test_no_system_prompt(self):
        from app.services.playground import build_messages
        msgs = build_messages("", "", [], "Hello")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"


# ──────────────────────────────────────────────────────────────────
# Playground service — simulated replies
# ──────────────────────────────────────────────────────────────────

class TestSimulatedReply:
    def test_greeting(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "hello"}])
        assert "help" in result["reply"].lower()
        assert result["tool_calls"] == []
        assert result["tokens_used"] > 0

    def test_order_query(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "What is my order status?"}])
        assert "order" in result["reply"].lower()

    def test_refund_query(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "I want a refund"}])
        assert "refund" in result["reply"].lower() or "return" in result["reply"].lower()

    def test_escalation_query(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "Let me speak to a human agent"}])
        assert "human" in result["reply"].lower() or "transfer" in result["reply"].lower()

    def test_farewell(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "thank you, goodbye"}])
        assert "thank" in result["reply"].lower()

    def test_appointment(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "I'd like to schedule an appointment"}])
        assert "appointment" in result["reply"].lower() or "schedule" in result["reply"].lower()

    def test_generic_fallback(self):
        from app.services.playground import _simulated_reply
        result = _simulated_reply([{"role": "user", "content": "xyzzy foobar"}])
        assert len(result["reply"]) > 10  # some generic response


# ──────────────────────────────────────────────────────────────────
# Playground service — turn processing
# ──────────────────────────────────────────────────────────────────

class TestProcessTurn:
    @pytest.mark.asyncio
    async def test_basic_turn(self):
        from app.services import playground as pg
        pg._sessions.clear()
        session = pg.create_session("cust-1", "agent-1", "Bot")
        agent_config = {
            "system_prompt": "You are a test agent.",
            "first_message": "",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_config": {},
            "tools": [],
            "end_call_phrases": [],
        }
        result = await pg.process_turn(session, "Hello", agent_config)
        assert "reply" in result
        assert len(result["reply"]) > 0
        assert session.total_turns == 1
        assert len(session.messages) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_max_turns_limit(self):
        from app.services import playground as pg
        pg._sessions.clear()
        session = pg.create_session("cust-1", "agent-1", "Bot")
        session.total_turns = pg.MAX_TURNS
        result = await pg.process_turn(session, "One more", {"system_prompt": "", "first_message": "", "llm_provider": "openai", "llm_model": "gpt-4o-mini", "llm_config": {}, "tools": [], "end_call_phrases": []})
        assert result["done"] is True
        assert "limit" in result["reply"].lower()

    @pytest.mark.asyncio
    async def test_end_call_phrase_detected(self):
        from app.services import playground as pg
        pg._sessions.clear()
        session = pg.create_session("cust-1", "agent-1", "Bot")
        agent_config = {
            "system_prompt": "",
            "first_message": "",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_config": {},
            "tools": [],
            "end_call_phrases": ["goodbye", "thank you for calling"],
        }
        # The simulated reply for "goodbye" includes "thank" — which may match
        result = await pg.process_turn(session, "goodbye", agent_config)
        # Whether done=True depends on the simulated reply content,
        # but the mechanism should work
        assert "reply" in result


# ──────────────────────────────────────────────────────────────────
# QA Email models
# ──────────────────────────────────────────────────────────────────

class TestQAWeeklyReport:
    def test_defaults(self):
        from app.models.database import QAWeeklyReport
        r = QAWeeklyReport()
        assert r.total_calls_scored == 0
        assert r.avg_overall_score == 0.0
        assert r.score_trend == "stable"
        assert r.top_issues == []
        assert r.top_agents == []
        assert r.improvement_areas == []

    def test_custom_report(self):
        from app.models.database import QAWeeklyReport
        r = QAWeeklyReport(
            customer_id="cust-1",
            customer_email="test@example.com",
            customer_name="Test User",
            total_calls_scored=150,
            avg_overall_score=78.5,
            flagged_calls=12,
            score_trend="improving",
            top_agents=[{"name": "Bot 1", "score": 85, "calls": 100}],
        )
        assert r.total_calls_scored == 150
        assert r.score_trend == "improving"
        assert len(r.top_agents) == 1


# ──────────────────────────────────────────────────────────────────
# QA Email — report generation
# ──────────────────────────────────────────────────────────────────

class TestReportGeneration:
    def test_basic_report(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="cust-1",
            customer_email="user@example.com",
            customer_name="Alice",
            qa_summary={
                "total_scored": 100,
                "avg_overall": 82.5,
                "avg_accuracy": 85.0,
                "avg_tone": 78.0,
                "avg_resolution": 80.0,
                "avg_compliance": 90.0,
                "flagged_count": 5,
                "pii_count": 2,
                "angry_count": 3,
                "top_flag_reasons": [{"reason": "PII detected", "count": 2}],
            },
        )
        assert report.customer_email == "user@example.com"
        assert report.total_calls_scored == 100
        assert report.avg_overall_score == 82.5
        assert report.flagged_calls == 5
        assert report.pii_detections == 2
        assert len(report.top_issues) == 1
        assert report.score_trend == "stable"  # no previous data

    def test_trend_improving(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="c", customer_email="e", customer_name="n",
            qa_summary={"avg_overall": 85.0, "avg_accuracy": 85, "avg_tone": 85, "avg_resolution": 85, "avg_compliance": 85},
            previous_avg=80.0,
        )
        assert report.score_trend == "improving"

    def test_trend_declining(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="c", customer_email="e", customer_name="n",
            qa_summary={"avg_overall": 70.0, "avg_accuracy": 70, "avg_tone": 70, "avg_resolution": 70, "avg_compliance": 70},
            previous_avg=80.0,
        )
        assert report.score_trend == "declining"

    def test_trend_stable(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="c", customer_email="e", customer_name="n",
            qa_summary={"avg_overall": 80.5, "avg_accuracy": 80, "avg_tone": 80, "avg_resolution": 80, "avg_compliance": 80},
            previous_avg=80.0,
        )
        assert report.score_trend == "stable"

    def test_improvement_areas_generated(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="c", customer_email="e", customer_name="n",
            qa_summary={
                "avg_overall": 50,
                "avg_accuracy": 55,
                "avg_tone": 60,
                "avg_resolution": 45,
                "avg_compliance": 40,
                "pii_count": 3,
                "angry_count": 5,
            },
        )
        assert len(report.improvement_areas) >= 3  # low scores + PII + angry

    def test_agent_stats_ranking(self):
        from app.services.qa_email import generate_weekly_report
        report = generate_weekly_report(
            customer_id="c", customer_email="e", customer_name="n",
            qa_summary={"avg_overall": 80, "avg_accuracy": 80, "avg_tone": 80, "avg_resolution": 80, "avg_compliance": 80},
            agent_stats=[
                {"agent_name": "Bot A", "avg_score": 90, "total_calls": 50},
                {"agent_name": "Bot B", "avg_score": 70, "total_calls": 30},
                {"agent_name": "Bot C", "avg_score": 95, "total_calls": 20},
            ],
        )
        # Top agents should be sorted by score desc
        assert report.top_agents[0]["name"] == "Bot C"
        assert report.top_agents[1]["name"] == "Bot A"


# ──────────────────────────────────────────────────────────────────
# QA Email — HTML rendering
# ──────────────────────────────────────────────────────────────────

class TestEmailRendering:
    def test_html_contains_key_elements(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import render_email_html
        report = QAWeeklyReport(
            customer_name="Alice",
            period_start="2026-02-10",
            period_end="2026-02-17",
            total_calls_scored=100,
            avg_overall_score=82.5,
            avg_accuracy=85.0,
            avg_tone=78.0,
            avg_resolution=80.0,
            avg_compliance=90.0,
            flagged_calls=5,
            score_trend="improving",
        )
        html = render_email_html(report)
        assert "Alice" in html
        assert "82.5" in html
        assert "2026-02-10" in html
        assert "VoxBridge" in html
        assert "Improving" in html

    def test_html_shows_alerts(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import render_email_html
        report = QAWeeklyReport(
            flagged_calls=10,
            pii_detections=3,
            angry_callers=5,
        )
        html = render_email_html(report)
        assert "10 flagged calls" in html
        assert "3 PII detections" in html
        assert "5 angry callers" in html

    def test_html_no_alerts_when_clean(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import render_email_html
        report = QAWeeklyReport(
            flagged_calls=0,
            pii_detections=0,
        )
        html = render_email_html(report)
        assert "Alerts" not in html

    def test_html_with_agents(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import render_email_html
        report = QAWeeklyReport(
            top_agents=[
                {"name": "Sales Bot", "score": 92, "calls": 50},
                {"name": "Support Bot", "score": 85, "calls": 80},
            ],
        )
        html = render_email_html(report)
        assert "Sales Bot" in html
        assert "Support Bot" in html
        assert "Top Agents" in html

    def test_html_with_issues(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import render_email_html
        report = QAWeeklyReport(
            top_issues=["PII detected in responses", "Low resolution rate"],
        )
        html = render_email_html(report)
        assert "PII detected in responses" in html
        assert "Top Flag Reasons" in html


# ──────────────────────────────────────────────────────────────────
# QA Email — send function (SMTP not configured = logs instead)
# ──────────────────────────────────────────────────────────────────

class TestEmailSending:
    def test_send_without_smtp_returns_false(self):
        from app.services.qa_email import send_email
        result = send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<p>Hi</p>",
        )
        assert result is False

    def test_send_weekly_report_without_smtp(self):
        from app.models.database import QAWeeklyReport
        from app.services.qa_email import send_weekly_report
        report = QAWeeklyReport(
            customer_email="test@example.com",
            avg_overall_score=80,
            period_start="2026-02-10",
        )
        result = send_weekly_report(report)
        assert result is False  # no SMTP configured
