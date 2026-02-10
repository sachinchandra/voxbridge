"""Base serializer interface for VoxBridge.

Every telephony provider implements this interface. Serializers are pure
message translators with no I/O - they convert between provider-specific
wire formats and VoxBridge's unified event model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from voxbridge.core.events import AnyEvent, Codec


class BaseSerializer(ABC):
    """Abstract base class for telephony provider serializers.

    Serializers handle the translation between a provider's specific
    WebSocket/API message format and VoxBridge's unified events.

    Key principles:
    - Serializers do NO I/O (no network calls, no file access)
    - They are stateless where possible (call state lives in CallSession)
    - They map provider messages to/from the canonical event model
    """

    @abstractmethod
    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        """Parse a raw message from the provider into VoxBridge events.

        A single provider message may produce multiple events (e.g., a Twilio
        'start' message produces both CallStarted and AudioFrame events).

        Args:
            raw: The raw message from the provider WebSocket. Could be:
                - bytes: binary audio frame
                - str: JSON text message
                - dict: already-parsed JSON

        Returns:
            List of VoxBridge events. Empty list if the message should be ignored.
        """
        ...

    @abstractmethod
    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        """Convert a VoxBridge event to the provider's wire format.

        Args:
            event: A VoxBridge event to send to the provider.

        Returns:
            The serialized message ready to send over the provider's transport.
            Return None if this event type is not applicable for the provider.
        """
        ...

    @abstractmethod
    def handshake_response(self, connect_msg: dict) -> dict | None:
        """Generate a response to the provider's initial connection/handshake message.

        Many providers send an initial message when connecting (e.g., Twilio sends
        a 'connected' event, Genesys sends an 'open' message). This method generates
        the appropriate response.

        Args:
            connect_msg: The provider's initial handshake message.

        Returns:
            Response dict to send back, or None if no response is needed.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this serializer (e.g., 'twilio', 'genesys')."""
        ...

    @property
    @abstractmethod
    def audio_codec(self) -> Codec:
        """The audio codec this provider uses natively."""
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """The native sample rate for this provider's audio (e.g., 8000, 16000)."""
        ...
