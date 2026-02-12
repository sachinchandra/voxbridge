"""FreeSWITCH mod_ws WebSocket serializer for VoxBridge.

Translates FreeSWITCH WebSocket JSON events and binary audio frames
into VoxBridge's unified event model. FreeSWITCH sends JSON for call
signaling (connect, dtmf, disconnect) and raw MULAW binary for audio.
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
    Mark,
)
from voxbridge.serializers.base import BaseSerializer


class FreeSwitchSerializer(BaseSerializer):
    """Serializer for the FreeSWITCH mod_ws WebSocket protocol.

    FreeSWITCH uses:
    - JSON messages for call signaling (connect, dtmf, disconnect)
    - Raw binary frames for MULAW audio at 8000Hz

    State tracked:
    - uuid: The FreeSWITCH channel UUID from the connect message.
    """

    def __init__(self) -> None:
        self._uuid: str = ""

    @property
    def uuid(self) -> str:
        """The FreeSWITCH channel UUID for the current call."""
        return self._uuid

    @property
    def name(self) -> str:
        return "freeswitch"

    @property
    def audio_codec(self) -> Codec:
        return Codec.MULAW

    @property
    def sample_rate(self) -> int:
        return 8000

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        """Parse a FreeSWITCH WebSocket message into VoxBridge events.

        Binary messages are treated as raw MULAW audio frames.
        JSON messages are dispatched by their ``event`` field.
        """
        if isinstance(raw, bytes):
            return [
                AudioFrame(
                    call_id=self._uuid,
                    codec=Codec.MULAW,
                    sample_rate=8000,
                    data=raw,
                ),
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        event_name = msg.get("event", "")

        if event_name == "connect":
            self._uuid = msg.get("uuid", "")
            # Extract SIP headers from FreeSWITCH variables
            sip_headers: dict[str, str] = {}
            for key, val in msg.items():
                if key.startswith("variable_sip_h_") or key.startswith("sip_"):
                    sip_headers[key] = str(val)
            return [
                CallStarted(
                    call_id=self._uuid,
                    from_number=msg.get("caller_id", ""),
                    to_number=msg.get("destination", ""),
                    provider=self.name,
                    sip_headers=sip_headers,
                    metadata={
                        "sip_from_user": msg.get("variable_sip_from_user", ""),
                    },
                ),
            ]

        if event_name == "dtmf":
            return [
                DTMFReceived(
                    call_id=msg.get("uuid", self._uuid),
                    digit=msg.get("digit", ""),
                    duration_ms=msg.get("duration", 250),
                ),
            ]

        if event_name == "disconnect":
            return [
                CallEnded(
                    call_id=msg.get("uuid", self._uuid),
                    reason=msg.get("cause", "NORMAL_CLEARING"),
                ),
            ]

        # Unrecognised events are surfaced as custom events so nothing is lost.
        return [
            CustomEvent(
                call_id=self._uuid,
                custom_type=f"freeswitch.{event_name}",
                payload=msg,
            ),
        ]

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        """Convert a VoxBridge event to FreeSWITCH's wire format.

        AudioFrame events are returned as raw binary MULAW bytes.
        CallEnded events produce a hangup command.
        TransferRequested events produce a transfer command.
        """
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, CallEnded):
            return json.dumps({
                "command": "hangup",
                "uuid": event.call_id or self._uuid,
                "cause": event.reason or "NORMAL_CLEARING",
            })

        if isinstance(event, ClearAudio):
            # FreeSWITCH: break command stops current playback
            return json.dumps({
                "command": "break",
                "uuid": event.call_id or self._uuid,
            })

        if isinstance(event, Mark):
            return json.dumps({
                "command": "mark",
                "uuid": event.call_id or self._uuid,
                "name": event.name,
            })

        from voxbridge.core.events import TransferRequested

        if isinstance(event, TransferRequested):
            return json.dumps({
                "command": "transfer",
                "uuid": event.call_id or self._uuid,
                "destination": event.target,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        """FreeSWITCH mod_ws does not require a handshake response."""
        return None
