"""OpenAI GPT streaming LLM provider.

Uses the OpenAI Chat Completions API with streaming for real-time
response generation. Supports function/tool calling for agent actions.

Requires: pip install openai
API key: https://platform.openai.com/
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from loguru import logger

from voxbridge.providers.base import BaseLLM, LLMChunk, LLMToolCall, Message

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore


class OpenAILLM(BaseLLM):
    """OpenAI GPT streaming LLM provider.

    Connects to OpenAI's Chat Completions API and streams responses.
    Supports tool/function calling for agent actions.

    Args:
        api_key: OpenAI API key.
        model: Model identifier (default: "gpt-4o-mini").
        base_url: Optional custom API base URL (for Azure, local models, etc.).
        organization: Optional OpenAI organization ID.
        max_retries: Max API retries (default: 2).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        organization: str | None = None,
        max_retries: int = 2,
    ):
        if AsyncOpenAI is None:
            raise ImportError(
                "openai is required for OpenAILLM. "
                "Install with: pip install openai"
            )

        self._api_key = api_key
        self._model_name = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            max_retries=max_retries,
        )

    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a response from OpenAI GPT.

        Converts Message objects to OpenAI format, streams the response,
        and yields LLMChunk objects with text and/or tool call data.
        """
        # Convert messages to OpenAI format
        oai_messages = self._convert_messages(messages)

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug(
            f"OpenAI request: model={self._model_name}, "
            f"messages={len(messages)}, tools={len(tools or [])}"
        )

        try:
            stream = await self._client.chat.completions.create(**kwargs)

            # Track accumulated tool call data
            tool_calls_acc: dict[int, dict[str, str]] = {}
            full_text = ""

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

                # Handle text content
                if delta and delta.content:
                    full_text += delta.content
                    yield LLMChunk(text=delta.content)

                # Handle tool calls
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_acc[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

                        # Yield partial tool call info
                        yield LLMChunk(
                            tool_call_id=tool_calls_acc[idx]["id"],
                            tool_name=tool_calls_acc[idx]["name"],
                            tool_arguments=tool_calls_acc[idx]["arguments"],
                        )

                # Handle usage (final chunk)
                if chunk.usage:
                    yield LLMChunk(
                        is_final=True,
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                    )

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield LLMChunk(text=f"[Error: {e}]", is_final=True)

    async def close(self) -> None:
        """Close the OpenAI client."""
        await self._client.close()

    @property
    def model(self) -> str:
        return self._model_name

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert VoxBridge Message objects to OpenAI format."""
        oai_messages = []

        for msg in messages:
            oai_msg: dict[str, Any] = {"role": msg.role}

            if msg.role == "tool":
                oai_msg["content"] = msg.content
                oai_msg["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    oai_msg["name"] = msg.name
            elif msg.tool_calls:
                # Assistant message with tool calls
                oai_msg["content"] = msg.content or None
                oai_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            else:
                oai_msg["content"] = msg.content

            oai_messages.append(oai_msg)

        return oai_messages
