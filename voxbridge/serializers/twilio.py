"""Twilio Media Streams WebSocket serializer.

Translates between Twilio's Media Streams WebSocket protocol and VoxBridge's
unified event model. Twilio streams audio as base64-encoded mu-law at 8kHz
over JSON WebSocket messages.

Protocol reference:
    https://www.twilio.com/docs/voice/media-streams/websocket-messages
"""

from __future__ import annotations

import base64
import json
from typing import Any

from voxbridge.core.events import (
    AnyEvent,
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    DTMFReceived,
    CustomEvent,
)
from voxbridge.serializers.base import BaseSerializer


class TwilioSerializer(BaseSerializer):
    """Serializer for the Twilio Media Streams WebSocket protocol.

    Twilio sends JSON messages with an ``event`` field that indicates the
    message type.  Audio payloads arrive as base64-encoded mu-law in
    ``media`` events and must be decoded before being wrapped in an
    :class:`AudioFrame`.

    State kept across the lifetime of a single stream:
        stream_sid: The unique identifier for the media stream.
        call_sid:   The Twilio Call SID associated with this stream.
    """

    def __init__(self) -> None:
        self.stream_sid: str = ""
        self.call_sid: str = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "twilio"

    @property
    def audio_codec(self) -> Codec:
        return Codec.MULAW

    @property
    def sample_rate(self) -> int:
        return 8000

    # ------------------------------------------------------------------
    # Deserialization (provider -> VoxBridge events)
    # ------------------------------------------------------------------

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        """Parse a Twilio Media Streams message into VoxBridge events.

        Message types handled:
            * ``connected`` -- initial handshake acknowledgement (ignored).
            * ``start``     -- stream metadata; produces :class:`CallStarted`.
            * ``media``     -- audio payload; produces :class:`AudioFrame`.
            * ``dtmf``      -- DTMF digit; produces :class:`DTMFReceived`.
            * ``stop``      -- stream ended; produces :class:`CallEnded`.

        Any unrecognised message type is surfaced as a :class:`CustomEvent`.
        """
        msg = self._parse_message(raw)
        event_type = msg.get("event", "")

        if event_type == "connected":
            # Twilio's initial connection acknowledgement -- no VoxBridge event.
            return []

        if event_type == "start":
            return self._handle_start(msg)

        if event_type == "media":
            return self._handle_media(msg)

        if event_type == "dtmf":
            return self._handle_dtmf(msg)

        if event_type == "stop":
            return self._handle_stop(msg)

        # Unknown / provider-specific event -- wrap as custom.
        return [
            CustomEvent(
                call_id=self.call_sid,
                custom_type=f"twilio.{event_type}",
                payload=msg,
            )
        ]

    # ------------------------------------------------------------------
    # Serialization (VoxBridge events -> provider wire format)
    # ------------------------------------------------------------------

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        """Convert a VoxBridge event to a Twilio Media Streams message.

        Supported outbound events:
            * :class:`AudioFrame` -- encoded as a ``media`` message with
              base64-encoded audio payload.

        Returns ``None`` for event types that Twilio does not accept.
        """
        if isinstance(event, AudioFrame):
            payload_b64 = base64.b64encode(event.data).decode("ascii")
            return json.dumps(
                {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": payload_b64,
                    },
                }
            )

        # No mapping for other event types on the outbound side.
        return None

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def handshake_response(self, connect_msg: dict) -> dict | None:
        """Twilio's ``connected`` event does not require a response."""
        return None

    # ------------------------------------------------------------------
    # Helpers for building a clear-audio control message
    # ------------------------------------------------------------------

    def build_clear_message(self) -> str:
        """Build a Twilio ``clear`` control message.

        Sending this message instructs Twilio to discard any buffered audio
        that has not yet been played to the caller.
        """
        return json.dumps(
            {
                "event": "clear",
                "streamSid": self.stream_sid,
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_message(raw: bytes | str | dict) -> dict[str, Any]:
        """Normalise the raw WebSocket frame into a dict."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def _handle_start(self, msg: dict) -> list[AnyEvent]:
        """Process a Twilio ``start`` message."""
        start_data = msg.get("start", {})
        self.stream_sid = start_data.get("streamSid", "")
        self.call_sid = start_data.get("callSid", "")

        metadata: dict[str, Any] = {
            "account_sid": start_data.get("accountSid", ""),
            "stream_sid": self.stream_sid,
            "custom_parameters": start_data.get("customParameters", {}),
            "media_format": start_data.get("mediaFormat", {}),
        }

        return [
            CallStarted(
                call_id=self.call_sid,
                provider="twilio",
                metadata=metadata,
            )
        ]

    def _handle_media(self, msg: dict) -> list[AnyEvent]:
        """Process a Twilio ``media`` message."""
        media_data = msg.get("media", {})
        payload_b64 = media_data.get("payload", "")
        audio_bytes = base64.b64decode(payload_b64)

        # Update stream_sid if present at the top level.
        if "streamSid" in msg:
            self.stream_sid = msg["streamSid"]

        return [
            AudioFrame(
                call_id=self.call_sid,
                codec=Codec.MULAW,
                sample_rate=8000,
                channels=1,
                data=audio_bytes,
            )
        ]

    def _handle_dtmf(self, msg: dict) -> list[AnyEvent]:
        """Process a Twilio ``dtmf`` message."""
        dtmf_data = msg.get("dtmf", {})
        digit = dtmf_data.get("digit", "")

        if "streamSid" in msg:
            self.stream_sid = msg["streamSid"]

        return [
            DTMFReceived(
                call_id=self.call_sid,
                digit=digit,
            )
        ]

    def _handle_stop(self, msg: dict) -> list[AnyEvent]:
        """Process a Twilio ``stop`` message."""
        if "streamSid" in msg:
            self.stream_sid = msg["streamSid"]

        return [
            CallEnded(
                call_id=self.call_sid,
                reason="normal",
            )
        ]
