"""Generic WebSocket serializer for VoxBridge.

A minimal, configurable serializer for custom voice bots that use a simple
protocol. Supports both binary audio frames (raw PCM16) and JSON control
messages. Useful as a starting point for custom integrations or for bots
that already speak a straightforward WebSocket protocol.

Protocol:
    Binary messages        -> AudioFrame (raw PCM16 by default)
    {"type": "start", ...} -> CallStarted
    {"type": "audio", ...} -> AudioFrame (base64-encoded)
    {"type": "dtmf", ...}  -> DTMFReceived
    {"type": "stop", ...}  -> CallEnded
    Outgoing AudioFrame    -> binary PCM16 bytes
    Outgoing control       -> JSON
"""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from voxbridge.core.events import (
    AnyEvent,
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    DTMFReceived,
)
from voxbridge.serializers.base import BaseSerializer


class GenericWebSocketSerializer(BaseSerializer):
    """A simple generic WebSocket serializer with configurable codec/rate.

    Designed for voice bots that use a minimal JSON+binary protocol.
    The codec and sample rate can be configured at construction time.
    """

    def __init__(
        self,
        codec: Codec = Codec.PCM16,
        rate: int = 16000,
    ) -> None:
        self._codec = codec
        self._rate = rate
        self._call_id: str = ""

    @property
    def name(self) -> str:
        return "generic"

    @property
    def audio_codec(self) -> Codec:
        return self._codec

    @property
    def sample_rate(self) -> int:
        return self._rate

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        # Binary = raw audio
        if isinstance(raw, bytes):
            return [
                AudioFrame(
                    call_id=self._call_id,
                    codec=self._codec,
                    sample_rate=self._rate,
                    channels=1,
                    data=raw,
                )
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        msg_type = msg.get("type", "")

        if msg_type == "start":
            self._call_id = msg.get("call_id", str(uuid.uuid4()))
            return [
                CallStarted(
                    call_id=self._call_id,
                    provider="generic",
                    from_number=msg.get("from", ""),
                    to_number=msg.get("to", ""),
                    metadata=msg.get("metadata", {}),
                )
            ]

        if msg_type == "audio":
            data_b64 = msg.get("data", "")
            audio_data = base64.b64decode(data_b64) if data_b64 else b""
            codec_str = msg.get("codec", self._codec.value)
            rate = msg.get("sample_rate", self._rate)
            return [
                AudioFrame(
                    call_id=self._call_id,
                    codec=Codec(codec_str),
                    sample_rate=rate,
                    channels=msg.get("channels", 1),
                    data=audio_data,
                )
            ]

        if msg_type == "dtmf":
            return [
                DTMFReceived(
                    call_id=self._call_id,
                    digit=msg.get("digit", ""),
                    duration_ms=msg.get("duration_ms", 250),
                )
            ]

        if msg_type == "stop":
            return [
                CallEnded(
                    call_id=self._call_id,
                    reason=msg.get("reason", "normal"),
                )
            ]

        return []

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, CallStarted):
            return json.dumps({
                "type": "start",
                "call_id": event.call_id,
                "from": event.from_number,
                "to": event.to_number,
                "provider": event.provider,
                "metadata": event.metadata,
            })

        if isinstance(event, CallEnded):
            return json.dumps({
                "type": "stop",
                "call_id": event.call_id,
                "reason": event.reason,
            })

        if isinstance(event, DTMFReceived):
            return json.dumps({
                "type": "dtmf",
                "call_id": event.call_id,
                "digit": event.digit,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        return None
