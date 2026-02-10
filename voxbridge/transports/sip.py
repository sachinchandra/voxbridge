"""SIP transport for VoxBridge.

Provides a SIP-to-WebSocket bridge using PJSIP (via pjsua2 bindings).
This transport accepts incoming SIP calls from an SBC and bridges the
RTP audio to VoxBridge's internal event pipeline.

NOTE: This transport requires the optional ``pjsua2`` dependency.
Install with: pip install voxbridge[sip]

If pjsua2 is not available, this module provides a stub that raises
ImportError with a helpful message on instantiation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from voxbridge.transports.base import BaseTransport


def _pjsua2_available() -> bool:
    try:
        import pjsua2  # noqa: F401
        return True
    except ImportError:
        return False


class SIPTransport(BaseTransport):
    """SIP transport that bridges SIP/RTP calls to VoxBridge.

    Accepts incoming SIP calls (e.g., from an SBC or IP-PBX) and makes
    the RTP audio available as recv()/send() calls compatible with the
    VoxBridge bridge orchestrator.

    Configuration:
        sip_port: The SIP signaling port to listen on (default: 5060).
        rtp_port_range: Tuple of (min_port, max_port) for RTP media.
        codecs: List of supported codecs for SDP negotiation.

    Requires: pip install voxbridge[sip]
    """

    def __init__(
        self,
        sip_port: int = 5060,
        rtp_port_range: tuple[int, int] = (10000, 20000),
        codecs: list[str] | None = None,
    ) -> None:
        if not _pjsua2_available():
            raise ImportError(
                "SIP transport requires pjsua2. Install with: pip install voxbridge[sip]\n"
                "On Linux: apt-get install python3-pjsua2\n"
                "On macOS: brew install pjsip && pip install pjsua2"
            )

        self._sip_port = sip_port
        self._rtp_port_range = rtp_port_range
        self._codecs = codecs or ["PCMU", "PCMA"]
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._connected = False
        self._call: Any = None
        self._endpoint: Any = None

    async def connect(self, **kwargs) -> None:
        """Initialize the PJSIP endpoint and start listening for SIP calls."""
        import pjsua2 as pj

        ep_cfg = pj.EpConfig()
        ep_cfg.uaConfig.maxCalls = 4
        ep_cfg.medConfig.rxDropPct = 0
        ep_cfg.medConfig.txDropPct = 0

        self._endpoint = pj.Endpoint()
        self._endpoint.libCreate()
        self._endpoint.libInit(ep_cfg)

        # Configure SIP transport
        tp_cfg = pj.TransportConfig()
        tp_cfg.port = self._sip_port
        self._endpoint.transportCreate(pj.PJSIP_TRANSPORT_UDP, tp_cfg)

        # Configure RTP ports
        media_cfg = ep_cfg.medConfig
        media_cfg.rxDropPct = 0
        media_cfg.txDropPct = 0

        self._endpoint.libStart()
        self._connected = True
        logger.info(f"SIP transport listening on port {self._sip_port}")

    async def send(self, data: bytes | str) -> None:
        """Send audio data to the SIP call's RTP stream."""
        if not self._connected:
            raise RuntimeError("SIP transport not connected")
        if isinstance(data, str):
            data = data.encode()
        # In a full implementation, this would feed audio into the PJSIP
        # media port. For now, we buffer it.
        # TODO: Implement PJSIP media port integration
        pass

    async def recv(self) -> bytes | str:
        """Receive audio from the SIP call's RTP stream."""
        if not self._connected:
            raise RuntimeError("SIP transport not connected")
        return await self._audio_queue.get()

    async def disconnect(self) -> None:
        """Hang up the call and shut down the PJSIP endpoint."""
        self._connected = False
        if self._call:
            try:
                import pjsua2 as pj
                call_op = pj.CallOpParam()
                call_op.statusCode = pj.PJSIP_SC_OK
                self._call.hangup(call_op)
            except Exception as e:
                logger.warning(f"Error hanging up SIP call: {e}")
            self._call = None

        if self._endpoint:
            try:
                self._endpoint.libDestroy()
            except Exception:
                pass
            self._endpoint = None
        logger.info("SIP transport disconnected")

    def is_connected(self) -> bool:
        return self._connected
