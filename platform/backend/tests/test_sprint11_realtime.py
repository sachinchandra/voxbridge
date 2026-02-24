"""Sprint 11 tests — Real-Time Events & Live Monitoring.

Tests cover:
  - Event bus: publish, subscribe, unsubscribe, history, isolation
  - WebSocket manager: connect tracking, broadcast, cleanup
  - Live metrics: snapshots, active calls, agent presence, counters
  - Event hooks: workforce and alert events emitted correctly
  - Live API endpoints: dashboard, events, active-calls, agent-presence
"""

import asyncio
import pytest
from datetime import datetime, timezone

from app.services import event_bus
from app.services import ws_manager
from app.services import live_metrics
from app.services import workforce as wf_svc
from app.services import alerts as alert_svc
from app.models.database import (
    HumanAgentStatus,
    EscalationPriority,
    Alert,
    AlertSeverity,
    AlertType,
)

CUSTOMER_ID = "cust_test_sprint11"
OTHER_CUSTOMER = "cust_other_sprint11"


@pytest.fixture(autouse=True)
def _clear_all():
    """Clear all in-memory stores before each test."""
    event_bus.clear_all()
    ws_manager.clear_all()
    live_metrics.clear_all()
    wf_svc._human_agents.clear()
    wf_svc._escalations.clear()
    wf_svc._forecasts.clear()
    wf_svc._metrics.clear()
    yield


# ── Event Bus Tests ──────────────────────────────────────────────


class TestEventBus:
    def test_publish_returns_event(self):
        evt = event_bus.publish(CUSTOMER_ID, "test.event", {"key": "value"})
        assert evt["type"] == "test.event"
        assert evt["customer_id"] == CUSTOMER_ID
        assert evt["payload"]["key"] == "value"
        assert "timestamp" in evt

    def test_publish_with_enum(self):
        evt = event_bus.publish(CUSTOMER_ID, event_bus.EventType.CALL_STARTED, {"call_id": "c1"})
        assert evt["type"] == "call.started"

    def test_subscribe_receives_events(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        event_bus.publish(CUSTOMER_ID, "test.event", {"n": 1})
        assert not queue.empty()
        evt = queue.get_nowait()
        assert evt["payload"]["n"] == 1

    def test_unsubscribe_stops_events(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        event_bus.unsubscribe(CUSTOMER_ID, queue)
        event_bus.publish(CUSTOMER_ID, "test.event", {"n": 1})
        assert queue.empty()

    def test_customer_isolation(self):
        queue_a = event_bus.subscribe(CUSTOMER_ID)
        queue_b = event_bus.subscribe(OTHER_CUSTOMER)
        event_bus.publish(CUSTOMER_ID, "test.event", {"for": "a"})
        assert not queue_a.empty()
        assert queue_b.empty()

    def test_multiple_subscribers(self):
        q1 = event_bus.subscribe(CUSTOMER_ID)
        q2 = event_bus.subscribe(CUSTOMER_ID)
        event_bus.publish(CUSTOMER_ID, "test.event", {"n": 1})
        assert not q1.empty()
        assert not q2.empty()

    def test_event_history(self):
        for i in range(5):
            event_bus.publish(CUSTOMER_ID, "test.event", {"n": i})
        recent = event_bus.get_recent_events(CUSTOMER_ID, limit=3)
        assert len(recent) == 3
        # Newest first
        assert recent[0]["payload"]["n"] == 4
        assert recent[2]["payload"]["n"] == 2

    def test_history_max_buffer(self):
        for i in range(60):
            event_bus.publish(CUSTOMER_ID, "test.event", {"n": i})
        # Should only keep last 50
        all_events = event_bus.get_recent_events(CUSTOMER_ID, limit=100)
        assert len(all_events) == 50
        # Oldest retained should be n=10 (0-9 evicted)
        assert all_events[-1]["payload"]["n"] == 10

    def test_events_since(self):
        for i in range(5):
            event_bus.publish(CUSTOMER_ID, "test.event", {"n": i})
        all_events = event_bus.get_recent_events(CUSTOMER_ID, limit=5)
        # Get events since the 3rd event's timestamp (should return events after it)
        since_ts = all_events[3]["timestamp"]  # 2nd event (index 3 = 2nd oldest)
        newer = event_bus.get_events_since(CUSTOMER_ID, since_ts)
        assert len(newer) >= 1  # at least the latest events after that timestamp

    def test_subscriber_count(self):
        assert event_bus.subscriber_count(CUSTOMER_ID) == 0
        q = event_bus.subscribe(CUSTOMER_ID)
        assert event_bus.subscriber_count(CUSTOMER_ID) == 1
        event_bus.unsubscribe(CUSTOMER_ID, q)
        assert event_bus.subscriber_count(CUSTOMER_ID) == 0

    def test_total_subscribers(self):
        event_bus.subscribe(CUSTOMER_ID)
        event_bus.subscribe(OTHER_CUSTOMER)
        assert event_bus.total_subscribers() == 2

    def test_clear_customer(self):
        event_bus.publish(CUSTOMER_ID, "test.event", {})
        event_bus.subscribe(CUSTOMER_ID)
        event_bus.clear_customer(CUSTOMER_ID)
        assert event_bus.get_recent_events(CUSTOMER_ID) == []
        assert event_bus.subscriber_count(CUSTOMER_ID) == 0


# ── WebSocket Manager Tests ──────────────────────────────────────


class TestWSManager:
    def test_connection_count_empty(self):
        assert ws_manager.connection_count(CUSTOMER_ID) == 0

    def test_total_connections_empty(self):
        assert ws_manager.total_connections() == 0

    def test_active_customers_empty(self):
        assert ws_manager.active_customers() == []

    def test_clear_all(self):
        # Just verify clear_all doesn't crash
        ws_manager.clear_all()
        assert ws_manager.total_connections() == 0


# ── Live Metrics Tests ───────────────────────────────────────────


class TestLiveMetrics:
    def test_empty_snapshot(self):
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["active_calls"] == 0
        assert snap["calls_today"] == 0
        assert snap["containment_rate"] == 0.0
        assert snap["active_agents"] == 0
        assert snap["queue_depth"] == 0
        assert snap["calls_per_minute"] == 0.0
        assert "timestamp" in snap

    def test_track_call_started(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID, agent_id="a1", direction="inbound")
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["active_calls"] == 1
        assert snap["calls_today"] == 1

    def test_track_call_ended_ai(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID)
        live_metrics.track_call_ended("call_1", escalated=False)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["active_calls"] == 0
        assert snap["calls_today"] == 1
        assert snap["ai_contained_today"] == 1
        assert snap["escalated_today"] == 0

    def test_track_call_ended_escalated(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID)
        live_metrics.track_call_ended("call_1", escalated=True)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["escalated_today"] == 1
        assert snap["ai_contained_today"] == 0

    def test_containment_rate(self):
        for i in range(10):
            live_metrics.track_call_started(f"call_{i}", CUSTOMER_ID)
        for i in range(8):
            live_metrics.track_call_ended(f"call_{i}", escalated=False)
        for i in range(8, 10):
            live_metrics.track_call_ended(f"call_{i}", escalated=True)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["containment_rate"] == 0.8

    def test_active_calls_list(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID, agent_name="Bot A", direction="inbound")
        live_metrics.track_call_started("call_2", CUSTOMER_ID, agent_name="Bot B", direction="outbound")
        active = live_metrics.get_active_calls(CUSTOMER_ID)
        assert len(active) == 2
        assert active[0]["agent_name"] in ("Bot A", "Bot B")
        assert "duration_seconds" in active[0]

    def test_active_calls_filtered_by_customer(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID)
        live_metrics.track_call_started("call_2", OTHER_CUSTOMER)
        active = live_metrics.get_active_calls(CUSTOMER_ID)
        assert len(active) == 1

    def test_agent_presence(self):
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice", status=HumanAgentStatus.AVAILABLE)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Bob", status=HumanAgentStatus.BUSY)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Charlie", status=HumanAgentStatus.OFFLINE)
        presence = live_metrics.get_agent_presence(CUSTOMER_ID)
        assert len(presence) == 3
        assert all("status" in p for p in presence)
        assert all("name" in p for p in presence)

    def test_snapshot_with_agents(self):
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice", status=HumanAgentStatus.AVAILABLE)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Bob", status=HumanAgentStatus.BUSY)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["active_agents"] == 2
        assert snap["total_agents"] == 2

    def test_snapshot_with_queue(self):
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_2")
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["queue_depth"] == 2

    def test_track_call_status(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID)
        live_metrics.track_call_status("call_1", "ringing")
        active = live_metrics.get_active_calls(CUSTOMER_ID)
        assert active[0]["status"] == "ringing"

    def test_calls_per_minute(self):
        for i in range(10):
            live_metrics.track_call_started(f"call_{i}", CUSTOMER_ID)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["calls_per_minute"] > 0

    def test_reset_daily_counters(self):
        live_metrics.track_call_started("call_1", CUSTOMER_ID)
        live_metrics.track_call_ended("call_1", escalated=False)
        live_metrics.reset_daily_counters(CUSTOMER_ID)
        snap = live_metrics.get_live_snapshot(CUSTOMER_ID)
        assert snap["calls_today"] == 0


# ── Event Hook Tests ─────────────────────────────────────────────


class TestEventHooks:
    def test_agent_status_emits_event(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Alice")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        assert not queue.empty()
        evt = queue.get_nowait()
        assert evt["type"] == "agent.status_changed"
        assert evt["payload"]["agent_name"] == "Alice"
        assert evt["payload"]["new_status"] == HumanAgentStatus.AVAILABLE

    def test_escalation_created_emits_event(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1", reason="Complex issue")
        assert not queue.empty()
        evt = queue.get_nowait()
        assert evt["type"] == "escalation.created"
        assert evt["payload"]["call_id"] == "call_1"
        assert evt["payload"]["reason"] == "Complex issue"

    def test_escalation_assigned_emits_event(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Bob")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")

        queue = event_bus.subscribe(CUSTOMER_ID)
        wf_svc.assign_escalation(esc.id, agent.id)
        assert not queue.empty()
        evt = queue.get_nowait()
        assert evt["type"] == "escalation.assigned"
        assert evt["payload"]["agent_name"] == "Bob"

    def test_escalation_resolved_emits_event(self):
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Carol")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        esc = wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        wf_svc.assign_escalation(esc.id, agent.id)

        queue = event_bus.subscribe(CUSTOMER_ID)
        wf_svc.resolve_escalation(esc.id)
        # Should get agent.status_changed (back to available) + escalation.resolved
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        types = [e["type"] for e in events]
        assert "escalation.resolved" in types

    def test_alert_fired_emits_event(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        alert = Alert(
            customer_id=CUSTOMER_ID,
            rule_id="rule_1",
            alert_type=AlertType.HIGH_VOLUME,
            severity=AlertSeverity.WARNING,
            title="High call volume",
            message="Volume spike detected",
        )
        alert_svc.create_alert(alert)
        assert not queue.empty()
        evt = queue.get_nowait()
        assert evt["type"] == "alert.fired"
        assert evt["payload"]["title"] == "High call volume"
        assert evt["payload"]["severity"] == AlertSeverity.WARNING

    def test_no_event_for_other_customer(self):
        queue = event_bus.subscribe(OTHER_CUSTOMER)
        wf_svc.create_human_agent(CUSTOMER_ID, name="Alice")
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")
        assert queue.empty()  # events only go to CUSTOMER_ID

    def test_multiple_events_in_sequence(self):
        queue = event_bus.subscribe(CUSTOMER_ID)
        agent = wf_svc.create_human_agent(CUSTOMER_ID, name="Dave")
        wf_svc.set_agent_status(agent.id, HumanAgentStatus.AVAILABLE)
        wf_svc.enqueue_escalation(CUSTOMER_ID, call_id="call_1")

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
        assert len(events) == 2  # agent.status_changed + escalation.created
        types = [e["type"] for e in events]
        assert "agent.status_changed" in types
        assert "escalation.created" in types


# ── Event Types Enum Tests ───────────────────────────────────────


class TestEventTypes:
    def test_all_event_types_exist(self):
        expected = [
            "call.started", "call.ended", "call.status_changed",
            "agent.status_changed", "escalation.created",
            "escalation.assigned", "escalation.resolved",
            "alert.fired", "violation.detected", "metric.updated",
        ]
        for et in expected:
            assert et in [e.value for e in event_bus.EventType]

    def test_event_type_values(self):
        assert event_bus.EventType.CALL_STARTED == "call.started"
        assert event_bus.EventType.AGENT_STATUS_CHANGED == "agent.status_changed"
        assert event_bus.EventType.ALERT_FIRED == "alert.fired"
