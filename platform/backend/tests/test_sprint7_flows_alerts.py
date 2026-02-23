"""Sprint 7 tests — Conversation Flow Engine + Alerts System.

Tests cover:
- Flow models (nodes, edges, flows, versions, test results)
- Flow engine (CRUD, validation, execution, A/B traffic selection)
- Alert models (rules, alerts, summary)
- Alert service (rule CRUD, alert CRUD, evaluation engine, default rules)
"""

import pytest


# ──────────────────────────────────────────────────────────────────
# Flow models
# ──────────────────────────────────────────────────────────────────

class TestFlowNode:
    def test_defaults(self):
        from app.models.database import FlowNode, FlowNodeType
        node = FlowNode()
        assert node.type == FlowNodeType.MESSAGE
        assert node.label == ""
        assert node.config == {}
        assert len(node.id) > 0

    def test_custom_node(self):
        from app.models.database import FlowNode, FlowNodeType
        node = FlowNode(type=FlowNodeType.CONDITION, label="Check Intent", config={"rules": [{"match": "refund", "target_node_id": "n1"}]})
        assert node.type == FlowNodeType.CONDITION
        assert len(node.config["rules"]) == 1


class TestFlowEdge:
    def test_defaults(self):
        from app.models.database import FlowEdge
        edge = FlowEdge()
        assert edge.source_id == ""
        assert edge.target_id == ""
        assert edge.label == ""


class TestConversationFlow:
    def test_defaults(self):
        from app.models.database import ConversationFlow
        flow = ConversationFlow()
        assert flow.nodes == []
        assert flow.edges == []
        assert flow.is_active is False
        assert flow.version == 1

    def test_with_nodes(self):
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType
        flow = ConversationFlow(
            name="Test Flow",
            nodes=[FlowNode(type=FlowNodeType.START), FlowNode(type=FlowNodeType.END)],
        )
        assert flow.name == "Test Flow"
        assert len(flow.nodes) == 2


class TestFlowVersion:
    def test_defaults(self):
        from app.models.database import FlowVersion
        v = FlowVersion()
        assert v.traffic_percent == 100
        assert v.calls_count == 0


class TestFlowTestResult:
    def test_defaults(self):
        from app.models.database import FlowTestResult
        r = FlowTestResult()
        assert r.path == []
        assert r.messages == []
        assert r.completed is False


# ──────────────────────────────────────────────────────────────────
# Flow engine — CRUD
# ──────────────────────────────────────────────────────────────────

class TestFlowCRUD:
    def setup_method(self):
        from app.services import flow_engine as fe
        fe._flows.clear()
        fe._versions.clear()

    def test_save_and_get(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow
        flow = ConversationFlow(customer_id="c1", name="Test")
        fe.save_flow(flow)
        assert fe.get_flow(flow.id) is not None
        assert fe.get_flow(flow.id).name == "Test"

    def test_list_flows(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow
        fe.save_flow(ConversationFlow(customer_id="c1", name="A"))
        fe.save_flow(ConversationFlow(customer_id="c1", name="B"))
        fe.save_flow(ConversationFlow(customer_id="c2", name="C"))
        assert len(fe.list_flows("c1")) == 2
        assert len(fe.list_flows("c2")) == 1

    def test_delete_flow(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow
        flow = ConversationFlow(customer_id="c1")
        fe.save_flow(flow)
        assert fe.delete_flow(flow.id) is True
        assert fe.get_flow(flow.id) is None
        assert fe.delete_flow(flow.id) is False

    def test_get_nonexistent(self):
        from app.services import flow_engine as fe
        assert fe.get_flow("nonexistent") is None


# ──────────────────────────────────────────────────────────────────
# Flow engine — validation
# ──────────────────────────────────────────────────────────────────

class TestFlowValidation:
    def test_empty_flow(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow
        errors = fe.validate_flow(ConversationFlow())
        assert "Flow has no nodes" in errors

    def test_no_start_node(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType
        flow = ConversationFlow(nodes=[FlowNode(type=FlowNodeType.END)])
        errors = fe.validate_flow(flow)
        assert any("START" in e for e in errors)

    def test_no_end_node(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType, FlowEdge
        start = FlowNode(type=FlowNodeType.START)
        msg = FlowNode(type=FlowNodeType.MESSAGE)
        flow = ConversationFlow(
            nodes=[start, msg],
            edges=[FlowEdge(source_id=start.id, target_id=msg.id)],
        )
        errors = fe.validate_flow(flow)
        assert any("END" in e for e in errors)

    def test_valid_flow(self):
        from app.services import flow_engine as fe
        flow = fe.create_default_flow("c1", "a1")
        errors = fe.validate_flow(flow)
        assert errors == []

    def test_condition_needs_two_edges(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType, FlowEdge
        start = FlowNode(type=FlowNodeType.START)
        cond = FlowNode(type=FlowNodeType.CONDITION, label="Check")
        end = FlowNode(type=FlowNodeType.END)
        flow = ConversationFlow(
            nodes=[start, cond, end],
            edges=[
                FlowEdge(source_id=start.id, target_id=cond.id),
                FlowEdge(source_id=cond.id, target_id=end.id),  # only 1 edge
            ],
        )
        errors = fe.validate_flow(flow)
        assert any("at least 2" in e for e in errors)


# ──────────────────────────────────────────────────────────────────
# Flow engine — execution
# ──────────────────────────────────────────────────────────────────

class TestFlowExecution:
    def test_default_flow(self):
        from app.services import flow_engine as fe
        flow = fe.create_default_flow("c1", "a1")
        result = fe.execute_flow(flow, ["Hello, I need help"])
        assert result.completed is True
        assert result.end_reason == "completed"
        assert len(result.messages) >= 2  # greeting + end message
        assert len(result.path) >= 3

    def test_no_start_node_error(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType
        flow = ConversationFlow(nodes=[FlowNode(type=FlowNodeType.END)])
        result = fe.execute_flow(flow, [])
        assert result.completed is False
        assert result.end_reason == "error"

    def test_timeout_on_no_input(self):
        from app.services import flow_engine as fe
        flow = fe.create_default_flow("c1", "a1")
        # No inputs provided — listen node will timeout
        result = fe.execute_flow(flow, [])
        assert result.end_reason == "timeout"

    def test_transfer_node(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType, FlowEdge
        start = FlowNode(type=FlowNodeType.START)
        transfer = FlowNode(type=FlowNodeType.TRANSFER, config={"target_number": "+1555"})
        flow = ConversationFlow(
            nodes=[start, transfer],
            edges=[FlowEdge(source_id=start.id, target_id=transfer.id)],
        )
        result = fe.execute_flow(flow, [])
        assert result.completed is True
        assert result.end_reason == "transfer"

    def test_condition_routing(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType, FlowEdge
        start = FlowNode(type=FlowNodeType.START)
        listen = FlowNode(type=FlowNodeType.LISTEN)
        cond = FlowNode(type=FlowNodeType.CONDITION, config={
            "rules": [
                {"match": "refund|return", "target_node_id": ""},  # will be set below
                {"match": "*", "target_node_id": ""},
            ]
        })
        refund_end = FlowNode(type=FlowNodeType.END, config={"text": "Processing refund"})
        default_end = FlowNode(type=FlowNodeType.END, config={"text": "General help"})

        cond.config["rules"][0]["target_node_id"] = refund_end.id
        cond.config["rules"][1]["target_node_id"] = default_end.id

        flow = ConversationFlow(
            nodes=[start, listen, cond, refund_end, default_end],
            edges=[
                FlowEdge(source_id=start.id, target_id=listen.id),
                FlowEdge(source_id=listen.id, target_id=cond.id),
                FlowEdge(source_id=cond.id, target_id=refund_end.id),
                FlowEdge(source_id=cond.id, target_id=default_end.id),
            ],
        )
        result = fe.execute_flow(flow, ["I want a refund please"])
        assert result.completed is True
        assert any("refund" in m["content"].lower() for m in result.messages if m["role"] == "assistant")

    def test_tool_call_node(self):
        from app.services import flow_engine as fe
        from app.models.database import ConversationFlow, FlowNode, FlowNodeType, FlowEdge
        start = FlowNode(type=FlowNodeType.START)
        tool = FlowNode(type=FlowNodeType.TOOL_CALL, config={"tool_name": "check_order"})
        end = FlowNode(type=FlowNodeType.END)
        flow = ConversationFlow(
            nodes=[start, tool, end],
            edges=[
                FlowEdge(source_id=start.id, target_id=tool.id),
                FlowEdge(source_id=tool.id, target_id=end.id),
            ],
        )
        result = fe.execute_flow(flow, [])
        assert any("check_order" in m["content"] for m in result.messages if m["role"] == "tool")


# ──────────────────────────────────────────────────────────────────
# Flow engine — versioning and A/B
# ──────────────────────────────────────────────────────────────────

class TestFlowVersioning:
    def setup_method(self):
        from app.services import flow_engine as fe
        fe._flows.clear()
        fe._versions.clear()

    def test_save_and_get_versions(self):
        from app.services import flow_engine as fe
        from app.models.database import FlowVersion
        v = FlowVersion(flow_id="f1", version=1, name="A", traffic_percent=50)
        fe.save_version("f1", v)
        assert len(fe.get_versions("f1")) == 1

    def test_traffic_split_single_version(self):
        from app.services import flow_engine as fe
        from app.models.database import FlowVersion
        v = FlowVersion(flow_id="f1", traffic_percent=100)
        fe.save_version("f1", v)
        selected = fe.select_version_by_traffic("f1")
        assert selected is not None

    def test_traffic_split_returns_none_for_no_versions(self):
        from app.services import flow_engine as fe
        assert fe.select_version_by_traffic("nonexistent") is None

    def test_default_flow_creation(self):
        from app.services import flow_engine as fe
        flow = fe.create_default_flow("c1", "a1", "My Flow")
        assert flow.name == "My Flow"
        assert len(flow.nodes) == 5
        assert len(flow.edges) == 4


# ──────────────────────────────────────────────────────────────────
# Alert models
# ──────────────────────────────────────────────────────────────────

class TestAlertModels:
    def test_alert_rule_defaults(self):
        from app.models.database import AlertRule, AlertType, AlertSeverity
        rule = AlertRule()
        assert rule.alert_type == AlertType.HIGH_VOLUME
        assert rule.severity == AlertSeverity.WARNING
        assert rule.enabled is True
        assert rule.notify_email is True

    def test_alert_defaults(self):
        from app.models.database import Alert
        alert = Alert()
        assert alert.acknowledged is False
        assert alert.acknowledged_at is None

    def test_alert_summary_defaults(self):
        from app.models.database import AlertSummary
        s = AlertSummary()
        assert s.total == 0
        assert s.unacknowledged == 0
        assert s.recent == []


# ──────────────────────────────────────────────────────────────────
# Alert service — rule CRUD
# ──────────────────────────────────────────────────────────────────

class TestAlertRuleCRUD:
    def setup_method(self):
        from app.services import alerts
        alerts._rules.clear()
        alerts._alerts.clear()

    def test_create_and_get_rule(self):
        from app.services import alerts
        from app.models.database import AlertRule
        rule = AlertRule(customer_id="c1", name="Test")
        alerts.create_rule(rule)
        assert alerts.get_rule(rule.id) is not None

    def test_list_rules(self):
        from app.services import alerts
        from app.models.database import AlertRule
        alerts.create_rule(AlertRule(customer_id="c1", name="R1"))
        alerts.create_rule(AlertRule(customer_id="c1", name="R2"))
        alerts.create_rule(AlertRule(customer_id="c2", name="R3"))
        assert len(alerts.list_rules("c1")) == 2

    def test_update_rule(self):
        from app.services import alerts
        from app.models.database import AlertRule
        rule = AlertRule(customer_id="c1", name="Old")
        alerts.create_rule(rule)
        updated = alerts.update_rule(rule.id, {"name": "New", "enabled": False})
        assert updated.name == "New"
        assert updated.enabled is False

    def test_delete_rule(self):
        from app.services import alerts
        from app.models.database import AlertRule
        rule = AlertRule(customer_id="c1")
        alerts.create_rule(rule)
        assert alerts.delete_rule(rule.id) is True
        assert alerts.delete_rule(rule.id) is False

    def test_default_rules(self):
        from app.services import alerts
        rules = alerts.create_default_rules("c1")
        assert len(rules) == 6
        assert len(alerts.list_rules("c1")) == 6


# ──────────────────────────────────────────────────────────────────
# Alert service — alert CRUD
# ──────────────────────────────────────────────────────────────────

class TestAlertCRUD:
    def setup_method(self):
        from app.services import alerts
        alerts._rules.clear()
        alerts._alerts.clear()

    def test_create_alert(self):
        from app.services import alerts
        from app.models.database import Alert
        alert = Alert(customer_id="c1", title="Test")
        alerts.create_alert(alert)
        assert alerts.get_alert(alert.id) is not None

    def test_acknowledge_alert(self):
        from app.services import alerts
        from app.models.database import Alert
        alert = Alert(customer_id="c1")
        alerts.create_alert(alert)
        alerts.acknowledge_alert(alert.id)
        assert alerts.get_alert(alert.id).acknowledged is True

    def test_acknowledge_all(self):
        from app.services import alerts
        from app.models.database import Alert
        alerts.create_alert(Alert(customer_id="c1"))
        alerts.create_alert(Alert(customer_id="c1"))
        count = alerts.acknowledge_all("c1")
        assert count == 2

    def test_list_unacknowledged(self):
        from app.services import alerts
        from app.models.database import Alert
        a1 = Alert(customer_id="c1")
        a2 = Alert(customer_id="c1")
        alerts.create_alert(a1)
        alerts.create_alert(a2)
        alerts.acknowledge_alert(a1.id)
        unack = alerts.list_alerts("c1", unacknowledged_only=True)
        assert len(unack) == 1

    def test_summary(self):
        from app.services import alerts
        from app.models.database import Alert, AlertSeverity
        alerts.create_alert(Alert(customer_id="c1", severity=AlertSeverity.CRITICAL))
        alerts.create_alert(Alert(customer_id="c1", severity=AlertSeverity.WARNING))
        alerts.create_alert(Alert(customer_id="c1", severity=AlertSeverity.INFO))
        summary = alerts.get_alert_summary("c1")
        assert summary.total == 3
        assert summary.critical == 1
        assert summary.warning == 1
        assert summary.info == 1


# ──────────────────────────────────────────────────────────────────
# Alert service — evaluation engine
# ──────────────────────────────────────────────────────────────────

class TestAlertEvaluation:
    def setup_method(self):
        from app.services import alerts
        alerts._rules.clear()
        alerts._alerts.clear()

    def test_high_volume_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.HIGH_VOLUME, config={"threshold": 50})
        alert = alerts.evaluate_rule(rule, {"calls_in_window": 100})
        assert alert is not None
        assert "100" in alert.title

    def test_high_volume_no_trigger(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.HIGH_VOLUME, config={"threshold": 100})
        alert = alerts.evaluate_rule(rule, {"calls_in_window": 50})
        assert alert is None

    def test_angry_caller_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.ANGRY_CALLER_SPIKE, config={"threshold": 3})
        alert = alerts.evaluate_rule(rule, {"angry_callers_in_window": 5})
        assert alert is not None

    def test_low_quality_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.LOW_QUALITY_SCORE, config={"threshold": 60})
        alert = alerts.evaluate_rule(rule, {"avg_quality_score": 45})
        assert alert is not None

    def test_pii_detected_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType, AlertSeverity
        rule = AlertRule(customer_id="c1", alert_type=AlertType.PII_DETECTED)
        alert = alerts.evaluate_rule(rule, {"pii_detected": True})
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_cost_threshold_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.COST_THRESHOLD, config={"daily_limit_cents": 5000})
        alert = alerts.evaluate_rule(rule, {"daily_cost_cents": 7500})
        assert alert is not None
        assert "$75.00" in alert.title

    def test_disabled_rule_never_triggers(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.HIGH_VOLUME, config={"threshold": 10}, enabled=False)
        alert = alerts.evaluate_rule(rule, {"calls_in_window": 1000})
        assert alert is None

    def test_escalation_rate_with_min_calls(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        rule = AlertRule(customer_id="c1", alert_type=AlertType.HIGH_ESCALATION_RATE, config={"threshold_percent": 30, "min_calls": 20})
        # Not enough calls
        assert alerts.evaluate_rule(rule, {"escalation_rate": 50, "calls_in_window": 5}) is None
        # Enough calls + high rate
        alert = alerts.evaluate_rule(rule, {"escalation_rate": 50, "calls_in_window": 25})
        assert alert is not None

    def test_evaluate_all_rules(self):
        from app.services import alerts
        from app.models.database import AlertRule, AlertType
        alerts.create_rule(AlertRule(customer_id="c1", alert_type=AlertType.HIGH_VOLUME, config={"threshold": 10}))
        alerts.create_rule(AlertRule(customer_id="c1", alert_type=AlertType.PII_DETECTED))
        triggered = alerts.evaluate_all_rules("c1", {"calls_in_window": 50, "pii_detected": True})
        assert len(triggered) == 2
