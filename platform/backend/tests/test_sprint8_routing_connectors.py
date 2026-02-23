"""Sprint 8 tests — Multi-Department Routing + Contact Center Connectors.

Tests cover:
  - Department & Routing models
  - Intent router service (CRUD, classification, routing)
  - Connector models
  - Connector service (CRUD, activation, config validation, queue mapping, call routing, events)
"""

import pytest
from datetime import datetime, timezone

from app.models.database import (
    Department,
    RoutingRule,
    RoutingResult,
    RoutingConfig,
    Connector,
    ConnectorEvent,
    ConnectorType,
    ConnectorStatus,
)
from app.services import intent_router
from app.services import connectors as conn_svc


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

CUSTOMER_ID = "cust_test_sprint8"


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear in-memory stores before each test."""
    intent_router._departments.clear()
    intent_router._rules.clear()
    conn_svc._connectors.clear()
    conn_svc._events.clear()
    yield
    intent_router._departments.clear()
    intent_router._rules.clear()
    conn_svc._connectors.clear()
    conn_svc._events.clear()


# ──────────────────────────────────────────────────────────────────────
# Department model tests
# ──────────────────────────────────────────────────────────────────────

class TestDepartmentModel:
    def test_department_defaults(self):
        dept = Department(customer_id=CUSTOMER_ID, name="Sales")
        assert dept.name == "Sales"
        assert dept.customer_id == CUSTOMER_ID
        assert dept.enabled is True
        assert dept.is_default is False
        assert dept.priority == 0
        assert dept.intent_keywords == []
        assert dept.id  # should have auto-generated ID

    def test_department_with_keywords(self):
        dept = Department(
            customer_id=CUSTOMER_ID,
            name="Billing",
            intent_keywords=["bill", "invoice", "payment"],
        )
        assert len(dept.intent_keywords) == 3
        assert "bill" in dept.intent_keywords

    def test_routing_rule_defaults(self):
        rule = RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Sales keywords",
            department_id="dept_1",
            match_type="keyword",
            match_value="buy,purchase",
        )
        assert rule.match_type == "keyword"
        assert rule.enabled is True
        assert rule.priority == 0

    def test_routing_result_defaults(self):
        result = RoutingResult(department_name="Support")
        assert result.confidence == 0.0
        assert result.fallback is False
        assert result.matched_keywords == []

    def test_routing_config_defaults(self):
        config = RoutingConfig(customer_id=CUSTOMER_ID)
        assert config.use_ai_intent is True
        assert config.max_classification_attempts == 2
        assert len(config.departments) == 0


# ──────────────────────────────────────────────────────────────────────
# Department CRUD tests
# ──────────────────────────────────────────────────────────────────────

class TestDepartmentCRUD:
    def test_create_department(self):
        dept = Department(customer_id=CUSTOMER_ID, name="Sales", priority=1)
        result = intent_router.create_department(dept)
        assert result.name == "Sales"
        assert intent_router.get_department(dept.id) is not None

    def test_list_departments(self):
        intent_router.create_department(Department(customer_id=CUSTOMER_ID, name="Sales", priority=2))
        intent_router.create_department(Department(customer_id=CUSTOMER_ID, name="Support", priority=1))
        intent_router.create_department(Department(customer_id="other", name="Other"))
        depts = intent_router.list_departments(CUSTOMER_ID)
        assert len(depts) == 2
        # sorted by priority
        assert depts[0].name == "Support"
        assert depts[1].name == "Sales"

    def test_update_department(self):
        dept = Department(customer_id=CUSTOMER_ID, name="Sales")
        intent_router.create_department(dept)
        updated = intent_router.update_department(dept.id, {"name": "Enterprise Sales", "priority": 5})
        assert updated.name == "Enterprise Sales"
        assert updated.priority == 5

    def test_update_nonexistent_department(self):
        result = intent_router.update_department("nonexistent", {"name": "Nope"})
        assert result is None

    def test_delete_department(self):
        dept = Department(customer_id=CUSTOMER_ID, name="Sales")
        intent_router.create_department(dept)
        assert intent_router.delete_department(dept.id) is True
        assert intent_router.get_department(dept.id) is None

    def test_delete_nonexistent_department(self):
        assert intent_router.delete_department("nonexistent") is False

    def test_create_default_departments(self):
        depts = intent_router.create_default_departments(CUSTOMER_ID)
        assert len(depts) == 3
        names = [d.name for d in depts]
        assert "Sales" in names
        assert "Support" in names
        assert "Billing" in names
        # Support should be default
        support = next(d for d in depts if d.name == "Support")
        assert support.is_default is True


# ──────────────────────────────────────────────────────────────────────
# Routing Rule CRUD tests
# ──────────────────────────────────────────────────────────────────────

class TestRoutingRuleCRUD:
    def test_create_rule(self):
        rule = RoutingRule(customer_id=CUSTOMER_ID, name="Sales keywords", department_id="d1")
        result = intent_router.create_rule(rule)
        assert result.name == "Sales keywords"
        assert intent_router.get_rule(rule.id) is not None

    def test_list_rules(self):
        intent_router.create_rule(RoutingRule(customer_id=CUSTOMER_ID, name="R1", department_id="d1", priority=2))
        intent_router.create_rule(RoutingRule(customer_id=CUSTOMER_ID, name="R2", department_id="d2", priority=1))
        rules = intent_router.list_rules(CUSTOMER_ID)
        assert len(rules) == 2
        assert rules[0].name == "R2"  # lower priority first

    def test_delete_rule(self):
        rule = RoutingRule(customer_id=CUSTOMER_ID, name="R1", department_id="d1")
        intent_router.create_rule(rule)
        assert intent_router.delete_rule(rule.id) is True
        assert intent_router.get_rule(rule.id) is None


# ──────────────────────────────────────────────────────────────────────
# Intent classification tests
# ──────────────────────────────────────────────────────────────────────

class TestIntentClassification:
    def _setup_departments(self):
        depts = intent_router.create_default_departments(CUSTOMER_ID)
        return depts

    def test_keyword_classification_sales(self):
        depts = self._setup_departments()
        result = intent_router.classify_by_keywords("I want to buy a plan", depts)
        assert result is not None
        assert result.department_name == "Sales"
        assert result.confidence > 0

    def test_keyword_classification_support(self):
        depts = self._setup_departments()
        result = intent_router.classify_by_keywords("I need help with a problem", depts)
        assert result is not None
        assert result.department_name == "Support"

    def test_keyword_classification_billing(self):
        depts = self._setup_departments()
        result = intent_router.classify_by_keywords("I want a refund on my invoice", depts)
        assert result is not None
        assert result.department_name == "Billing"

    def test_keyword_no_match(self):
        depts = self._setup_departments()
        result = intent_router.classify_by_keywords("hello world", depts)
        assert result is None

    def test_keyword_best_match_wins(self):
        depts = self._setup_departments()
        # "problem" + "help" = 2 support keywords, "refund" = 1 billing keyword
        result = intent_router.classify_by_keywords("I have a problem and need help", depts)
        assert result is not None
        assert result.department_name == "Support"
        assert len(result.matched_keywords) == 2

    def test_rule_classification_keyword(self):
        depts = self._setup_departments()
        rule = RoutingRule(
            customer_id=CUSTOMER_ID,
            name="VIP Sales",
            department_id=depts[0].id,  # Sales
            match_type="keyword",
            match_value="enterprise,corporate",
        )
        intent_router.create_rule(rule)
        rules = intent_router.list_rules(CUSTOMER_ID)
        result = intent_router.classify_by_rules("I need an enterprise plan", rules, depts)
        assert result is not None
        assert result.department_name == "Sales"

    def test_rule_classification_regex(self):
        depts = self._setup_departments()
        billing = next(d for d in depts if d.name == "Billing")
        rule = RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Order number",
            department_id=billing.id,
            match_type="regex",
            match_value=r"order\s*#?\d+",
        )
        intent_router.create_rule(rule)
        rules = intent_router.list_rules(CUSTOMER_ID)
        result = intent_router.classify_by_rules("my order #12345 is wrong", rules, depts)
        assert result is not None
        assert result.department_name == "Billing"

    def test_rule_classification_dtmf(self):
        depts = self._setup_departments()
        sales = next(d for d in depts if d.name == "Sales")
        rule = RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Press 1",
            department_id=sales.id,
            match_type="dtmf",
            match_value="1",
        )
        intent_router.create_rule(rule)
        rules = intent_router.list_rules(CUSTOMER_ID)
        result = intent_router.classify_by_rules("1", rules, depts)
        assert result is not None
        assert result.department_name == "Sales"

    def test_rule_disabled_skipped(self):
        depts = self._setup_departments()
        rule = RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Disabled rule",
            department_id=depts[0].id,
            match_type="keyword",
            match_value="test",
            enabled=False,
        )
        intent_router.create_rule(rule)
        rules = intent_router.list_rules(CUSTOMER_ID)
        result = intent_router.classify_by_rules("test", rules, depts)
        assert result is None


# ──────────────────────────────────────────────────────────────────────
# Route call (full pipeline) tests
# ──────────────────────────────────────────────────────────────────────

class TestRouteCall:
    def test_route_call_keyword_match(self):
        intent_router.create_default_departments(CUSTOMER_ID)
        result = intent_router.route_call("I want to buy something", CUSTOMER_ID)
        assert result.department_name == "Sales"
        assert result.fallback is False

    def test_route_call_fallback_to_default(self):
        intent_router.create_default_departments(CUSTOMER_ID)
        result = intent_router.route_call("just checking in", CUSTOMER_ID)
        assert result.department_name == "Support"  # Support is default
        assert result.fallback is True

    def test_route_call_no_departments(self):
        result = intent_router.route_call("hello", CUSTOMER_ID)
        assert result.department_name == "Default"
        assert result.fallback is True

    def test_route_call_dtmf_priority(self):
        depts = intent_router.create_default_departments(CUSTOMER_ID)
        billing = next(d for d in depts if d.name == "Billing")
        intent_router.create_rule(RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Press 3 billing",
            department_id=billing.id,
            match_type="dtmf",
            match_value="3",
        ))
        # DTMF should take priority over text keywords
        result = intent_router.route_call("I want to buy", CUSTOMER_ID, dtmf_input="3")
        assert result.department_name == "Billing"

    def test_route_call_rule_before_keywords(self):
        depts = intent_router.create_default_departments(CUSTOMER_ID)
        billing = next(d for d in depts if d.name == "Billing")
        intent_router.create_rule(RoutingRule(
            customer_id=CUSTOMER_ID,
            name="Urgent billing",
            department_id=billing.id,
            match_type="keyword",
            match_value="urgent",
        ))
        # "urgent" matches the rule → Billing, even though "buy" matches Sales keywords
        result = intent_router.route_call("urgent purchase help", CUSTOMER_ID)
        assert result.department_name == "Billing"


# ──────────────────────────────────────────────────────────────────────
# Connector model tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorModel:
    def test_connector_defaults(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="My Twilio")
        assert conn.connector_type == ConnectorType.TWILIO
        assert conn.status == ConnectorStatus.INACTIVE
        assert conn.total_calls_routed == 0
        assert conn.config == {}
        assert conn.department_mappings == {}

    def test_connector_types(self):
        for ct in ConnectorType:
            conn = Connector(customer_id=CUSTOMER_ID, name=ct.value, connector_type=ct)
            assert conn.connector_type == ct

    def test_connector_statuses(self):
        for st in ConnectorStatus:
            conn = Connector(customer_id=CUSTOMER_ID, name="test", status=st)
            assert conn.status == st

    def test_connector_event_defaults(self):
        ev = ConnectorEvent(connector_id="conn_1", event_type="connected", message="OK")
        assert ev.event_type == "connected"
        assert ev.metadata == {}
        assert ev.id


# ──────────────────────────────────────────────────────────────────────
# Connector CRUD tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorCRUD:
    def test_create_connector(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="Twilio Prod")
        result = conn_svc.create_connector(conn)
        assert result.name == "Twilio Prod"
        assert conn_svc.get_connector(conn.id) is not None

    def test_list_connectors(self):
        conn_svc.create_connector(Connector(customer_id=CUSTOMER_ID, name="C1"))
        conn_svc.create_connector(Connector(customer_id=CUSTOMER_ID, name="C2"))
        conn_svc.create_connector(Connector(customer_id="other", name="C3"))
        conns = conn_svc.list_connectors(CUSTOMER_ID)
        assert len(conns) == 2

    def test_update_connector(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="Old Name")
        conn_svc.create_connector(conn)
        updated = conn_svc.update_connector(conn.id, {"name": "New Name"})
        assert updated.name == "New Name"

    def test_update_nonexistent(self):
        result = conn_svc.update_connector("nonexistent", {"name": "Nope"})
        assert result is None

    def test_delete_connector(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="To Delete")
        conn_svc.create_connector(conn)
        assert conn_svc.delete_connector(conn.id) is True
        assert conn_svc.get_connector(conn.id) is None

    def test_delete_nonexistent(self):
        assert conn_svc.delete_connector("nonexistent") is False


# ──────────────────────────────────────────────────────────────────────
# Connector activation & config validation tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorActivation:
    def test_activate_twilio_valid(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Twilio",
            connector_type=ConnectorType.TWILIO,
            config={"account_sid": "AC123", "auth_token": "tok123"},
        )
        conn_svc.create_connector(conn)
        result = conn_svc.activate_connector(conn.id)
        assert result.status == ConnectorStatus.ACTIVE
        assert result.error_message == ""

    def test_activate_twilio_missing_config(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Twilio Bad",
            connector_type=ConnectorType.TWILIO,
            config={},
        )
        conn_svc.create_connector(conn)
        result = conn_svc.activate_connector(conn.id)
        assert result.status == ConnectorStatus.ERROR
        assert "account_sid" in result.error_message

    def test_activate_genesys_valid(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Genesys",
            connector_type=ConnectorType.GENESYS,
            config={"org_id": "o1", "client_id": "c1", "client_secret": "s1", "region": "us-east-1"},
        )
        conn_svc.create_connector(conn)
        result = conn_svc.activate_connector(conn.id)
        assert result.status == ConnectorStatus.ACTIVE

    def test_activate_genesys_missing_fields(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Genesys Bad",
            connector_type=ConnectorType.GENESYS,
            config={"org_id": "o1"},
        )
        conn_svc.create_connector(conn)
        result = conn_svc.activate_connector(conn.id)
        assert result.status == ConnectorStatus.ERROR
        assert "client_id" in result.error_message

    def test_activate_amazon_connect_valid(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Amazon",
            connector_type=ConnectorType.AMAZON_CONNECT,
            config={"instance_id": "i-123", "region": "us-west-2"},
        )
        conn_svc.create_connector(conn)
        result = conn_svc.activate_connector(conn.id)
        assert result.status == ConnectorStatus.ACTIVE

    def test_activate_nonexistent(self):
        result = conn_svc.activate_connector("nonexistent")
        assert result is None

    def test_deactivate_connector(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1", config={"account_sid": "a", "auth_token": "b"})
        conn_svc.create_connector(conn)
        conn_svc.activate_connector(conn.id)
        result = conn_svc.deactivate_connector(conn.id)
        assert result.status == ConnectorStatus.INACTIVE

    def test_deactivate_nonexistent(self):
        result = conn_svc.deactivate_connector("nonexistent")
        assert result is None

    def test_validate_avaya_config(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            connector_type=ConnectorType.AVAYA,
            config={"host": "avaya.local", "port": "5060"},
        )
        errors = conn_svc.validate_config(conn)
        assert errors == []

    def test_validate_cisco_config(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            connector_type=ConnectorType.CISCO,
            config={},
        )
        errors = conn_svc.validate_config(conn)
        assert "finesse_url" in errors[0]

    def test_validate_five9_config(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            connector_type=ConnectorType.FIVE9,
            config={"domain": "five9.com", "username": "admin"},
        )
        errors = conn_svc.validate_config(conn)
        assert errors == []

    def test_validate_generic_sip_config(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            connector_type=ConnectorType.GENERIC_SIP,
            config={},
        )
        errors = conn_svc.validate_config(conn)
        assert any("sip_server" in e for e in errors)


# ──────────────────────────────────────────────────────────────────────
# Queue mapping & call routing tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorRouting:
    def _make_active_connector(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Test Conn",
            connector_type=ConnectorType.TWILIO,
            config={"account_sid": "AC1", "auth_token": "tok1"},
        )
        conn_svc.create_connector(conn)
        conn_svc.activate_connector(conn.id)
        return conn

    def test_map_queue_to_department(self):
        conn = self._make_active_connector()
        result = conn_svc.map_queue_to_department(conn.id, "queue_sales", "dept_sales")
        assert result is not None
        assert result.department_mappings["queue_sales"] == "dept_sales"

    def test_resolve_department(self):
        conn = self._make_active_connector()
        conn_svc.map_queue_to_department(conn.id, "q1", "d1")
        assert conn_svc.resolve_department(conn.id, "q1") == "d1"
        assert conn_svc.resolve_department(conn.id, "unknown") is None

    def test_route_incoming_call_success(self):
        conn = self._make_active_connector()
        conn_svc.map_queue_to_department(conn.id, "q_support", "dept_support")
        result = conn_svc.route_incoming_call(conn.id, "q_support", "+15551234567")
        assert result["routed"] is True
        assert result["department_id"] == "dept_support"
        assert result["caller_number"] == "+15551234567"
        # Check stats incremented
        updated = conn_svc.get_connector(conn.id)
        assert updated.total_calls_routed == 1

    def test_route_incoming_call_no_mapping(self):
        conn = self._make_active_connector()
        result = conn_svc.route_incoming_call(conn.id, "unknown_queue", "+15551234567")
        assert result["routed"] is False
        assert "No department mapping" in result["error"]

    def test_route_incoming_call_inactive_connector(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Inactive",
            status=ConnectorStatus.INACTIVE,
        )
        conn_svc.create_connector(conn)
        result = conn_svc.route_incoming_call(conn.id, "q1", "+15551234567")
        assert result["routed"] is False
        assert "not active" in result["error"]


# ──────────────────────────────────────────────────────────────────────
# Connector event logging tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorEvents:
    def test_log_event(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1")
        conn_svc.create_connector(conn)
        ev = conn_svc.log_event(conn.id, "test", "Test event")
        assert ev.event_type == "test"
        assert ev.message == "Test event"

    def test_get_events(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1")
        conn_svc.create_connector(conn)
        # create_connector already logs a "created" event
        events = conn_svc.get_events(conn.id)
        assert len(events) >= 1
        assert events[0].event_type == "created"

    def test_events_limit(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1")
        conn_svc.create_connector(conn)
        for i in range(10):
            conn_svc.log_event(conn.id, "test", f"Event {i}")
        events = conn_svc.get_events(conn.id, limit=5)
        assert len(events) == 5

    def test_events_trimmed_at_max(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1")
        conn_svc.create_connector(conn)
        for i in range(150):
            conn_svc.log_event(conn.id, "test", f"Event {i}")
        # Should be trimmed to MAX_EVENTS_PER_CONNECTOR
        assert len(conn_svc._events[conn.id]) <= conn_svc.MAX_EVENTS_PER_CONNECTOR

    def test_log_event_with_metadata(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="C1")
        conn_svc.create_connector(conn)
        ev = conn_svc.log_event(conn.id, "call_routed", "Routed call", {"caller": "+15551234567"})
        assert ev.metadata["caller"] == "+15551234567"


# ──────────────────────────────────────────────────────────────────────
# Connector health check tests
# ──────────────────────────────────────────────────────────────────────

class TestConnectorHealth:
    def test_health_active_connector(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Active Conn",
            connector_type=ConnectorType.TWILIO,
            config={"account_sid": "AC1", "auth_token": "tok1"},
        )
        conn_svc.create_connector(conn)
        conn_svc.activate_connector(conn.id)
        health = conn_svc.get_health(conn.id)
        assert health["healthy"] is True
        assert health["status"] == ConnectorStatus.ACTIVE
        assert health["name"] == "Active Conn"

    def test_health_inactive_connector(self):
        conn = Connector(customer_id=CUSTOMER_ID, name="Inactive")
        conn_svc.create_connector(conn)
        health = conn_svc.get_health(conn.id)
        assert health["healthy"] is False

    def test_health_nonexistent(self):
        health = conn_svc.get_health("nonexistent")
        assert health["healthy"] is False
        assert "not found" in health["error"]

    def test_health_with_calls(self):
        conn = Connector(
            customer_id=CUSTOMER_ID,
            name="Busy Conn",
            connector_type=ConnectorType.TWILIO,
            config={"account_sid": "AC1", "auth_token": "tok1"},
        )
        conn_svc.create_connector(conn)
        conn_svc.activate_connector(conn.id)
        conn_svc.map_queue_to_department(conn.id, "q1", "d1")
        conn_svc.route_incoming_call(conn.id, "q1", "+15551234567")
        conn_svc.route_incoming_call(conn.id, "q1", "+15559876543")
        health = conn_svc.get_health(conn.id)
        assert health["total_calls_routed"] == 2
        assert health["last_active_at"] is not None
