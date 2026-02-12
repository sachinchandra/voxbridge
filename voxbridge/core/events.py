"""Unified event model for VoxBridge.

All telephony provider serializers convert their platform-specific messages
into these canonical events. The bridge orchestrator routes events between
provider and bot sides using this common language.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Codec(str, Enum):
    MULAW = "mulaw"
    ALAW = "alaw"
    PCM16 = "pcm16"
    OPUS = "opus"


class EventType(str, Enum):
    AUDIO_FRAME = "audio_frame"
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    DTMF_RECEIVED = "dtmf_received"
    HOLD_STARTED = "hold_started"
    HOLD_ENDED = "hold_ended"
    TRANSFER_REQUESTED = "transfer_requested"
    BARGE_IN = "barge_in"
    CLEAR_AUDIO = "clear_audio"
    MARK = "mark"
    CUSTOM = "custom"
    ERROR = "error"


class Event(BaseModel):
    """Base event that all VoxBridge events inherit from."""

    event_type: EventType
    call_id: str = ""
    timestamp: float = Field(default_factory=time.time)


class AudioFrame(Event):
    """A chunk of audio data flowing through the bridge."""

    event_type: EventType = EventType.AUDIO_FRAME
    codec: Codec = Codec.PCM16
    sample_rate: int = 8000
    channels: int = 1
    data: bytes = b""

    class Config:
        arbitrary_types_allowed = True


class CallStarted(Event):
    """Fired when a new call is established."""

    event_type: EventType = EventType.CALL_STARTED
    from_number: str = ""
    to_number: str = ""
    provider: str = ""
    direction: str = "inbound"  # "inbound" or "outbound"
    sip_headers: dict[str, str] = Field(default_factory=dict)  # Custom SIP headers
    metadata: dict[str, Any] = Field(default_factory=dict)


class CallEnded(Event):
    """Fired when a call terminates."""

    event_type: EventType = EventType.CALL_ENDED
    reason: str = "normal"
    duration_ms: int = 0


class DTMFReceived(Event):
    """Fired when a DTMF tone is detected."""

    event_type: EventType = EventType.DTMF_RECEIVED
    digit: str = ""
    duration_ms: int = 250


class HoldStarted(Event):
    """Fired when the call is placed on hold."""

    event_type: EventType = EventType.HOLD_STARTED


class HoldEnded(Event):
    """Fired when the call is taken off hold."""

    event_type: EventType = EventType.HOLD_ENDED


class TransferRequested(Event):
    """Fired when a call transfer is requested."""

    event_type: EventType = EventType.TRANSFER_REQUESTED
    target: str = ""
    transfer_type: str = "blind"  # "blind" or "attended"
    metadata: dict[str, Any] = Field(default_factory=dict)


class BargeIn(Event):
    """Fired when the caller interrupts bot playback (barge-in).

    When detected, the bridge should:
    1. Clear any queued outbound audio
    2. Notify the bot to stop TTS/playback
    3. Start forwarding the caller's speech to the bot
    """

    event_type: EventType = EventType.BARGE_IN
    audio_energy: float = 0.0  # RMS energy of the interrupting audio


class ClearAudio(Event):
    """Control event: instruct the provider to flush queued outbound audio.

    Sent from bot → provider when the bot wants to stop playback immediately
    (e.g., on barge-in, or when switching to a new response).
    """

    event_type: EventType = EventType.CLEAR_AUDIO


class Mark(Event):
    """Marker event for tracking audio playback progress.

    The bot sends a mark, it flows through the provider, and when the provider
    plays it back (e.g., Twilio sends a 'mark' event), the bridge fires this
    event back to the bot so it knows audio up to that point has been played.
    """

    event_type: EventType = EventType.MARK
    name: str = ""  # Unique mark identifier


class CustomEvent(Event):
    """Provider-specific events that don't map to standard events."""

    event_type: EventType = EventType.CUSTOM
    custom_type: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(Event):
    """Error event for signaling issues."""

    event_type: EventType = EventType.ERROR
    code: str = ""
    message: str = ""
    recoverable: bool = True


# Type alias for any event
AnyEvent = (
    AudioFrame
    | CallStarted
    | CallEnded
    | DTMFReceived
    | HoldStarted
    | HoldEnded
    | TransferRequested
    | BargeIn
    | ClearAudio
    | Mark
    | CustomEvent
    | ErrorEvent
)

# Map event types to their classes for deserialization
EVENT_TYPE_MAP: dict[EventType, type[Event]] = {
    EventType.AUDIO_FRAME: AudioFrame,
    EventType.CALL_STARTED: CallStarted,
    EventType.CALL_ENDED: CallEnded,
    EventType.DTMF_RECEIVED: DTMFReceived,
    EventType.HOLD_STARTED: HoldStarted,
    EventType.HOLD_ENDED: HoldEnded,
    EventType.TRANSFER_REQUESTED: TransferRequested,
    EventType.BARGE_IN: BargeIn,
    EventType.CLEAR_AUDIO: ClearAudio,
    EventType.MARK: Mark,
    EventType.CUSTOM: CustomEvent,
    EventType.ERROR: ErrorEvent,
}
