"""VoxBridge Platform client for SaaS integration.

This module handles API key validation and usage reporting when the SDK
is used with the VoxBridge SaaS platform.

Usage:
    bridge = VoxBridge({
        "provider": "twilio",
        "bot_url": "ws://localhost:9000/ws",
        "api_key": "vxb_your_api_key_here",
        "platform_url": "https://api.voxbridge.io",
    })
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from loguru import logger


DEFAULT_PLATFORM_URL = "https://api.voxbridge.io"


class PlatformClient:
    """Client for the VoxBridge SaaS platform.

    Handles:
    - API key validation on startup
    - Usage reporting at the end of each call
    - Plan limit checking
    """

    def __init__(
        self,
        api_key: str,
        platform_url: str = DEFAULT_PLATFORM_URL,
        validate_on_start: bool = True,
        report_usage: bool = True,
    ) -> None:
        self.api_key = api_key
        self.platform_url = platform_url.rstrip("/")
        self.validate_on_start = validate_on_start
        self.report_usage = report_usage

        # Cached validation result
        self._customer_id: str | None = None
        self._plan: str | None = None
        self._validated: bool = False
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Content-Type": "application/json"},
            )
        return self._session

    async def validate(self) -> bool:
        """Validate the API key against the platform.

        Returns True if valid, False otherwise.
        """
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.platform_url}/api/v1/usage/validate-key",
                json={"api_key": self.api_key},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._customer_id = data.get("customer_id")
                    self._plan = data.get("plan")
                    self._validated = True
                    logger.info(
                        f"VoxBridge Platform: API key validated "
                        f"(plan={self._plan}, "
                        f"remaining={data.get('minutes_remaining')} min)"
                    )
                    return data.get("allowed", True)
                else:
                    error = await resp.text()
                    logger.error(f"VoxBridge Platform: API key validation failed: {error}")
                    return False
        except Exception as e:
            logger.warning(f"VoxBridge Platform: Could not reach platform: {e}")
            # Allow operation if platform is unreachable (graceful degradation)
            return True

    async def report_call(
        self,
        session_id: str,
        call_id: str = "",
        provider: str = "",
        duration_seconds: float = 0.0,
        audio_bytes_in: int = 0,
        audio_bytes_out: int = 0,
        status: str = "completed",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Report call usage to the platform."""
        if not self.report_usage:
            return

        try:
            session = await self._get_session()
            payload = {
                "api_key": self.api_key,
                "session_id": session_id,
                "call_id": call_id,
                "provider": provider,
                "duration_seconds": duration_seconds,
                "audio_bytes_in": audio_bytes_in,
                "audio_bytes_out": audio_bytes_out,
                "status": status,
                "metadata": metadata or {},
            }

            async with session.post(
                f"{self.platform_url}/api/v1/usage/report",
                json=payload,
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    logger.debug(
                        f"VoxBridge Platform: Usage reported "
                        f"(session={session_id}, "
                        f"duration={duration_seconds:.1f}s, "
                        f"remaining={data.get('minutes_remaining')} min)"
                    )
                elif resp.status == 429:
                    logger.warning("VoxBridge Platform: Usage limit exceeded!")
                else:
                    error = await resp.text()
                    logger.warning(f"VoxBridge Platform: Usage report failed: {error}")

        except Exception as e:
            logger.warning(f"VoxBridge Platform: Could not report usage: {e}")

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    @property
    def is_validated(self) -> bool:
        return self._validated

    @property
    def customer_id(self) -> str | None:
        return self._customer_id

    @property
    def plan(self) -> str | None:
        return self._plan
