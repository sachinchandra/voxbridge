"""Tests for barge-in, marks, clear audio, SIP headers, and VAD."""

import asyncio
import json
import struct

import pytest

from voxbridge.core.events import (
    AudioFrame,
    BargeIn,
    CallEnded,
    CallStarted,
    ClearAudio,
    Codec,
    EventType,
    Mark,
    EVENT_TYPE_MAP,
)
from voxbridge.session import BargeInDetector, CallSession, compute_audio_energy
from voxbridge.serializers.twilio import TwilioSerializer
from voxbridge.serializers.genesys import GenesysSerializer
from voxbridge.serializers.generic_ws import GenericWebSocketSerializer
from voxbridge.serializers.freeswitch import FreeSwitchSerializer
from voxbridge.serializers.asterisk import AsteriskSerializer
from voxbridge.serializers.amazon_connect import AmazonConnectSerializer
from voxbridge.serializers.avaya import AvayaSerializer
from voxbridge.serializers.cisco import CiscoSerializer


# ==========================================================================
# Event Model Tests
# ==========================================================================


class TestBargeInEvent:

    def test_barge_in_defaults(self):
        event = BargeIn()
        assert event.event_type == EventType.BARGE_IN
        assert event.audio_energy == 0.0
        assert event.call_id == ""

    def test_barge_in_with_data(self):
        event = BargeIn(call_id="call-123", audio_energy=0.85)
        assert event.call_id == "call-123"
        assert event.audio_energy == 0.85

    def test_barge_in_in_event_type_map(self):
        assert EventType.BARGE_IN in EVENT_TYPE_MAP
        assert EVENT_TYPE_MAP[EventType.BARGE_IN] is BargeIn

    def test_barge_in_serialization(self):
        event = BargeIn(call_id="call-1", audio_energy=0.5)
        data = event.model_dump()
        assert data["event_type"] == EventType.BARGE_IN
        assert data["audio_energy"] == 0.5


class TestClearAudioEvent:

    def test_clear_audio_defaults(self):
        event = ClearAudio()
        assert event.event_type == EventType.CLEAR_AUDIO
        assert event.call_id == ""

    def test_clear_audio_with_call_id(self):
        event = ClearAudio(call_id="call-456")
        assert event.call_id == "call-456"

    def test_clear_audio_in_event_type_map(self):
        assert EventType.CLEAR_AUDIO in EVENT_TYPE_MAP
        assert EVENT_TYPE_MAP[EventType.CLEAR_AUDIO] is ClearAudio


class TestMarkEvent:

    def test_mark_defaults(self):
        event = Mark()
        assert event.event_type == EventType.MARK
        assert event.name == ""
        assert event.call_id == ""

    def test_mark_with_name(self):
        event = Mark(call_id="call-789", name="greeting_end")
        assert event.call_id == "call-789"
        assert event.name == "greeting_end"

    def test_mark_in_event_type_map(self):
        assert EventType.MARK in EVENT_TYPE_MAP
        assert EVENT_TYPE_MAP[EventType.MARK] is Mark

    def test_mark_serialization(self):
        event = Mark(call_id="call-1", name="sentence_1")
        data = event.model_dump()
        assert data["name"] == "sentence_1"


# ==========================================================================
# SIP Headers Tests
# ==========================================================================


class TestSIPHeaders:

    def test_call_started_sip_headers(self):
        event = CallStarted(
            call_id="call-1",
            provider="twilio",
            sip_headers={"X-Custom-ID": "abc123", "sip_from": "user@domain"},
        )
        assert event.sip_headers["X-Custom-ID"] == "abc123"
        assert event.sip_headers["sip_from"] == "user@domain"

    def test_call_started_empty_sip_headers(self):
        event = CallStarted(call_id="call-1")
        assert event.sip_headers == {}


# ==========================================================================
# Audio Energy / VAD Tests
# ==========================================================================


class TestComputeAudioEnergy:

    def test_empty_data(self):
        assert compute_audio_energy(b"", "mulaw") == 0.0

    def test_mulaw_silence(self):
        """mu-law silence is 0xFF (or 0x7F). Energy should be very low."""
        # 0xFF decodes to ~0 in mu-law
        silence = bytes([0xFF] * 160)  # 20ms of silence at 8kHz
        energy = compute_audio_energy(silence, "mulaw")
        assert energy < 50  # Very low energy

    def test_mulaw_loud_audio(self):
        """Loud mu-law audio should have high energy."""
        # 0x00 decodes to a very large sample in mu-law (~-8031)
        loud = bytes([0x00] * 160)
        energy = compute_audio_energy(loud, "mulaw")
        assert energy > 5000  # High energy

    def test_pcm16_silence(self):
        """PCM16 silence (all zeros) should be zero energy."""
        silence = b"\x00\x00" * 160
        energy = compute_audio_energy(silence, "pcm16")
        assert energy == 0.0

    def test_pcm16_loud(self):
        """PCM16 loud signal should have high energy."""
        # Pack 160 samples of value 10000
        loud = struct.pack(f"<{160}h", *([10000] * 160))
        energy = compute_audio_energy(loud, "pcm16")
        assert abs(energy - 10000.0) < 1.0  # RMS of constant = constant


class TestBargeInDetector:

    def test_defaults(self):
        detector = BargeInDetector()
        assert detector.energy_threshold == 200.0
        assert detector.min_speech_frames == 3
        assert detector.codec == "mulaw"
        assert detector._consecutive_speech_frames == 0
        assert detector._triggered is False

    def test_silence_does_not_trigger(self):
        """mu-law silence should never trigger barge-in."""
        detector = BargeInDetector()
        silence = bytes([0xFF] * 160)
        for _ in range(100):
            assert detector.check(silence) is False

    def test_speech_triggers_after_min_frames(self):
        """Loud audio should trigger after min_speech_frames consecutive frames."""
        detector = BargeInDetector(min_speech_frames=3)
        loud = bytes([0x00] * 160)  # Very loud mu-law

        assert detector.check(loud) is False  # frame 1
        assert detector.check(loud) is False  # frame 2
        assert detector.check(loud) is True   # frame 3 — trigger!

    def test_speech_interrupted_by_silence_resets(self):
        """A silence frame in between resets the counter."""
        detector = BargeInDetector(min_speech_frames=3)
        loud = bytes([0x00] * 160)
        silence = bytes([0xFF] * 160)

        detector.check(loud)   # 1
        detector.check(loud)   # 2
        detector.check(silence)  # reset!
        detector.check(loud)   # 1 again
        detector.check(loud)   # 2 again
        assert detector._triggered is False  # still not triggered

    def test_trigger_only_fires_once(self):
        """After triggering, check() returns False until reset."""
        detector = BargeInDetector(min_speech_frames=1)
        loud = bytes([0x00] * 160)

        assert detector.check(loud) is True   # trigger
        assert detector.check(loud) is False  # already triggered

    def test_reset(self):
        """reset() allows the detector to trigger again."""
        detector = BargeInDetector(min_speech_frames=1)
        loud = bytes([0x00] * 160)

        assert detector.check(loud) is True  # trigger
        detector.reset()
        assert detector.check(loud) is True  # trigger again

    def test_custom_threshold(self):
        """A high threshold should make the detector less sensitive."""
        # Use a threshold so high that even loud audio won't trigger
        detector = BargeInDetector(energy_threshold=50000.0, min_speech_frames=1)
        loud = bytes([0x00] * 160)
        assert detector.check(loud) is False

    def test_low_threshold_catches_quiet_audio(self):
        """A very low threshold catches even quiet audio."""
        detector = BargeInDetector(energy_threshold=1.0, min_speech_frames=1)
        # Some non-silent but quiet mulaw audio
        quiet = bytes([0xFE] * 160)
        energy = compute_audio_energy(quiet, "mulaw")
        if energy >= 1.0:
            assert detector.check(quiet) is True
        else:
            assert detector.check(quiet) is False


# ==========================================================================
# Session Barge-In State Tests
# ==========================================================================


class TestSessionBargeIn:

    def test_session_barge_in_defaults(self):
        session = CallSession()
        assert session.is_bot_speaking is False
        assert session.barge_in_enabled is True
        assert session.sip_headers == {}
        assert session._pending_marks == []

    def test_session_has_barge_in_detector(self):
        session = CallSession()
        assert isinstance(session.barge_in_detector, BargeInDetector)
        assert session.barge_in_detector.energy_threshold == 200.0

    def test_clear_outbound_audio_empty(self):
        session = CallSession()
        cleared = session.clear_outbound_audio()
        assert cleared == 0
        assert session.is_bot_speaking is False

    def test_clear_outbound_audio_with_items(self):
        session = CallSession()
        session.is_bot_speaking = True
        queue = session.outbound_audio_queue
        queue.put_nowait(b"\x00\x01")
        queue.put_nowait(b"\x02\x03")
        queue.put_nowait(b"\x04\x05")

        cleared = session.clear_outbound_audio()
        assert cleared == 3
        assert session.is_bot_speaking is False
        assert queue.empty()

    def test_outbound_audio_queue_lazy_init(self):
        session = CallSession()
        assert session._outbound_audio_queue is None
        queue = session.outbound_audio_queue
        assert queue is not None
        # Second access returns same queue
        assert session.outbound_audio_queue is queue

    def test_sip_headers_storage(self):
        session = CallSession()
        session.sip_headers = {"X-Bot-ID": "bot-1", "sip_custom": "value"}
        assert session.sip_headers["X-Bot-ID"] == "bot-1"

    def test_pending_marks(self):
        session = CallSession()
        session._pending_marks.append("mark_1")
        session._pending_marks.append("mark_2")
        assert len(session._pending_marks) == 2
        session._pending_marks.remove("mark_1")
        assert session._pending_marks == ["mark_2"]


# ==========================================================================
# Twilio Serializer - Barge-In / Mark / Clear / SIP
# ==========================================================================


class TestTwilioBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = TwilioSerializer()
        s.stream_sid = "MZ123"
        s.call_sid = "CA456"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="CA456")
        result = await serializer.serialize(event)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["event"] == "clear"
        assert parsed["streamSid"] == "MZ123"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="CA456", name="greeting_done")
        result = await serializer.serialize(event)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["event"] == "mark"
        assert parsed["streamSid"] == "MZ123"
        assert parsed["mark"]["name"] == "greeting_done"

    @pytest.mark.asyncio
    async def test_deserialize_mark_event(self, serializer):
        msg = {
            "event": "mark",
            "streamSid": "MZ123",
            "mark": {"name": "sentence_end"},
        }
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], Mark)
        assert events[0].name == "sentence_end"
        assert events[0].call_id == "CA456"

    @pytest.mark.asyncio
    async def test_sip_headers_from_custom_parameters(self, serializer):
        msg = {
            "event": "start",
            "start": {
                "streamSid": "MZ123",
                "callSid": "CA456",
                "customParameters": {
                    "sip_from_display": "John Doe",
                    "X-Custom-Header": "custom_value",
                    "bot_name": "test",  # should NOT be in sip_headers
                },
            },
        }
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "sip_from_display" in event.sip_headers
        assert "X-Custom-Header" in event.sip_headers
        assert "bot_name" not in event.sip_headers

    def test_build_clear_message(self, serializer):
        msg = serializer.build_clear_message()
        parsed = json.loads(msg)
        assert parsed["event"] == "clear"
        assert parsed["streamSid"] == "MZ123"

    def test_build_mark_message(self, serializer):
        msg = serializer.build_mark_message("end_of_greeting")
        parsed = json.loads(msg)
        assert parsed["event"] == "mark"
        assert parsed["mark"]["name"] == "end_of_greeting"


# ==========================================================================
# Genesys Serializer - Barge-In / Mark / Clear / SIP
# ==========================================================================


class TestGenesysBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = GenesysSerializer()
        s.session_id = "sess-001"
        s.conversation_id = "conv-456"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="conv-456")
        result = await serializer.serialize(event)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["type"] == "discardAudio"
        assert parsed["id"] == "sess-001"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="conv-456", name="mark_1")
        result = await serializer.serialize(event)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["type"] == "position"
        assert parsed["parameters"]["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_participant(self, serializer):
        msg = {
            "type": "open",
            "id": "sess-001",
            "parameters": {
                "conversationId": "conv-456",
                "organizationId": "org-123",
                "participant": {
                    "sip_from_display": "Agent Smith",
                    "x-custom-header": "value",
                    "ani": "+1555",  # should NOT be in sip_headers
                },
            },
        }
        events = await serializer.deserialize(json.dumps(msg))
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "sip_from_display" in event.sip_headers
        assert "x-custom-header" in event.sip_headers
        assert "ani" not in event.sip_headers

    def test_build_discard_audio(self, serializer):
        msg = serializer.build_discard_audio_message()
        parsed = json.loads(msg)
        assert parsed["type"] == "discardAudio"

    def test_build_position(self, serializer):
        msg = serializer.build_position_message("pos_1")
        parsed = json.loads(msg)
        assert parsed["type"] == "position"
        assert parsed["parameters"]["name"] == "pos_1"


# ==========================================================================
# Generic WS Serializer - Barge-In / Mark / Clear / SIP
# ==========================================================================


class TestGenericBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = GenericWebSocketSerializer()
        s._call_id = "call-1"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="call-1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "clear"
        assert parsed["call_id"] == "call-1"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="call-1", name="my_mark")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "mark"
        assert parsed["name"] == "my_mark"

    @pytest.mark.asyncio
    async def test_deserialize_mark(self, serializer):
        msg = {"type": "mark", "name": "test_mark"}
        events = await serializer.deserialize(json.dumps(msg))
        assert len(events) == 1
        assert isinstance(events[0], Mark)
        assert events[0].name == "test_mark"

    @pytest.mark.asyncio
    async def test_sip_headers_in_start(self, serializer):
        msg = {
            "type": "start",
            "call_id": "call-1",
            "sip_headers": {
                "X-Bot-ID": "bot-123",
                "sip_custom": "value",
            },
        }
        events = await serializer.deserialize(json.dumps(msg))
        event = events[0]
        assert isinstance(event, CallStarted)
        assert event.sip_headers["X-Bot-ID"] == "bot-123"
        assert event.sip_headers["sip_custom"] == "value"


# ==========================================================================
# FreeSWITCH Serializer - ClearAudio / Mark / SIP
# ==========================================================================


class TestFreeSwitchBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = FreeSwitchSerializer()
        s._uuid = "fs-uuid-123"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="fs-uuid-123")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["command"] == "break"
        assert parsed["uuid"] == "fs-uuid-123"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="fs-uuid-123", name="mark_1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["command"] == "mark"
        assert parsed["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_connect(self, serializer):
        msg = {
            "event": "connect",
            "uuid": "fs-uuid-123",
            "caller_id": "+1555",
            "variable_sip_h_X-Custom": "hello",
            "sip_from_user": "agent",
        }
        events = await serializer.deserialize(msg)
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "variable_sip_h_X-Custom" in event.sip_headers
        assert "sip_from_user" in event.sip_headers


# ==========================================================================
# Amazon Connect Serializer - ClearAudio / Mark / SIP
# ==========================================================================


class TestAmazonConnectBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = AmazonConnectSerializer()
        s._contact_id = "ct-789"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="ct-789")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["event"] == "CLEAR_AUDIO"
        assert parsed["contactId"] == "ct-789"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="ct-789", name="mark_1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["event"] == "MARK"
        assert parsed["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_attributes(self, serializer):
        msg = {
            "event": "STARTED",
            "contactId": "ct-789",
            "instanceId": "inst-001",
            "contactAttributes": {
                "customerNumber": "+1555",
                "sip_from_display": "caller",
                "X-Routing-Key": "vip",
            },
        }
        events = await serializer.deserialize(msg)
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "sip_from_display" in event.sip_headers
        assert "X-Routing-Key" in event.sip_headers
        assert "customerNumber" not in event.sip_headers


# ==========================================================================
# Avaya Serializer - ClearAudio / Mark / SIP
# ==========================================================================


class TestAvayaBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = AvayaSerializer()
        s._session_id = "avaya-sess-1"
        s._call_id = "avaya-call-1"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="avaya-call-1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "audio.clear"
        assert parsed["sessionId"] == "avaya-sess-1"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="avaya-call-1", name="mark_1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "audio.mark"
        assert parsed["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_parameters(self, serializer):
        msg = {
            "type": "session.start",
            "sessionId": "avaya-sess-1",
            "callId": "avaya-call-1",
            "parameters": {
                "callerNumber": "+1555",
                "sip_contact": "agent@pbx",
                "X-Enterprise-ID": "ent-1",
            },
        }
        events = await serializer.deserialize(msg)
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "sip_contact" in event.sip_headers
        assert "X-Enterprise-ID" in event.sip_headers
        assert "callerNumber" not in event.sip_headers


# ==========================================================================
# Cisco Serializer - ClearAudio / Mark / SIP
# ==========================================================================


class TestCiscoBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = CiscoSerializer()
        s._interaction_id = "cisco-int-1"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="cisco-int-1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["event"] == "audio.clear"
        assert parsed["interactionId"] == "cisco-int-1"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="cisco-int-1", name="mark_1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["event"] == "audio.mark"
        assert parsed["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_call_data(self, serializer):
        msg = {
            "event": "call.new",
            "interactionId": "cisco-int-1",
            "data": {
                "ani": "+1555",
                "dnis": "+1666",
                "sip_contact": "agent@cc",
                "X-Skill-Group": "premium",
            },
        }
        events = await serializer.deserialize(msg)
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "sip_contact" in event.sip_headers
        assert "X-Skill-Group" in event.sip_headers
        assert "ani" not in event.sip_headers


# ==========================================================================
# Asterisk Serializer - ClearAudio / Mark / SIP
# ==========================================================================


class TestAsteriskBargeInFeatures:

    @pytest.fixture
    def serializer(self):
        s = AsteriskSerializer()
        s._channel_id = "chan-123"
        return s

    @pytest.mark.asyncio
    async def test_serialize_clear_audio(self, serializer):
        event = ClearAudio(call_id="chan-123")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "PlaybackControl"
        assert parsed["operation"] == "stop"

    @pytest.mark.asyncio
    async def test_serialize_mark(self, serializer):
        event = Mark(call_id="chan-123", name="mark_1")
        result = await serializer.serialize(event)
        parsed = json.loads(result)
        assert parsed["type"] == "Mark"
        assert parsed["name"] == "mark_1"

    @pytest.mark.asyncio
    async def test_sip_headers_from_stasis_start(self, serializer):
        msg = {
            "type": "StasisStart",
            "channel": {
                "id": "chan-123",
                "name": "PJSIP/test",
                "caller": {"number": "+1555"},
                "connected": {"number": "+1666"},
                "channelvars": {
                    "PJSIP_HEADER(read,X-Custom)": "value",
                    "SIP_HEADER(From)": "sip:user@domain",
                    "DIALPLAN_CONTEXT": "default",  # should NOT be in sip_headers
                },
            },
            "args": [],
        }
        events = await serializer.deserialize(msg)
        event = events[0]
        assert isinstance(event, CallStarted)
        assert "PJSIP_HEADER(read,X-Custom)" in event.sip_headers
        assert "SIP_HEADER(From)" in event.sip_headers
        assert "DIALPLAN_CONTEXT" not in event.sip_headers


# ==========================================================================
# __init__.py Export Tests
# ==========================================================================


class TestExports:

    def test_barge_in_exported(self):
        from voxbridge import BargeIn
        assert BargeIn is not None

    def test_clear_audio_exported(self):
        from voxbridge import ClearAudio
        assert ClearAudio is not None

    def test_mark_exported(self):
        from voxbridge import Mark
        assert Mark is not None

    def test_barge_in_detector_exported(self):
        from voxbridge import BargeInDetector
        assert BargeInDetector is not None

    def test_compute_audio_energy_exported(self):
        from voxbridge import compute_audio_energy
        assert compute_audio_energy is not None
