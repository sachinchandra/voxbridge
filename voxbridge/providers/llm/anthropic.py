"""Anthropic Claude streaming LLM provider.

Uses the Anthropic Messages API with streaming for real-time response
generation. Supports tool use for agent actions.

Requires: pip install anthropic
API key: https://console.anthropic.com/
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from loguru import logger

from voxbridge.providers.base import BaseLLM, LLMChunk, LLMToolCall, Message

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore


class AnthropicLLM(BaseLLM):
    """Anthropic Claude streaming LLM provider.

    Connects to the Anthropic Messages API and streams responses.
    Supports tool use for agent actions.

    Args:
        api_key: Anthropic API key.
        model: Model identifier (default: "claude-sonnet-4-20250514").
        max_retries: Max API retries (default: 2).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_retries: int = 2,
    ):
        if AsyncAnthropic is None:
            raise ImportError(
                "anthropic is required for AnthropicLLM. "
                "Install with: pip install anthropic"
            )

        self._api_key = api_key
        self._model_name = model
        self._client = AsyncAnthropic(
            api_key=api_key,
            max_retries=max_retries,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a response from Anthropic Claude.

        Converts Message objects to Anthropic format, streams the response,
        and yields LLMChunk objects with text and/or tool call data.
        """
        # Extract system message and convert the rest
        system_prompt, anthropic_messages = self._convert_messages(messages)

        # Convert tools to Anthropic format
        anthropic_tools = self._convert_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        logger.debug(
            f"Anthropic request: model={self._model_name}, "
            f"messages={len(anthropic_messages)}, tools={len(anthropic_tools or [])}"
        )

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                current_tool_id = ""
                current_tool_name = ""
                current_tool_args = ""
                input_tokens = 0
                output_tokens = 0

                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            current_tool_args = ""

                    elif event.type == "content_block_delta":
                        delta = event.delta

                        if delta.type == "text_delta":
                            yield LLMChunk(text=delta.text)

                        elif delta.type == "input_json_delta":
                            current_tool_args += delta.partial_json
                            yield LLMChunk(
                                tool_call_id=current_tool_id,
                                tool_name=current_tool_name,
                                tool_arguments=current_tool_args,
                            )

                    elif event.type == "content_block_stop":
                        # Reset tool tracking
                        current_tool_id = ""
                        current_tool_name = ""
                        current_tool_args = ""

                    elif event.type == "message_start":
                        if event.message and event.message.usage:
                            input_tokens = event.message.usage.input_tokens

                    elif event.type == "message_delta":
                        if hasattr(event, "usage") and event.usage:
                            output_tokens = event.usage.output_tokens

                # Final chunk with usage
                yield LLMChunk(
                    is_final=True,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            yield LLMChunk(text=f"[Error: {e}]", is_final=True)

    async def close(self) -> None:
        """Close the Anthropic client."""
        await self._client.close()

    @property
    def model(self) -> str:
        return self._model_name

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Convert VoxBridge Messages to Anthropic format.

        Returns (system_prompt, messages) since Anthropic handles
        system messages separately from the message array.
        """
        system_prompt = ""
        anthropic_msgs = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            if msg.role == "tool":
                # Tool results go as user messages in Anthropic format
                anthropic_msgs.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            elif msg.tool_calls:
                # Assistant message with tool use
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                anthropic_msgs.append({"role": "assistant", "content": content})
            else:
                anthropic_msgs.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system_prompt, anthropic_msgs

    def _convert_tools(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert OpenAI-format tools to Anthropic format.

        OpenAI format:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}

        Anthropic format:
            {"name": ..., "description": ..., "input_schema": {...}}
        """
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools
