"""Avaya OCSAPI (Open Communication Service API) WebSocket serializer.

Translates between the Avaya OCSAPI WebSocket protocol and VoxBridge's
unified event model. Avaya uses JSON control messages for call signaling
and binary audio frames for mu-law audio at 8kHz.

Protocol (Avaya OCSAPI):
    JSON {"type": "session.start", ...}      -> CallStarted
    JSON {"type": "session.end", ...}        -> CallEnded
    JSON {"type": "dtmf", ...}               -> DTMFReceived
    JSON {"type": "hold", ...}               -> HoldStarted
    JSON {"type": "unhold", ...}             -> HoldEnded
    JSON {"type": "transfer.request", ...}   -> TransferRequested
    Binary frames                            -> AudioFrame (raw MULAW)
    Outgoing AudioFrame                      -> binary MULAW bytes
    Outgoing control                         -> JSON
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
    TransferRequested,
)
from voxbridge.serializers.base import BaseSerializer


class AvayaSerializer(BaseSerializer):
    """Serializer for the Avaya OCSAPI WebSocket protocol.

    Avaya uses JSON signaling messages and raw binary MULAW audio.

    State tracked:
        session_id: The Avaya session identifier from session.start.
        call_id: The call/conversation identifier.
    """

    def __init__(self) -> None:
        self._session_id: str = ""
        self._call_id: str = ""

    @property
    def name(self) -> str:
        return "avaya"

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
                    call_id=self._call_id,
                    codec=Codec.MULAW,
                    sample_rate=8000,
                    channels=1,
                    data=raw,
                )
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        msg_type = msg.get("type", "")

        if msg_type == "session.start":
            self._session_id = msg.get("sessionId", "")
            self._call_id = msg.get("callId", self._session_id)
            params = msg.get("parameters", {})
            # Extract SIP headers from Avaya parameters
            sip_headers: dict[str, str] = {}
            for key, val in params.items():
                if key.startswith("sip_") or key.startswith("x-") or key.startswith("X-"):
                    sip_headers[key] = str(val)
            return [
                CallStarted(
                    call_id=self._call_id,
                    provider="avaya",
                    from_number=params.get("callerNumber", ""),
                    to_number=params.get("calledNumber", ""),
                    sip_headers=sip_headers,
                    metadata={
                        "session_id": self._session_id,
                        "ucid": params.get("ucid", ""),
                        "station_extension": params.get("stationExtension", ""),
                    },
                )
            ]

        if msg_type == "session.end":
            return [
                CallEnded(
                    call_id=self._call_id,
                    reason=msg.get("reason", "normal"),
                )
            ]

        if msg_type == "dtmf":
            return [
                DTMFReceived(
                    call_id=self._call_id,
                    digit=msg.get("digit", ""),
                    duration_ms=msg.get("duration", 250),
                )
            ]

        if msg_type == "hold":
            return [HoldStarted(call_id=self._call_id)]

        if msg_type == "unhold":
            return [HoldEnded(call_id=self._call_id)]

        if msg_type == "transfer.request":
            return [
                TransferRequested(
                    call_id=self._call_id,
                    target=msg.get("target", ""),
                    transfer_type=msg.get("transferType", "blind"),
                )
            ]

        return [
            CustomEvent(
                call_id=self._call_id,
                custom_type=f"avaya.{msg_type}",
                payload=msg,
            )
        ]

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, CallEnded):
            return json.dumps({
                "type": "session.end",
                "sessionId": self._session_id,
                "reason": event.reason,
            })

        if isinstance(event, ClearAudio):
            return json.dumps({
                "type": "audio.clear",
                "sessionId": self._session_id,
            })

        if isinstance(event, Mark):
            return json.dumps({
                "type": "audio.mark",
                "sessionId": self._session_id,
                "name": event.name,
            })

        if isinstance(event, TransferRequested):
            return json.dumps({
                "type": "transfer.initiate",
                "sessionId": self._session_id,
                "target": event.target,
                "transferType": event.transfer_type,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        msg_type = connect_msg.get("type", "")
        if msg_type == "session.start":
            self._session_id = connect_msg.get("sessionId", "")
            self._call_id = connect_msg.get("callId", self._session_id)
            return {
                "type": "session.accepted",
                "sessionId": self._session_id,
                "parameters": {
                    "media": {
                        "format": "PCMU",
                        "rate": 8000,
                        "channels": 1,
                    }
                },
            }
        return None
