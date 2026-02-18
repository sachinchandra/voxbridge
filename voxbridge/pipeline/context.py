"""Conversation context management for the AI pipeline.

Manages the message history sent to the LLM, including system prompt,
conversation turns, tool calls/results, and context window management.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from voxbridge.providers.base import LLMToolCall, Message


@dataclass
class ConversationContext:
    """Manages conversation history for LLM interactions.

    Handles:
    - System prompt configuration
    - Message history with automatic truncation
    - Tool call / result tracking
    - First message injection (agent greeting)
    - Context window management to stay within token limits

    Args:
        system_prompt: The agent's system prompt.
        first_message: Optional greeting message from the agent.
        max_messages: Maximum messages to keep in history (default: 50).
        max_context_chars: Approximate max chars in context (default: 32000).
        tools: Optional list of tool definitions.
    """

    system_prompt: str = ""
    first_message: str = ""
    max_messages: int = 50
    max_context_chars: int = 32000
    tools: list[dict[str, Any]] = field(default_factory=list)

    # Internal
    _messages: list[Message] = field(default_factory=list)
    _total_input_tokens: int = 0
    _total_output_tokens: int = 0

    def __post_init__(self) -> None:
        """Initialize with system prompt."""
        if self.system_prompt:
            self._messages.append(
                Message(role="system", content=self.system_prompt)
            )
        if self.first_message:
            self._messages.append(
                Message(role="assistant", content=self.first_message)
            )

    def add_user_message(self, text: str) -> None:
        """Add a user (caller) message to the conversation."""
        self._messages.append(Message(role="user", content=text))
        self._trim_context()
        logger.debug(f"Context: added user message ({len(text)} chars)")

    def add_assistant_message(self, text: str) -> None:
        """Add an assistant (AI agent) message to the conversation."""
        if text.strip():
            self._messages.append(Message(role="assistant", content=text))
            self._trim_context()

    def add_assistant_tool_calls(
        self, text: str, tool_calls: list[LLMToolCall]
    ) -> None:
        """Add an assistant message with tool calls."""
        self._messages.append(
            Message(role="assistant", content=text, tool_calls=tool_calls)
        )
        self._trim_context()

    def add_tool_result(
        self, tool_call_id: str, tool_name: str, result: Any
    ) -> None:
        """Add a tool/function result to the conversation."""
        content = json.dumps(result) if not isinstance(result, str) else result
        self._messages.append(
            Message(
                role="tool",
                content=content,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
        )
        self._trim_context()
        logger.debug(f"Context: added tool result for {tool_name}")

    def get_messages(self) -> list[Message]:
        """Get the current message list for LLM input."""
        return list(self._messages)

    def get_tools(self) -> list[dict[str, Any]] | None:
        """Get tool definitions, or None if no tools configured."""
        return self.tools if self.tools else None

    def update_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Track cumulative token usage."""
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

    @property
    def total_tokens(self) -> int:
        """Total tokens used across all LLM calls in this conversation."""
        return self._total_input_tokens + self._total_output_tokens

    @property
    def message_count(self) -> int:
        """Number of messages in the conversation."""
        return len(self._messages)

    @property
    def last_user_message(self) -> str:
        """Get the most recent user message text."""
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg.content
        return ""

    @property
    def last_assistant_message(self) -> str:
        """Get the most recent assistant message text."""
        for msg in reversed(self._messages):
            if msg.role == "assistant":
                return msg.content
        return ""

    def get_transcript(self) -> list[dict[str, str]]:
        """Get a simplified transcript for storage/display.

        Returns a list of {role, content} dicts (excludes system prompt and tool messages).
        """
        transcript = []
        for msg in self._messages:
            if msg.role in ("user", "assistant") and msg.content:
                transcript.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        return transcript

    def clear(self) -> None:
        """Clear all messages except the system prompt."""
        system_msgs = [m for m in self._messages if m.role == "system"]
        self._messages = system_msgs

    def _trim_context(self) -> None:
        """Trim context to stay within limits.

        Preserves the system prompt and the most recent messages.
        Removes oldest messages (after system prompt) to fit within limits.
        """
        # Trim by message count
        if len(self._messages) > self.max_messages:
            # Keep system prompt(s) + last N messages
            system_msgs = [m for m in self._messages if m.role == "system"]
            non_system = [m for m in self._messages if m.role != "system"]
            keep_count = self.max_messages - len(system_msgs)
            self._messages = system_msgs + non_system[-keep_count:]
            logger.debug(f"Context trimmed to {len(self._messages)} messages")

        # Trim by approximate character count
        total_chars = sum(len(m.content) for m in self._messages)
        while total_chars > self.max_context_chars and len(self._messages) > 2:
            # Find first non-system message and remove it
            for i, msg in enumerate(self._messages):
                if msg.role != "system":
                    removed = self._messages.pop(i)
                    total_chars -= len(removed.content)
                    break
            else:
                break
