"""Genesys Cloud AudioHook WebSocket serializer.

Translates between the Genesys Cloud AudioHook protocol and VoxBridge's
unified event model.  Genesys uses a mix of JSON control messages and raw
binary audio frames over a single WebSocket connection.

Protocol reference:
    https://developer.genesys.cloud/devapps/audiohook
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


class GenesysSerializer(BaseSerializer):
    """Serializer for the Genesys Cloud AudioHook WebSocket protocol.

    Genesys sends JSON control messages (``open``, ``ping``, ``close``,
    ``dtmf``, ``pause``, ``resume``) and raw binary mu-law audio frames
    on the same WebSocket connection.

    State kept across the lifetime of a single session:
        session_id: The unique identifier echoed in the ``id`` field of
                    every control message for this session.
        conversation_id: The Genesys conversation (call) identifier.
    """

    def __init__(self) -> None:
        self.session_id: str = ""
        self.conversation_id: str = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "genesys"

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
        """Parse a Genesys AudioHook message into VoxBridge events.

        Message types handled:
            * Binary frame      -- raw mu-law audio; produces :class:`AudioFrame`.
            * ``open``  (JSON)  -- session start; produces :class:`CallStarted`.
            * ``ping``  (JSON)  -- keepalive (handled internally, no event).
            * ``close`` (JSON)  -- session end; produces :class:`CallEnded`.
            * ``dtmf``  (JSON)  -- DTMF digit; produces :class:`DTMFReceived`.
            * ``pause`` (JSON)  -- call hold; produces :class:`HoldStarted`.
            * ``resume``(JSON)  -- call resumed; produces :class:`HoldEnded`.
        """
        # Binary frame -> audio
        if isinstance(raw, bytes):
            return self._handle_binary_audio(raw)

        msg = self._parse_message(raw)
        msg_type = msg.get("type", "")

        if msg_type == "open":
            return self._handle_open(msg)

        if msg_type == "ping":
            # Ping is handled via handshake_response / out-of-band.
            # No VoxBridge event, but callers can use build_pong().
            return []

        if msg_type == "close":
            return self._handle_close(msg)

        if msg_type == "dtmf":
            return self._handle_dtmf(msg)

        if msg_type == "pause":
            return [
                HoldStarted(
                    call_id=self.conversation_id,
                )
            ]

        if msg_type == "resume":
            return [
                HoldEnded(
                    call_id=self.conversation_id,
                )
            ]

        # Unknown message type.
        return [
            CustomEvent(
                call_id=self.conversation_id,
                custom_type=f"genesys.{msg_type}",
                payload=msg,
            )
        ]

    # ------------------------------------------------------------------
    # Serialization (VoxBridge events -> provider wire format)
    # ------------------------------------------------------------------

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        """Convert a VoxBridge event to the Genesys AudioHook wire format.

        Supported outbound events:
            * :class:`AudioFrame` -- sent as raw binary mu-law bytes.
            * :class:`ClearAudio` -- sent as a ``discardAudio`` control message.
            * :class:`Mark` -- sent as a ``position`` tracking message.

        Returns ``None`` for event types that have no Genesys outbound mapping.
        """
        if isinstance(event, AudioFrame):
            # Genesys expects raw binary audio on the wire.
            return bytes(event.data)

        if isinstance(event, ClearAudio):
            return self.build_discard_audio_message()

        if isinstance(event, Mark):
            return self.build_position_message(event.name)

        return None

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def handshake_response(self, connect_msg: dict) -> dict | None:
        """Generate a response to a Genesys control message that requires one.

        Handles:
            * ``open``  -> ``opened`` response with media parameters.
            * ``ping``  -> ``pong`` response.
            * ``close`` -> ``closed`` acknowledgement.

        Returns ``None`` for message types that need no response.
        """
        msg_type = connect_msg.get("type", "")
        msg_id = connect_msg.get("id", self.session_id)

        if msg_type == "open":
            # Store session state.
            self.session_id = msg_id
            params = connect_msg.get("parameters", {})
            self.conversation_id = params.get("conversationId", "")

            return {
                "type": "opened",
                "id": msg_id,
                "parameters": {
                    "startPaused": False,
                    "media": [
                        {
                            "type": "audio",
                            "format": "PCMU",
                            "channels": ["external"],
                            "rate": 8000,
                        }
                    ],
                },
            }

        if msg_type == "ping":
            return {
                "type": "pong",
                "id": msg_id,
            }

        if msg_type == "close":
            return {
                "type": "closed",
                "id": msg_id,
            }

        return None

    # ------------------------------------------------------------------
    # Convenience builders for outbound control messages
    # ------------------------------------------------------------------

    def build_pong(self, ping_msg: dict) -> str:
        """Build a JSON ``pong`` response string for a ``ping`` message."""
        return json.dumps(
            {
                "type": "pong",
                "id": ping_msg.get("id", self.session_id),
            }
        )

    def build_discard_audio_message(self) -> str:
        """Build a JSON ``discardAudio`` control message for Genesys.

        Instructs Genesys to discard any buffered audio that has not been
        played yet.  Used for barge-in.
        """
        return json.dumps(
            {
                "type": "discardAudio",
                "id": self.session_id,
            }
        )

    def build_position_message(self, name: str) -> str:
        """Build a JSON ``position`` control message for tracking playback.

        Genesys uses position markers to track audio playback progress.
        """
        return json.dumps(
            {
                "type": "position",
                "id": self.session_id,
                "parameters": {
                    "name": name,
                },
            }
        )

    def build_disconnect(self, reason: str = "normal") -> str:
        """Build a JSON ``disconnect`` control message.

        This can be sent to instruct Genesys to tear down the audio stream
        from the integration side.
        """
        return json.dumps(
            {
                "type": "disconnect",
                "id": self.session_id,
                "parameters": {
                    "reason": reason,
                },
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

    def _handle_binary_audio(self, raw: bytes) -> list[AnyEvent]:
        """Wrap raw binary audio bytes in an AudioFrame."""
        return [
            AudioFrame(
                call_id=self.conversation_id,
                codec=Codec.MULAW,
                sample_rate=8000,
                channels=1,
                data=raw,
            )
        ]

    def _handle_open(self, msg: dict) -> list[AnyEvent]:
        """Process a Genesys ``open`` message."""
        self.session_id = msg.get("id", "")
        params = msg.get("parameters", {})
        self.conversation_id = params.get("conversationId", "")

        # Extract SIP headers from participant data or custom parameters
        participant = params.get("participant", {})
        sip_headers: dict[str, str] = {}
        for key, val in participant.items():
            if key.startswith("sip_") or key.startswith("x-") or key.startswith("X-"):
                sip_headers[key] = str(val)

        metadata: dict[str, Any] = {
            "session_id": self.session_id,
            "organization_id": params.get("organizationId", ""),
            "participant": participant,
            "position": msg.get("position", 0),
        }

        return [
            CallStarted(
                call_id=self.conversation_id,
                provider="genesys",
                sip_headers=sip_headers,
                metadata=metadata,
            )
        ]

    def _handle_close(self, msg: dict) -> list[AnyEvent]:
        """Process a Genesys ``close`` message."""
        params = msg.get("parameters", {})
        reason = params.get("reason", "normal")

        return [
            CallEnded(
                call_id=self.conversation_id,
                reason=reason,
            )
        ]

    def _handle_dtmf(self, msg: dict) -> list[AnyEvent]:
        """Process a Genesys ``dtmf`` message."""
        params = msg.get("parameters", {})
        digit = params.get("digit", "")

        return [
            DTMFReceived(
                call_id=self.conversation_id,
                digit=digit,
            )
        ]
