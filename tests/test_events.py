"""Tests for the VoxBridge event model."""

import pytest

from voxbridge.core.events import (
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    CustomEvent,
    DTMFReceived,
    ErrorEvent,
    EventType,
    HoldEnded,
    HoldStarted,
    TransferRequested,
    EVENT_TYPE_MAP,
)


class TestEventModel:
    """Test the Pydantic event models."""

    def test_audio_frame_defaults(self):
        frame = AudioFrame()
        assert frame.event_type == EventType.AUDIO_FRAME
        assert frame.codec == Codec.PCM16
        assert frame.sample_rate == 8000
        assert frame.channels == 1
        assert frame.data == b""
        assert frame.call_id == ""

    def test_audio_frame_with_data(self):
        frame = AudioFrame(
            call_id="call-123",
            codec=Codec.MULAW,
            sample_rate=8000,
            data=b"\xff\x00\x01",
        )
        assert frame.call_id == "call-123"
        assert frame.codec == Codec.MULAW
        assert frame.data == b"\xff\x00\x01"

    def test_call_started(self):
        event = CallStarted(
            call_id="call-456",
            from_number="+15551234567",
            to_number="+15559876543",
            provider="twilio",
            direction="inbound",
            metadata={"stream_sid": "MZ123"},
        )
        assert event.event_type == EventType.CALL_STARTED
        assert event.from_number == "+15551234567"
        assert event.provider == "twilio"
        assert event.metadata["stream_sid"] == "MZ123"

    def test_call_ended(self):
        event = CallEnded(call_id="call-456", reason="hangup", duration_ms=30000)
        assert event.event_type == EventType.CALL_ENDED
        assert event.reason == "hangup"
        assert event.duration_ms == 30000

    def test_dtmf_received(self):
        event = DTMFReceived(call_id="call-789", digit="5", duration_ms=200)
        assert event.event_type == EventType.DTMF_RECEIVED
        assert event.digit == "5"
        assert event.duration_ms == 200

    def test_hold_events(self):
        start = HoldStarted(call_id="call-1")
        end = HoldEnded(call_id="call-1")
        assert start.event_type == EventType.HOLD_STARTED
        assert end.event_type == EventType.HOLD_ENDED

    def test_transfer_requested(self):
        event = TransferRequested(
            call_id="call-1",
            target="agent_queue",
            transfer_type="blind",
        )
        assert event.event_type == EventType.TRANSFER_REQUESTED
        assert event.target == "agent_queue"

    def test_custom_event(self):
        event = CustomEvent(
            call_id="call-1",
            custom_type="twilio.mark",
            payload={"name": "greeting_played"},
        )
        assert event.event_type == EventType.CUSTOM
        assert event.custom_type == "twilio.mark"
        assert event.payload["name"] == "greeting_played"

    def test_error_event(self):
        event = ErrorEvent(
            call_id="call-1",
            code="CODEC_ERROR",
            message="Unsupported codec",
            recoverable=False,
        )
        assert event.event_type == EventType.ERROR
        assert event.code == "CODEC_ERROR"
        assert event.recoverable is False

    def test_event_type_map_complete(self):
        """Every EventType should have a corresponding class."""
        for event_type in EventType:
            assert event_type in EVENT_TYPE_MAP, \
                f"EventType.{event_type.name} missing from EVENT_TYPE_MAP"

    def test_codec_enum_values(self):
        assert Codec.MULAW.value == "mulaw"
        assert Codec.ALAW.value == "alaw"
        assert Codec.PCM16.value == "pcm16"
        assert Codec.OPUS.value == "opus"

    def test_event_timestamp(self):
        """Events should have an auto-generated timestamp."""
        event = CallStarted(call_id="test")
        assert event.timestamp > 0

    def test_event_serialization(self):
        """Events should serialize to/from dict."""
        event = CallStarted(
            call_id="call-1",
            from_number="+1555",
            provider="genesys",
        )
        data = event.model_dump()
        assert data["call_id"] == "call-1"
        assert data["from_number"] == "+1555"
        assert data["event_type"] == EventType.CALL_STARTED
