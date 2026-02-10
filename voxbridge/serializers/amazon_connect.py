"""Amazon Connect WebSocket serializer for VoxBridge.

Translates between Amazon Connect's contact streaming WebSocket protocol
and VoxBridge's unified event model. Amazon Connect sends call events as
JSON and audio via Kinesis Video Streams (KVS), but when used with the
streaming audio API or a WebSocket adapter, audio arrives as binary frames.

Protocol (Amazon Connect Streaming):
    JSON {"event": "STARTED", ...}      -> CallStarted
    JSON {"event": "ENDED", ...}        -> CallEnded
    JSON {"event": "DTMF", ...}         -> DTMFReceived
    JSON {"event": "HOLD", ...}         -> HoldStarted
    JSON {"event": "RESUME", ...}       -> HoldEnded
    Binary frames                       -> AudioFrame (PCM16 at 8kHz)
    Outgoing AudioFrame                 -> binary PCM16 bytes
"""

from __future__ import annotations

import json
from typing import Any

from voxbridge.core.events import (
    AnyEvent,
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    CustomEvent,
    DTMFReceived,
    HoldEnded,
    HoldStarted,
)
from voxbridge.serializers.base import BaseSerializer


class AmazonConnectSerializer(BaseSerializer):
    """Serializer for Amazon Connect streaming WebSocket protocol.

    Amazon Connect typically streams audio via KVS, but can be used
    with a WebSocket adapter for real-time audio. This serializer
    handles the WebSocket variant.

    State tracked:
        contact_id: The Amazon Connect contact identifier.
        instance_id: The Connect instance identifier.
    """

    def __init__(self) -> None:
        self._contact_id: str = ""
        self._instance_id: str = ""

    @property
    def name(self) -> str:
        return "amazon_connect"

    @property
    def audio_codec(self) -> Codec:
        return Codec.PCM16

    @property
    def sample_rate(self) -> int:
        return 8000

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        if isinstance(raw, bytes):
            return [
                AudioFrame(
                    call_id=self._contact_id,
                    codec=Codec.PCM16,
                    sample_rate=8000,
                    channels=1,
                    data=raw,
                )
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        event_name = msg.get("event", "")

        if event_name == "STARTED":
            self._contact_id = msg.get("contactId", "")
            self._instance_id = msg.get("instanceId", "")
            attributes = msg.get("contactAttributes", {})
            return [
                CallStarted(
                    call_id=self._contact_id,
                    provider="amazon_connect",
                    from_number=attributes.get("customerNumber", ""),
                    to_number=attributes.get("systemNumber", ""),
                    metadata={
                        "contact_id": self._contact_id,
                        "instance_id": self._instance_id,
                        "queue": attributes.get("queue", ""),
                        "contact_attributes": attributes,
                    },
                )
            ]

        if event_name == "ENDED":
            return [
                CallEnded(
                    call_id=self._contact_id,
                    reason=msg.get("disconnectReason", "normal"),
                )
            ]

        if event_name == "DTMF":
            return [
                DTMFReceived(
                    call_id=self._contact_id,
                    digit=msg.get("digit", ""),
                )
            ]

        if event_name == "HOLD":
            return [HoldStarted(call_id=self._contact_id)]

        if event_name == "RESUME":
            return [HoldEnded(call_id=self._contact_id)]

        return [
            CustomEvent(
                call_id=self._contact_id,
                custom_type=f"amazon_connect.{event_name}",
                payload=msg,
            )
        ]

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, CallEnded):
            return json.dumps({
                "event": "END",
                "contactId": self._contact_id,
                "reason": event.reason,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        event_name = connect_msg.get("event", "")
        if event_name == "STARTED":
            self._contact_id = connect_msg.get("contactId", "")
            self._instance_id = connect_msg.get("instanceId", "")
            return {
                "event": "ACCEPTED",
                "contactId": self._contact_id,
                "parameters": {
                    "mediaFormat": "lpcm",
                    "sampleRate": 8000,
                },
            }
        return None
