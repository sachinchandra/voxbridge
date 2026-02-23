"""Conversation Flow Engine — executes visual call flows.

A flow is a directed graph of nodes (message, listen, AI respond, condition,
tool call, transfer, end) connected by edges. The engine traverses the graph
based on user input, conditions, and AI decisions.

Flows can be:
- Pure scripted (decision trees)
- Hybrid (scripted + free-form AI at specific nodes)
- A/B tested (multiple versions with traffic splitting)
"""

from __future__ import annotations

import random
import re
import time
import uuid
from typing import Any

from loguru import logger

from app.models.database import (
    AlertType,
    ConversationFlow,
    FlowEdge,
    FlowNode,
    FlowNodeType,
    FlowTestResult,
    FlowVersion,
)


# ──────────────────────────────────────────────────────────────────
# In-memory flow store (maps to DB in production)
# ──────────────────────────────────────────────────────────────────

_flows: dict[str, ConversationFlow] = {}
_versions: dict[str, list[FlowVersion]] = {}  # flow_id → versions


def save_flow(flow: ConversationFlow) -> ConversationFlow:
    """Save or update a conversation flow."""
    _flows[flow.id] = flow
    return flow


def get_flow(flow_id: str) -> ConversationFlow | None:
    return _flows.get(flow_id)


def list_flows(customer_id: str) -> list[ConversationFlow]:
    return [f for f in _flows.values() if f.customer_id == customer_id]


def delete_flow(flow_id: str) -> bool:
    removed = _flows.pop(flow_id, None)
    _versions.pop(flow_id, None)
    return removed is not None


def save_version(flow_id: str, version: FlowVersion) -> FlowVersion:
    """Save a versioned snapshot of a flow."""
    if flow_id not in _versions:
        _versions[flow_id] = []
    _versions[flow_id].append(version)
    return version


def get_versions(flow_id: str) -> list[FlowVersion]:
    return _versions.get(flow_id, [])


def select_version_by_traffic(flow_id: str) -> FlowVersion | None:
    """Select a flow version based on traffic split percentages (A/B test)."""
    versions = _versions.get(flow_id, [])
    if not versions:
        return None
    if len(versions) == 1:
        return versions[0]

    # Weighted random selection
    roll = random.randint(1, 100)
    cumulative = 0
    for v in versions:
        cumulative += v.traffic_percent
        if roll <= cumulative:
            return v
    return versions[-1]  # fallback


# ──────────────────────────────────────────────────────────────────
# Flow validation
# ──────────────────────────────────────────────────────────────────

def validate_flow(flow: ConversationFlow) -> list[str]:
    """Validate a conversation flow. Returns list of error messages."""
    errors: list[str] = []

    if not flow.nodes:
        errors.append("Flow has no nodes")
        return errors

    node_ids = {n.id for n in flow.nodes}

    # Check for start node
    start_nodes = [n for n in flow.nodes if n.type == FlowNodeType.START]
    if len(start_nodes) == 0:
        errors.append("Flow must have a START node")
    elif len(start_nodes) > 1:
        errors.append("Flow must have exactly one START node")

    # Check for at least one end node
    end_nodes = [n for n in flow.nodes if n.type == FlowNodeType.END]
    if not end_nodes:
        errors.append("Flow must have at least one END node")

    # Validate edges reference valid nodes
    for edge in flow.edges:
        if edge.source_id not in node_ids:
            errors.append(f"Edge {edge.id} references unknown source node {edge.source_id}")
        if edge.target_id not in node_ids:
            errors.append(f"Edge {edge.id} references unknown target node {edge.target_id}")

    # Check that non-end nodes have outgoing edges
    edge_sources = {e.source_id for e in flow.edges}
    for node in flow.nodes:
        if node.type not in (FlowNodeType.END, FlowNodeType.TRANSFER) and node.id not in edge_sources:
            errors.append(f"Node '{node.label or node.id}' ({node.type}) has no outgoing edges")

    # Condition nodes need at least 2 edges
    for node in flow.nodes:
        if node.type == FlowNodeType.CONDITION:
            outgoing = [e for e in flow.edges if e.source_id == node.id]
            if len(outgoing) < 2:
                errors.append(f"Condition node '{node.label or node.id}' needs at least 2 outgoing edges")

    return errors


# ──────────────────────────────────────────────────────────────────
# Flow execution (simulation)
# ──────────────────────────────────────────────────────────────────

def execute_flow(
    flow: ConversationFlow,
    test_inputs: list[str],
    max_steps: int = 50,
) -> FlowTestResult:
    """Simulate executing a flow with test inputs.

    Walks through the flow graph, consuming test_inputs as user responses.
    Returns the path taken and simulated conversation.

    Args:
        flow: The conversation flow to execute.
        test_inputs: Pre-defined user inputs for simulation.
        max_steps: Safety limit to prevent infinite loops.
    """
    start = time.time()
    path: list[str] = []
    messages: list[dict] = []
    input_idx = 0

    # Build lookup maps
    node_map = {n.id: n for n in flow.nodes}
    edges_from: dict[str, list[FlowEdge]] = {}
    for edge in flow.edges:
        edges_from.setdefault(edge.source_id, []).append(edge)

    # Find start node
    start_node = next((n for n in flow.nodes if n.type == FlowNodeType.START), None)
    if not start_node:
        return FlowTestResult(
            flow_id=flow.id,
            completed=False,
            end_reason="error",
            duration_ms=int((time.time() - start) * 1000),
        )

    current_node = start_node
    steps = 0

    while steps < max_steps:
        steps += 1
        path.append(current_node.id)

        # Process current node
        if current_node.type == FlowNodeType.START:
            pass  # just move to next

        elif current_node.type == FlowNodeType.MESSAGE:
            text = current_node.config.get("text", "")
            if text:
                messages.append({"role": "assistant", "content": text})

        elif current_node.type == FlowNodeType.LISTEN:
            if input_idx < len(test_inputs):
                user_msg = test_inputs[input_idx]
                input_idx += 1
                messages.append({"role": "user", "content": user_msg})
            else:
                # No more inputs — simulate timeout
                timeout_node_id = current_node.config.get("no_input_node_id")
                if timeout_node_id and timeout_node_id in node_map:
                    current_node = node_map[timeout_node_id]
                    continue
                return FlowTestResult(
                    flow_id=flow.id, version=flow.version, path=path,
                    messages=messages, completed=False, end_reason="timeout",
                    duration_ms=int((time.time() - start) * 1000),
                )

        elif current_node.type == FlowNodeType.AI_RESPOND:
            # In simulation, generate a placeholder AI response
            prompt_hint = current_node.config.get("system_prompt_override", "")
            messages.append({
                "role": "assistant",
                "content": f"[AI Response — {prompt_hint or 'free-form'}]",
            })

        elif current_node.type == FlowNodeType.CONDITION:
            # Evaluate condition rules against last user message
            last_user_msg = ""
            for m in reversed(messages):
                if m["role"] == "user":
                    last_user_msg = m["content"].lower()
                    break

            rules = current_node.config.get("rules", [])
            matched_target = None
            default_target = None

            for rule in rules:
                match_pattern = rule.get("match", "")
                target_id = rule.get("target_node_id", "")
                if match_pattern == "*" or match_pattern == "default":
                    default_target = target_id
                elif match_pattern and re.search(match_pattern, last_user_msg):
                    matched_target = target_id
                    break

            next_node_id = matched_target or default_target
            if next_node_id and next_node_id in node_map:
                current_node = node_map[next_node_id]
                continue
            else:
                return FlowTestResult(
                    flow_id=flow.id, version=flow.version, path=path,
                    messages=messages, completed=False, end_reason="error",
                    duration_ms=int((time.time() - start) * 1000),
                )

        elif current_node.type == FlowNodeType.TOOL_CALL:
            tool_name = current_node.config.get("tool_name", "unknown")
            messages.append({
                "role": "tool",
                "content": f"[Tool Call: {tool_name}] → simulated result",
            })

        elif current_node.type == FlowNodeType.TRANSFER:
            target = current_node.config.get("target_number", "human agent")
            messages.append({
                "role": "system",
                "content": f"[Transferring to {target}]",
            })
            return FlowTestResult(
                flow_id=flow.id, version=flow.version, path=path,
                messages=messages, completed=True, end_reason="transfer",
                duration_ms=int((time.time() - start) * 1000),
            )

        elif current_node.type == FlowNodeType.END:
            end_msg = current_node.config.get("text", "")
            if end_msg:
                messages.append({"role": "assistant", "content": end_msg})
            return FlowTestResult(
                flow_id=flow.id, version=flow.version, path=path,
                messages=messages, completed=True, end_reason="completed",
                duration_ms=int((time.time() - start) * 1000),
            )

        # Follow outgoing edge to next node
        outgoing = edges_from.get(current_node.id, [])
        if not outgoing:
            return FlowTestResult(
                flow_id=flow.id, version=flow.version, path=path,
                messages=messages, completed=False, end_reason="dead_end",
                duration_ms=int((time.time() - start) * 1000),
            )
        current_node = node_map.get(outgoing[0].target_id)
        if not current_node:
            break

    return FlowTestResult(
        flow_id=flow.id, version=flow.version, path=path,
        messages=messages, completed=False, end_reason="max_steps",
        duration_ms=int((time.time() - start) * 1000),
    )


# ──────────────────────────────────────────────────────────────────
# Helper: create a simple default flow
# ──────────────────────────────────────────────────────────────────

def create_default_flow(customer_id: str, agent_id: str, name: str = "") -> ConversationFlow:
    """Create a basic starter flow with greeting → listen → AI → end."""
    start_id = str(uuid.uuid4())
    greet_id = str(uuid.uuid4())
    listen_id = str(uuid.uuid4())
    ai_id = str(uuid.uuid4())
    end_id = str(uuid.uuid4())

    return ConversationFlow(
        customer_id=customer_id,
        agent_id=agent_id,
        name=name or "Default Flow",
        description="Basic greeting → listen → AI response → end flow",
        nodes=[
            FlowNode(id=start_id, type=FlowNodeType.START, label="Start", x=250, y=50),
            FlowNode(id=greet_id, type=FlowNodeType.MESSAGE, label="Greeting", x=250, y=150,
                     config={"text": "Hello! Thanks for calling. How can I help you today?"}),
            FlowNode(id=listen_id, type=FlowNodeType.LISTEN, label="Listen", x=250, y=250,
                     config={"timeout_seconds": 10}),
            FlowNode(id=ai_id, type=FlowNodeType.AI_RESPOND, label="AI Response", x=250, y=350,
                     config={"system_prompt_override": "", "max_tokens": 300}),
            FlowNode(id=end_id, type=FlowNodeType.END, label="End Call", x=250, y=450,
                     config={"text": "Thank you for calling! Goodbye."}),
        ],
        edges=[
            FlowEdge(source_id=start_id, target_id=greet_id),
            FlowEdge(source_id=greet_id, target_id=listen_id),
            FlowEdge(source_id=listen_id, target_id=ai_id),
            FlowEdge(source_id=ai_id, target_id=end_id),
        ],
    )
