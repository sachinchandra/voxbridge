"""Tool executor service for AI agent function calling.

When an LLM decides to call a tool during a call, this service:
1. Looks up the tool definition from the agent's configuration
2. Makes an HTTP request to the customer's API endpoint
3. Returns the result back to the LLM pipeline

Tools are defined in the agent's `tools` array with this format:
{
    "name": "check_order_status",
    "description": "Look up order status by order ID",
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "The order ID"}
        },
        "required": ["order_id"]
    },
    "endpoint": "https://api.myshop.com/orders/status",
    "method": "GET",
    "headers": {"Authorization": "Bearer {{api_key}}"}
}
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from loguru import logger


class ToolExecutionResult:
    """Result of a tool execution."""

    def __init__(
        self,
        name: str,
        success: bool,
        result: Any,
        duration_ms: int = 0,
        error: str = "",
    ):
        self.name = name
        self.success = success
        self.result = result
        self.duration_ms = duration_ms
        self.error = error


class ToolExecutor:
    """Executes tool/function calls by making HTTP requests to customer endpoints.

    Each agent has a list of tool definitions that map function names to
    HTTP endpoints. When the LLM calls a tool, this executor:
    1. Finds the matching tool definition
    2. Builds the HTTP request (substituting arguments)
    3. Executes the request with timeout
    4. Returns the parsed response

    Args:
        tools: List of tool definitions from the agent config.
        timeout: HTTP request timeout in seconds (default: 10).
        max_retries: Max retries on failure (default: 1).
    """

    def __init__(
        self,
        tools: list[dict[str, Any]],
        timeout: float = 10.0,
        max_retries: int = 1,
    ):
        self._tools = {t["name"]: t for t in tools if "name" in t}
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Create the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def execute(
        self, name: str, arguments: dict[str, Any]
    ) -> ToolExecutionResult:
        """Execute a tool call by name.

        Args:
            name: Tool/function name.
            arguments: Arguments dict from the LLM.

        Returns:
            ToolExecutionResult with the response data.
        """
        start_time = time.time()

        # Find tool definition
        tool_def = self._tools.get(name)
        if not tool_def:
            return ToolExecutionResult(
                name=name,
                success=False,
                result=None,
                error=f"Unknown tool: {name}",
            )

        endpoint = tool_def.get("endpoint", "")
        method = tool_def.get("method", "POST").upper()
        headers = dict(tool_def.get("headers", {}))

        if not endpoint:
            return ToolExecutionResult(
                name=name,
                success=False,
                result=None,
                error="Tool has no endpoint configured",
            )

        # Substitute template variables in endpoint
        url = self._substitute_template(endpoint, arguments)

        # Substitute template variables in headers
        for key, value in headers.items():
            if isinstance(value, str):
                headers[key] = self._substitute_template(value, arguments)

        # Ensure HTTP client exists
        if not self._client:
            await self.start()

        logger.info(f"Tool call: {name} → {method} {url}")

        try:
            if method == "GET":
                response = await self._client.get(url, params=arguments, headers=headers)
            elif method == "POST":
                response = await self._client.post(url, json=arguments, headers=headers)
            elif method == "PUT":
                response = await self._client.put(url, json=arguments, headers=headers)
            elif method == "PATCH":
                response = await self._client.patch(url, json=arguments, headers=headers)
            elif method == "DELETE":
                response = await self._client.delete(url, params=arguments, headers=headers)
            else:
                return ToolExecutionResult(
                    name=name,
                    success=False,
                    result=None,
                    error=f"Unsupported HTTP method: {method}",
                )

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse response
            try:
                result_data = response.json()
            except (json.JSONDecodeError, ValueError):
                result_data = response.text

            if response.is_success:
                logger.info(f"Tool {name} succeeded in {duration_ms}ms")
                return ToolExecutionResult(
                    name=name,
                    success=True,
                    result=result_data,
                    duration_ms=duration_ms,
                )
            else:
                logger.warning(
                    f"Tool {name} returned {response.status_code}: {result_data}"
                )
                return ToolExecutionResult(
                    name=name,
                    success=False,
                    result=result_data,
                    duration_ms=duration_ms,
                    error=f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Tool {name} timed out after {duration_ms}ms")
            return ToolExecutionResult(
                name=name,
                success=False,
                result=None,
                duration_ms=duration_ms,
                error="Request timed out",
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Tool {name} error: {e}")
            return ToolExecutionResult(
                name=name,
                success=False,
                result=None,
                duration_ms=duration_ms,
                error=str(e),
            )

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tool definitions for the LLM.

        Converts the tool configs into the format expected by the LLM.
        """
        definitions = []
        for tool in self._tools.values():
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {
                        "type": "object",
                        "properties": {},
                    }),
                },
            })
        return definitions

    @staticmethod
    def _substitute_template(template: str, values: dict[str, Any]) -> str:
        """Replace {{key}} placeholders in a template string."""
        result = template
        for key, value in values.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
