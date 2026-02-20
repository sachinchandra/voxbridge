"""Playground service — in-browser agent testing via text chat.

Lets users test their AI agent configurations before deploying to phone lines.
Simulates a conversation using the agent's LLM provider, system prompt, tools,
and knowledge base — everything except actual telephony/audio.

The playground uses a lightweight in-memory session store (no DB persistence
needed for ephemeral test chats). Each session maintains conversation context
and feeds it to the configured LLM.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.models.database import (
    PlaygroundMessage,
    PlaygroundSession,
)


# ──────────────────────────────────────────────────────────────────
# In-memory session store
# ──────────────────────────────────────────────────────────────────

_sessions: dict[str, PlaygroundSession] = {}

MAX_SESSIONS = 500  # per-process cap to prevent memory leaks
MAX_TURNS = 50  # max back-and-forth per session


def get_session(session_id: str) -> PlaygroundSession | None:
    return _sessions.get(session_id)


def create_session(customer_id: str, agent_id: str, agent_name: str) -> PlaygroundSession:
    """Create a new playground session."""
    # Evict oldest sessions if at capacity
    if len(_sessions) >= MAX_SESSIONS:
        oldest_key = min(_sessions, key=lambda k: _sessions[k].started_at)
        del _sessions[oldest_key]

    session = PlaygroundSession(
        customer_id=customer_id,
        agent_id=agent_id,
        agent_name=agent_name,
    )
    _sessions[session.id] = session
    logger.info(f"Playground session {session.id} created for agent {agent_id}")
    return session


def end_session(session_id: str) -> PlaygroundSession | None:
    """Mark session as completed."""
    session = _sessions.get(session_id)
    if session:
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)
    return session


def delete_session(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None


# ──────────────────────────────────────────────────────────────────
# LLM interaction (simulated for now, uses real API when keys exist)
# ──────────────────────────────────────────────────────────────────

def build_messages(
    system_prompt: str,
    first_message: str,
    history: list[PlaygroundMessage],
    user_message: str,
) -> list[dict[str, str]]:
    """Build the message array for the LLM call."""
    messages: list[dict[str, str]] = []

    # System prompt
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Replay history
    for msg in history:
        if msg.role in ("user", "assistant", "system"):
            messages.append({"role": msg.role, "content": msg.content})

    # If this is the first user message and agent has a first_message, include it
    if not history and first_message:
        messages.append({"role": "assistant", "content": first_message})

    # Current user message
    if user_message:
        messages.append({"role": "user", "content": user_message})

    return messages


async def generate_reply_openai(
    messages: list[dict[str, str]],
    model: str = "gpt-4o-mini",
    tools: list[dict] | None = None,
    llm_config: dict | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Call OpenAI Chat Completion API.

    Returns: {reply, tool_calls, tokens_used, latency_ms}
    """
    start = time.time()

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key) if api_key else openai.AsyncOpenAI()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": (llm_config or {}).get("max_tokens", 500),
            "temperature": (llm_config or {}).get("temperature", 0.7),
        }

        # Add tools if agent has function calling configured
        if tools:
            openai_tools = []
            for t in tools:
                if t.get("name") and t.get("endpoint"):
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                        },
                    })
            if openai_tools:
                kwargs["tools"] = openai_tools

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        latency_ms = int((time.time() - start) * 1000)

        result: dict[str, Any] = {
            "reply": choice.message.content or "",
            "tool_calls": [],
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "latency_ms": latency_ms,
        }

        # Handle tool calls
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                result["tool_calls"].append({
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

        return result

    except ImportError:
        latency_ms = int((time.time() - start) * 1000)
        return _simulated_reply(messages, latency_ms)
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.warning(f"OpenAI playground call failed: {e}, using simulation")
        return _simulated_reply(messages, latency_ms)


async def generate_reply_anthropic(
    messages: list[dict[str, str]],
    model: str = "claude-sonnet-4-20250514",
    tools: list[dict] | None = None,
    llm_config: dict | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Call Anthropic Messages API.

    Returns: {reply, tool_calls, tokens_used, latency_ms}
    """
    start = time.time()

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

        # Separate system from conversation messages
        system_content = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n"
            else:
                chat_messages.append(m)

        # Ensure messages alternate user/assistant
        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "Hello"})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": (llm_config or {}).get("max_tokens", 500),
        }
        if system_content.strip():
            kwargs["system"] = system_content.strip()

        # Add tools
        if tools:
            anthropic_tools = []
            for t in tools:
                if t.get("name") and t.get("endpoint"):
                    anthropic_tools.append({
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                    })
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

        response = await client.messages.create(**kwargs)
        latency_ms = int((time.time() - start) * 1000)

        reply = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                reply += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "arguments": str(block.input),
                })

        return {
            "reply": reply,
            "tool_calls": tool_calls,
            "tokens_used": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
            "latency_ms": latency_ms,
        }

    except ImportError:
        latency_ms = int((time.time() - start) * 1000)
        return _simulated_reply(messages, latency_ms)
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.warning(f"Anthropic playground call failed: {e}, using simulation")
        return _simulated_reply(messages, latency_ms)


def _simulated_reply(messages: list[dict[str, str]], latency_ms: int = 50) -> dict[str, Any]:
    """Fallback simulated reply when no LLM API key is available.

    Generates a contextual mock response so the playground UI still works.
    """
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"].lower()
            break

    # Simple keyword-based responses
    if any(w in last_user for w in ["hello", "hi", "hey"]):
        reply = "Hello! Thanks for calling. How can I help you today?"
    elif any(w in last_user for w in ["order", "status", "tracking"]):
        reply = "I'd be happy to help you with your order. Could you please provide your order number so I can look that up?"
    elif any(w in last_user for w in ["refund", "return", "money back"]):
        reply = "I understand you'd like a refund. Let me check our return policy for you. Can you tell me which product this is regarding?"
    elif any(w in last_user for w in ["speak", "human", "agent", "manager", "supervisor"]):
        reply = "I understand you'd like to speak with a human agent. Let me transfer you now. One moment please."
    elif any(w in last_user for w in ["thank", "bye", "goodbye"]):
        reply = "Thank you for contacting us! Is there anything else I can help you with before we end the call?"
    elif any(w in last_user for w in ["appointment", "schedule", "book"]):
        reply = "I can help you schedule an appointment. What date and time works best for you?"
    elif any(w in last_user for w in ["price", "cost", "how much"]):
        reply = "Great question about pricing! Let me look that up for you. Which specific product or service are you interested in?"
    elif any(w in last_user for w in ["problem", "issue", "broken", "not working"]):
        reply = "I'm sorry to hear you're experiencing an issue. Can you describe the problem in more detail so I can help resolve it?"
    else:
        reply = "I understand. Let me look into that for you. Could you provide a bit more detail about what you need?"

    return {
        "reply": reply,
        "tool_calls": [],
        "tokens_used": len(reply.split()) * 2,  # rough estimate
        "latency_ms": latency_ms,
    }


async def process_turn(
    session: PlaygroundSession,
    user_message: str,
    agent_config: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """Process a single conversation turn in the playground.

    Args:
        session: The active playground session.
        user_message: The user's text input.
        agent_config: Full agent configuration dict.
        api_key: Optional LLM API key.

    Returns:
        {reply, tool_calls, tokens_used, latency_ms, done}
    """
    if session.total_turns >= MAX_TURNS:
        return {
            "reply": "[Session limit reached — max 50 turns per playground session]",
            "tool_calls": [],
            "tokens_used": 0,
            "latency_ms": 0,
            "done": True,
        }

    # Build message history
    messages = build_messages(
        system_prompt=agent_config.get("system_prompt", ""),
        first_message=agent_config.get("first_message", ""),
        history=session.messages,
        user_message=user_message,
    )

    # Record user message
    now = time.time()
    session.messages.append(PlaygroundMessage(
        role="user",
        content=user_message,
        timestamp=now,
    ))

    # Call LLM based on provider
    provider = agent_config.get("llm_provider", "openai")
    model = agent_config.get("llm_model", "gpt-4o-mini")
    tools = agent_config.get("tools", [])
    llm_config = agent_config.get("llm_config", {})

    if provider == "anthropic":
        result = await generate_reply_anthropic(
            messages=messages,
            model=model,
            tools=tools,
            llm_config=llm_config,
            api_key=api_key,
        )
    else:
        result = await generate_reply_openai(
            messages=messages,
            model=model,
            tools=tools,
            llm_config=llm_config,
            api_key=api_key,
        )

    # Record assistant response
    session.messages.append(PlaygroundMessage(
        role="assistant",
        content=result["reply"],
        timestamp=time.time(),
        latency_ms=result["latency_ms"],
        tool_call=result["tool_calls"][0] if result["tool_calls"] else None,
    ))

    session.total_turns += 1
    session.total_tokens += result["tokens_used"]
    # Rough cost: $0.003/1K tokens for gpt-4o-mini
    session.estimated_cost_cents = int(session.total_tokens * 0.0003)

    # Check if conversation should end
    done = False
    end_phrases = agent_config.get("end_call_phrases", [])
    reply_lower = result["reply"].lower()
    if any(phrase.lower() in reply_lower for phrase in end_phrases if phrase):
        done = True

    result["done"] = done
    return result
