"""Sprint 10 tests — Workforce Management (Hybrid AI + Human).

Tests cover:
  - Human agent models + enums
  - Human agent CRUD + status management
  - Agent utilization calculation
  - Escalation queue: enqueue, assign, auto-assign, resolve, abandon
  - Queue status summary
  - Volume forecasting (default + historical)
  - Metrics calculation (containment, cost savings)
  - Containment trend
  - ROI calculator
  - Dashboard aggregation
"""

import pytest
from datetime import datetime, timezone

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
from app.services import workforce as wf_svc


CUSTOMER_ID = "cust_test_sprint10"


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear all in-memory stores before each test."""
    wf_svc._human_agents.clear()
    wf_svc._escalations.clear()
    wf_svc._forecasts.clear()
    wf_svc._metrics.clear()
    yield


# ── Model Tests ───────────────────────────────────────────────────


class TestModels:
    def test_human_agent_defaults(self):
        agent = HumanAgent(customer_id=CUSTOMER_ID, name="Alice")
        assert agent.id.startswith("hagent_")
        assert agent.status == HumanAgentStatus.OFFLINE
        assert agent.skills == []
        assert agent.current_call_id is None
        assert agent.calls_handled_today == 0

    def test_human_agent_status_enum(self):
        assert HumanAgentStatus.AVAILABLE == "available"
        assert HumanAgentStatus.BUSY == "busy"
        assert HumanAgentStatus.OFFLINE == "offline"
        assert HumanAgentStatus.BREAK == "break"

    def test_escalation_queue_defaults(self):
        esc = EscalationQueue(customer_id=CUSTOMER_ID, call_id="call_1")
        assert esc.id.startswith("esc_")
        assert esc.priority == EscalationPriority.NORMAL
        assert esc.status == EscalationStatus.WAITING
        assert esc.human_agent_id is None
        assert esc.assigned_at is None

    def test_escalation_priority_enum(self):
        assert EscalationPriority.LOW == "low"
        assert EscalationPriority.URGENT == "urgent"

    def test_escalation_status_enum(self):
        assert EscalationStatus.WAITING == "waiting"
        assert EscalationStatus.ASSIGNED == "assigned"
        assert EscalationStatus.RESOLVED == "resolved"
        assert EscalationStatus.ABANDONED == "abandoned"

    def test_staffing_forecast_defaults(self):
        fc = StaffingForecast(customer_id=CUSTOMER_ID, date="2026-02-24", hour=10)
        assert fc.id.startswith("fc_")
        assert fc.predicted_volume == 0
        assert fc.confidence == 0.0

    def test_workforce_metrics_defaults(self):
        wm = WorkforceMetrics(customer_id=CUSTOMER_ID)
        assert wm.id.startswith("wm_")
        assert wm.containment_rate == 0.0
        assert wm.cost_savings_cents == 0

    def test_roi_estimate(self):
        roi = ROIEstimate(
            human_cost_per_month_cents=100000,
            ai_cost_per_month_cents=30000,
            monthly_savings_cents=70000,
        )
        assert roi.monthly_savings_cents == 70000

    def test_workforce_dashboard(self):
        dash = WorkforceDashboard()
        assert dash.active_human_agents == 0
        assert dash.containment_trend == []


# ── Human Agent CRUD ──────────────────────────────────────────────


class TestHumanAgentCRUD:
    def test_create_agent(self):
        agent = wf_svc.create_human_agent(
            customer_id=CUSTOMER_ID,
            name="Alice Smith",
            email="alice@test.com",
            skills=["billing", "support"],
            department_id="dept_1",
            shift_start="09:00",
            shift_end="17:00",
        )
        assert agent.name == "Alice Smith"
        assert agent.email == "alice@test.com"
        assert "billing" in agent.skills
        assert agent.status == HumanAgentStatus.OFFLINE

    def test_list_agents(self):
        wf_svc.create_human_agent(CUSTOMER_ID, name="Bob", status=HumanAgentStatus.AVAILABLE)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice", status=HumanAgentStatus.OFFLINE)
        wf_svc.create_human_agent("other_customer", name="Eve")

        agents = wf_svc.list_human_agents(CUSTOMER_ID)
        assert len(agents) == 2
        assert agents[0].name == "Alice"  # sorted by name

    def test_list_agents_filter_status(self):
        wf_svc.create_human_agent(CUSTOMER_ID, name="Bob", status=HumanAgentStatus.AVAILABLE)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice", status=HumanAgentStatus.OFFLINE)

        available = wf_svc.list_human_agents(CUSTOMER_ID, status=HumanAgentStatus.AVAILABLE)
        assert len(available) == 1
        assert available[0].name == "Bob"

    def test_list_agents_filter_department(self):
        wf_svc.create_human_agent(CUSTOMER_ID, name="Bob", department_id="sales")
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice", department_id="support")

        sales = wf_svc.list_human_agents(CUSTOMER_ID, department_id="sales")
        assert len(sales) == 1

    def test_get_agent(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Charlie")
        found = wf_svc.get_human_agent(agent.id)
        assert found is not None
        assert found.name == "Charlie"

    def test_get_agent_not_found(self):
        assert wf_svc.get_human_agent("nonexistent") is None

    def test_update_agent(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Dave")
        updated = wf_svc.update_human_agent(agent.id, name="David", email="david@test.com")
        assert updated.name == "David"
        assert updated.email == "david@test.com"

    def test_update_agent_not_found(self):
        assert wf_svc.update_human_agent("nonexistent", name="X") is None

    def test_delete_agent(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Eve")
        assert wf_svc.delete_human_agent(agent.id) is True
        assert wf_svc.get_human_agent(agent.id) is None

    def test_delete_agent_not_found(self):
        assert wf_svc.delete_human_agent("nonexistent") is False


class TestAgentStatus:
    def test_set_status(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Frank")
        result = wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        assert result.status == HumanAgentStatus.AVAILABLE

    def test_set_offline_clears_call(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Grace")
        agent.current_call_id = "call_123"
        agent.status = HumanAgentStatus.BUSY
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.OFFLINE)
        assert agent.current_call_id is None

    def test_set_status_not_found(self):
        assert wf_svc.set_agent_status("nonexistent", HumanAgentStatus.AVAILABLE) is None


class TestAgentUtilization:
    def test_utilization_calculation(self):
        agent = wf_svc.create_human_agent(
            CUSTOMER_ID, name="Hank", shift_start="09:00", shift_end="17:00"
        )
        agent.busy_minutes_today = 240  # 4 hours out of 8
        util = wf_svc.get_agent_utilization(agent.id)
        assert util == 50.0

    def test_utilization_no_shift(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Ivy")
        assert wf_svc.get_agent_utilization(agent.id) == 0.0

    def test_utilization_not_found(self):
        assert wf_svc.get_agent_utilization("nonexistent") == 0.0

    def test_utilization_capped_at_100(self):
        agent = wf_svc.create_human_agent(
            CUSTOMER_ID, name="Jack", shift_start="09:00", shift_end="17:00"
        )
        agent.busy_minutes_today = 600  # more than shift
        assert wf_svc.get_agent_utilization(agent.id) == 100.0


# ── Escalation Queue ──────────────────────────────────────────────


class TestEscalationQueue:
    def test_enqueue(self):
        esc = wf_svc.enqueue_escalation(
            CUSTOMER_ID,
            call_id="call_1",
            reason="Complex billing issue",
            priority=EscalationPriority.HIGH,
        )
        assert esc.status == EscalationStatus.WAITING
        assert esc.reason == "Complex billing issue"
        assert esc.priority == EscalationPriority.HIGH

    def test_list_escalations(self):
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_2")
        wf_svc.enqueue_escalation("other", call_id="call_3")

        escs = wf_svc.list_escalations(CUSTOMER_ID)
        assert len(escs) == 2

    def test_list_escalations_filter_status(self):
        esc1 = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_2")
        wf_svc.abandon_escalation(esc1.id)

        waiting = wf_svc.list_escalations(CUSTOMER_ID, status=EscalationStatus.WAITING)
        assert len(waiting) == 1

    def test_assign_escalation(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Kate")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")

        result = wf_svc.assign_escalation(esc.id, agent.id)
        assert result.status == EscalationStatus.ASSIGNED
        assert result.human_agent_id == agent.id
        assert result.assigned_at is not None
        assert result.wait_time_seconds >= 0
        # Agent should be busy
        assert agent.status == HumanAgentStatus.BUSY
        assert agent.current_call_id == "call_1"

    def test_assign_fails_not_waiting(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Lee")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.abandon_escalation(esc.id)

        assert wf_svc.assign_escalation(esc.id, agent.id) is None

    def test_assign_fails_agent_not_available(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Mike")
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")

        assert wf_svc.assign_escalation(esc.id, agent.id) is None  # agent is offline

    def test_auto_assign(self):
        a1 = wf_svc.create_human_agent(CUSTOMER_ID, name="Nina", department_id="support")
        wf_svc.set_agent_status(a1.id, HumanAgentStatus.AVAILABLE)
        a1.calls_handled_today = 5

        a2 = wf_svc.create_human_agent(CUSTOMER_ID, name="Oscar", department_id="support")
        wf_svc.set_agent_status(a2.id, HumanAgentStatus.AVAILABLE)
        a2.calls_handled_today = 2  # fewer calls → should be picked

        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1", department_id="support")
        result = wf_svc.auto_assign_escalation(esc.id, CUSTOMER_ID)

        assert result is not None
        assert result.human_agent_id == a2.id  # least busy

    def test_auto_assign_no_agents(self):
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        assert wf_svc.auto_assign_escalation(esc.id, CUSTOMER_ID) is None

    def test_resolve_escalation(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Pat")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.assign_escalation(esc.id, agent.id)

        result = wf_svc.resolve_escalation(esc.id)
        assert result.status == EscalationStatus.RESOLVED
        assert result.resolved_at is not None
        assert result.handle_time_seconds >= 0
        # Agent freed
        assert agent.status == HumanAgentStatus.AVAILABLE
        assert agent.current_call_id is None
        assert agent.calls_handled_today == 1

    def test_resolve_fails_already_resolved(self):
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.resolve_escalation(esc.id)
        assert wf_svc.resolve_escalation(esc.id) is None

    def test_abandon_escalation(self):
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        result = wf_svc.abandon_escalation(esc.id)
        assert result.status == EscalationStatus.ABANDONED
        assert result.wait_time_seconds >= 0

    def test_abandon_fails_not_waiting(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Quinn")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.assign_escalation(esc.id, agent.id)

        assert wf_svc.abandon_escalation(esc.id) is None  # already assigned


class TestQueueStatus:
    def test_empty_queue(self):
        status = wf_svc.get_queue_status(CUSTOMER_ID)
        assert status["waiting"] == 0
        assert status["assigned"] == 0
        assert status["avg_wait_time_seconds"] == 0.0

    def test_queue_with_items(self):
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_2")

        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Ray")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc3 = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_3")
        wf_svc.assign_escalation(esc3.id, agent.id)

        status = wf_svc.get_queue_status(CUSTOMER_ID)
        assert status["waiting"] == 2
        assert status["assigned"] == 1


# ── Forecasting ───────────────────────────────────────────────────


class TestForecasting:
    def test_generate_default_forecast(self):
        forecasts = wf_svc.generate_forecast(CUSTOMER_ID, date="2026-02-24")
        assert len(forecasts) == 24
        # Peak hours should have higher volume
        peak = next(f for f in forecasts if f.hour == 10)
        night = next(f for f in forecasts if f.hour == 2)
        assert peak.predicted_volume > night.predicted_volume
        assert peak.recommended_staff >= 1
        assert peak.confidence == 0.65  # default data

    def test_forecast_containment_split(self):
        forecasts = wf_svc.generate_forecast(
            CUSTOMER_ID, date="2026-02-24", containment_rate=0.80
        )
        for fc in forecasts:
            assert fc.predicted_ai_handled + fc.predicted_escalations == fc.predicted_volume
            if fc.predicted_volume >= 20:  # only check rate for meaningful volumes
                actual_rate = fc.predicted_ai_handled / fc.predicted_volume
                assert abs(actual_rate - 0.80) < 0.10  # int rounding tolerance

    def test_generate_with_historical(self):
        historical = [
            {"hour": 9, "volume": 100},
            {"hour": 9, "volume": 120},
            {"hour": 10, "volume": 150},
        ]
        forecasts = wf_svc.generate_forecast(
            CUSTOMER_ID, date="2026-02-24", historical_calls=historical
        )
        hour_9 = next(f for f in forecasts if f.hour == 9)
        assert hour_9.predicted_volume == 110  # average of 100, 120
        assert hour_9.confidence == 0.85  # historical data

    def test_get_forecasts(self):
        wf_svc.generate_forecast(CUSTOMER_ID, date="2026-02-24")
        results = wf_svc.get_forecasts(CUSTOMER_ID, "2026-02-24")
        assert len(results) == 24
        assert results[0].hour == 0
        assert results[-1].hour == 23

    def test_get_forecasts_wrong_date(self):
        wf_svc.generate_forecast(CUSTOMER_ID, date="2026-02-24")
        results = wf_svc.get_forecasts(CUSTOMER_ID, "2026-03-01")
        assert len(results) == 0


# ── Metrics & ROI ─────────────────────────────────────────────────


class TestMetrics:
    def test_calculate_metrics(self):
        metrics = wf_svc.calculate_metrics(
            CUSTOMER_ID,
            period_start="2026-02-17",
            period_end="2026-02-23",
            total_calls=1000,
            ai_handled=800,
            human_handled=200,
            avg_wait_time_seconds=45.0,
            avg_handle_time_seconds=300.0,
        )
        assert metrics.containment_rate == 0.8
        assert metrics.escalation_rate == 0.2
        assert metrics.cost_savings_cents > 0

    def test_calculate_metrics_zero_calls(self):
        metrics = wf_svc.calculate_metrics(
            CUSTOMER_ID,
            period_start="2026-02-17",
            period_end="2026-02-23",
            total_calls=0,
        )
        assert metrics.containment_rate == 0.0
        assert metrics.escalation_rate == 0.0

    def test_containment_trend_no_data(self):
        trend = wf_svc.get_containment_trend(CUSTOMER_ID, weeks=4)
        assert len(trend) == 4
        for entry in trend:
            assert "period" in entry
            assert "containment_rate" in entry
            assert 0.0 <= entry["containment_rate"] <= 1.0

    def test_containment_trend_with_metrics(self):
        for i in range(3):
            wf_svc.calculate_metrics(
                CUSTOMER_ID,
                period_start=f"2026-02-{10 + i * 7:02d}",
                period_end=f"2026-02-{16 + i * 7:02d}",
                total_calls=1000,
                ai_handled=800 + i * 20,
                human_handled=200 - i * 20,
            )
        trend = wf_svc.get_containment_trend(CUSTOMER_ID)
        assert len(trend) == 3
        # Should show improvement
        assert trend[-1]["containment_rate"] >= trend[0]["containment_rate"]


class TestROI:
    def test_calculate_roi(self):
        roi = wf_svc.calculate_roi(
            CUSTOMER_ID,
            human_agent_hourly_rate_cents=2000,
            calls_per_agent_per_hour=4,
            total_monthly_calls=10000,
            containment_rate=0.80,
            avg_call_duration_minutes=5.0,
            ai_cost_per_minute_cents=6,
        )
        assert roi.human_cost_per_month_cents > 0
        assert roi.ai_cost_per_month_cents > 0
        assert roi.monthly_savings_cents > 0
        assert roi.annual_savings_cents == roi.monthly_savings_cents * 12
        assert roi.savings_percentage > 0

    def test_roi_high_containment(self):
        roi_80 = wf_svc.calculate_roi(CUSTOMER_ID, containment_rate=0.80)
        roi_95 = wf_svc.calculate_roi(CUSTOMER_ID, containment_rate=0.95)
        # Higher containment → more savings
        assert roi_95.monthly_savings_cents >= roi_80.monthly_savings_cents

    def test_roi_low_volume(self):
        roi = wf_svc.calculate_roi(CUSTOMER_ID, total_monthly_calls=100)
        assert roi.calls_per_month == 100
        assert roi.monthly_savings_cents >= 0


# ── Dashboard ─────────────────────────────────────────────────────


class TestDashboard:
    def test_empty_dashboard(self):
        dash = wf_svc.get_dashboard(CUSTOMER_ID)
        assert dash.active_human_agents == 0
        assert dash.total_human_agents == 0
        assert dash.queue_length == 0

    def test_dashboard_with_data(self):
        a1 = wf_svc.create_human_agent(CUSTOMER_ID, name="Sam")
        wf_svc.set_agent_status(a1.id, HumanAgentStatus.AVAILABLE)
        a2 = wf_svc.create_human_agent(CUSTOMER_ID, name="Tina")
        wf_svc.set_agent_status(a2.id, HumanAgentStatus.BUSY)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Uma")  # offline

        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_2")

        dash = wf_svc.get_dashboard(CUSTOMER_ID)
        assert dash.active_human_agents == 2  # available + busy
        assert dash.total_human_agents == 3
        assert dash.queue_length == 2
        assert dash.agents_by_status["available"] == 1
        assert dash.agents_by_status["busy"] == 1
        assert dash.agents_by_status["offline"] == 1
        assert len(dash.containment_trend) > 0
        assert len(dash.recent_escalations) == 2
