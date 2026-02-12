"""Asterisk ARI (Asterisk REST Interface) WebSocket serializer for VoxBridge.

Translates Asterisk ARI WebSocket events and binary audio from external
media channels into VoxBridge's unified event model. ARI uses a WebSocket
for event delivery and external media audio; most commands are sent over
the separate ARI HTTP API, so the serializer only handles the WS side.
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


class AsteriskSerializer(BaseSerializer):
    """Serializer for the Asterisk ARI WebSocket protocol.

    Asterisk ARI uses:
    - JSON messages for channel events (StasisStart, ChannelDtmfReceived,
      StasisEnd, ChannelHold, ChannelUnhold)
    - Raw binary frames for MULAW audio via external media channels

    Note: ARI uses separate HTTP endpoints for sending commands
    (e.g., originate, hangup, transfer). This serializer focuses on the
    WebSocket stream which carries events and audio.

    State tracked:
    - channel_id: The Asterisk channel identifier from StasisStart.
    """

    def __init__(self) -> None:
        self._channel_id: str = ""

    @property
    def channel_id(self) -> str:
        """The Asterisk channel ID for the current call."""
        return self._channel_id

    @property
    def name(self) -> str:
        return "asterisk"

    @property
    def audio_codec(self) -> Codec:
        return Codec.MULAW

    @property
    def sample_rate(self) -> int:
        return 8000

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        """Parse an Asterisk ARI WebSocket message into VoxBridge events.

        Binary messages are treated as raw MULAW audio from external media.
        JSON messages are dispatched by their ``type`` field.
        """
        if isinstance(raw, bytes):
            return [
                AudioFrame(
                    call_id=self._channel_id,
                    codec=Codec.MULAW,
                    sample_rate=8000,
                    data=raw,
                ),
            ]

        msg: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
        msg_type = msg.get("type", "")

        if msg_type == "StasisStart":
            channel = msg.get("channel", {})
            self._channel_id = channel.get("id", "")
            caller = channel.get("caller", {})
            connected = channel.get("connected", {})
            # Extract SIP headers from channel variables
            dialplan = channel.get("dialplan", {})
            chan_vars = channel.get("channelvars", {})
            sip_headers: dict[str, str] = {}
            for key, val in chan_vars.items():
                if key.startswith("PJSIP_HEADER") or key.startswith("SIP_HEADER"):
                    sip_headers[key] = str(val)
            return [
                CallStarted(
                    call_id=self._channel_id,
                    from_number=caller.get("number", ""),
                    to_number=connected.get("number", ""),
                    provider=self.name,
                    sip_headers=sip_headers,
                    metadata={
                        "channel_name": channel.get("name", ""),
                        "args": msg.get("args", []),
                    },
                ),
            ]

        if msg_type == "ChannelDtmfReceived":
            channel = msg.get("channel", {})
            return [
                DTMFReceived(
                    call_id=channel.get("id", self._channel_id),
                    digit=msg.get("digit", ""),
                    duration_ms=msg.get("duration_ms", 250),
                ),
            ]

        if msg_type == "StasisEnd":
            channel = msg.get("channel", {})
            return [
                CallEnded(
                    call_id=channel.get("id", self._channel_id),
                    reason="stasis_end",
                ),
            ]

        if msg_type == "ChannelHold":
            channel = msg.get("channel", {})
            return [
                HoldStarted(
                    call_id=channel.get("id", self._channel_id),
                ),
            ]

        if msg_type == "ChannelUnhold":
            channel = msg.get("channel", {})
            return [
                HoldEnded(
                    call_id=channel.get("id", self._channel_id),
                ),
            ]

        # Unrecognised events are surfaced as custom events.
        return [
            CustomEvent(
                call_id=self._channel_id,
                custom_type=f"asterisk.{msg_type}",
                payload=msg,
            ),
        ]

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        """Convert a VoxBridge event to Asterisk's wire format.

        AudioFrame events are returned as raw binary MULAW bytes for the
        external media channel. Most ARI commands (hangup, transfer) are
        sent over the HTTP API rather than the WebSocket, so this serializer
        only handles audio output.
        """
        if isinstance(event, AudioFrame):
            return event.data

        if isinstance(event, ClearAudio):
            # Asterisk: stop playback on channel via ARI-style command
            return json.dumps({
                "type": "PlaybackControl",
                "channel_id": event.call_id or self._channel_id,
                "operation": "stop",
            })

        if isinstance(event, Mark):
            return json.dumps({
                "type": "Mark",
                "channel_id": event.call_id or self._channel_id,
                "name": event.name,
            })

        return None

    def handshake_response(self, connect_msg: dict) -> dict | None:
        """Asterisk ARI WebSocket does not require a handshake response."""
        return None
