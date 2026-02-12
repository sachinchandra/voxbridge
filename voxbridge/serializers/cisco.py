"""Cisco OCSDK / WebEx Contact Center WebSocket serializer.

Translates between Cisco's contact center WebSocket protocol and
VoxBridge's unified event model. Cisco uses JSON for signaling and
binary audio frames for mu-law or PCM audio.

Protocol (Cisco WebEx CC):
    JSON {"event": "call.new", ...}       -> CallStarted
    JSON {"event": "call.ended", ...}     -> CallEnded
    JSON {"event": "dtmf", ...}           -> DTMFReceived
    JSON {"event": "call.held", ...}      -> HoldStarted
    JSON {"event": "call.retrieved", ...} -> HoldEnded
    Binary frames                         -> AudioFrame (raw MULAW)
    Outgoing AudioFrame                   -> binary MULAW bytes
"""

from __future__ import annotations

import json
from typing import Any

from voxbridge.core.events import (
    AnyEvent,
    AudioFrame,
    CallEnded,
    CallStarted,
    ClearAudio,
    Codec,
    CustomEvent,
    DTMFReceived,
    HoldEnded,
    HoldStarted,
    Mark,
)
from voxbridge.serializers.base import BaseSerializer


class CiscoSerializer(BaseSerializer):
    """Serializer for Cisco WebEx Contact Center / OCSDK WebSocket protocol.

    State tracked:
        interaction_id: The Cisco interaction identifier.
        agent_id: The agent session identifier.
    """

    def __init__(self) -> None:
        self._interaction_id: str = ""
        self._agent_id: str = ""

    @property
    def name(self) -> str:
        return "cisco"

    @property
    def audio_codec(self) -> Codec:
        return Codec.MULAW

    @property
    def sample_rate(self) -> int:
        return 8000

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        if isinstance(raw, bytes):
            return [
                AudioFrame(
                    call_id=self._interaction_id,
                    codec=Codec.MULAW,
                    sample_rate=8000,
                    channels=1,
                    data=raw,
                )
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        event_name = msg.get("event", "")

        if event_name == "call.new":
            self._interaction_id = msg.get("interactionId", "")
            self._agent_id = msg.get("agentId", "")
            data = msg.get("data", {})
            # Extract SIP headers from call data
            sip_headers: dict[str, str] = {}
            for key, val in data.items():
                if key.startswith("sip_") or key.startswith("x-") or key.startswith("X-"):
                    sip_headers[key] = str(val)
            return [
                CallStarted(
                    call_id=self._interaction_id,
                    provider="cisco",
                    from_number=data.get("ani", ""),
                    to_number=data.get("dnis", ""),
                    sip_headers=sip_headers,
                    metadata={
                        "interaction_id": self._interaction_id,
                        "agent_id": self._agent_id,
                        "queue_name": data.get("queueName", ""),
                    },
                )
            ]

        if event_name == "call.ended":
            return [
                CallEnded(
                    call_id=self._interaction_id,
                    reason=msg.get("reason", "normal"),
                )
            ]

        if event_name == "dtmf":
            return [
                DTMFReceived(
                    call_id=self._interaction_id,
                    digit=msg.get("digit", ""),
                )
            ]

        if event_name == "call.held":
            return [HoldStarted(call_id=self._interaction_id)]

        if event_name == "call.retrieved":
            return [HoldEnded(call_id=self._interaction_id)]

        return [
            CustomEvent(
                call_id=self._interaction_id,
                custom_type=f"cisco.{event_name}",
                payload=msg,
            )
        ]

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, CallEnded):
            return json.dumps({
                "event": "call.end",
                "interactionId": self._interaction_id,
                "reason": event.reason,
            })

        if isinstance(event, ClearAudio):
            return json.dumps({
                "event": "audio.clear",
                "interactionId": self._interaction_id,
            })

        if isinstance(event, Mark):
            return json.dumps({
                "event": "audio.mark",
                "interactionId": self._interaction_id,
                "name": event.name,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        event_name = connect_msg.get("event", "")
        if event_name == "call.new":
            self._interaction_id = connect_msg.get("interactionId", "")
            return {
                "event": "call.accepted",
                "interactionId": self._interaction_id,
                "parameters": {
                    "mediaFormat": "PCMU",
                    "sampleRate": 8000,
                },
            }
        return None
