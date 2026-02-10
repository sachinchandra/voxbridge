"""Tests for VoxBridge serializers."""

import base64
import json

import pytest

from voxbridge.core.events import (
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    CustomEvent,
    DTMFReceived,
    HoldEnded,
    HoldStarted,
)
from voxbridge.serializers.twilio import TwilioSerializer
from voxbridge.serializers.genesys import GenesysSerializer
from voxbridge.serializers.generic_ws import GenericWebSocketSerializer
from voxbridge.serializers.freeswitch import FreeSwitchSerializer
from voxbridge.serializers.asterisk import AsteriskSerializer
from voxbridge.serializers.amazon_connect import AmazonConnectSerializer
from voxbridge.serializers.avaya import AvayaSerializer
from voxbridge.serializers.cisco import CiscoSerializer
from voxbridge.serializers.registry import SerializerRegistry


# ==========================================================================
# Twilio Serializer Tests
# ==========================================================================


class TestTwilioSerializer:

    @pytest.fixture
    def serializer(self):
        return TwilioSerializer()

    @pytest.mark.asyncio
    async def test_connected_event(self, serializer):
        msg = json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        events = await serializer.deserialize(msg)
        assert events == []

    @pytest.mark.asyncio
    async def test_start_event(self, serializer):
        msg = {
            "event": "start",
            "start": {
                "streamSid": "MZ123",
                "callSid": "CA456",
                "accountSid": "AC789",
                "customParameters": {"bot_name": "test"},
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
            },
        }
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "CA456"
        assert events[0].provider == "twilio"
        assert serializer.stream_sid == "MZ123"
        assert serializer.call_sid == "CA456"

    @pytest.mark.asyncio
    async def test_media_event(self, serializer):
        serializer.call_sid = "CA456"
        audio_bytes = b"\xff\x00\x01\x02"
        msg = {
            "event": "media",
            "streamSid": "MZ123",
            "media": {
                "payload": base64.b64encode(audio_bytes).decode(),
                "timestamp": "1234",
                "chunk": "1",
            },
        }
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], AudioFrame)
        assert events[0].codec == Codec.MULAW
        assert events[0].data == audio_bytes

    @pytest.mark.asyncio
    async def test_dtmf_event(self, serializer):
        serializer.call_sid = "CA456"
        msg = {"event": "dtmf", "dtmf": {"digit": "5"}, "streamSid": "MZ123"}
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], DTMFReceived)
        assert events[0].digit == "5"

    @pytest.mark.asyncio
    async def test_stop_event(self, serializer):
        serializer.call_sid = "CA456"
        msg = {"event": "stop", "streamSid": "MZ123"}
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], CallEnded)

    @pytest.mark.asyncio
    async def test_serialize_audio(self, serializer):
        serializer.stream_sid = "MZ123"
        frame = AudioFrame(data=b"\xff\x00", codec=Codec.MULAW)
        result = await serializer.serialize(frame)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["event"] == "media"
        assert parsed["streamSid"] == "MZ123"
        payload = base64.b64decode(parsed["media"]["payload"])
        assert payload == b"\xff\x00"

    def test_properties(self, serializer):
        assert serializer.name == "twilio"
        assert serializer.audio_codec == Codec.MULAW
        assert serializer.sample_rate == 8000

    def test_handshake(self, serializer):
        assert serializer.handshake_response({"event": "connected"}) is None


# ==========================================================================
# Genesys Serializer Tests
# ==========================================================================


class TestGenesysSerializer:

    @pytest.fixture
    def serializer(self):
        return GenesysSerializer()

    @pytest.mark.asyncio
    async def test_open_event(self, serializer):
        msg = {
            "type": "open",
            "id": "sess-001",
            "position": 0,
            "parameters": {
                "organizationId": "org-123",
                "conversationId": "conv-456",
                "participant": {"ani": "+1555", "dnis": "+1666"},
            },
        }
        events = await serializer.deserialize(json.dumps(msg))
        assert len(events) == 1
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "conv-456"
        assert events[0].provider == "genesys"

    @pytest.mark.asyncio
    async def test_binary_audio(self, serializer):
        serializer.conversation_id = "conv-456"
        events = await serializer.deserialize(b"\xff\x00\x01")
        assert len(events) == 1
        assert isinstance(events[0], AudioFrame)
        assert events[0].codec == Codec.MULAW
        assert events[0].data == b"\xff\x00\x01"

    @pytest.mark.asyncio
    async def test_close_event(self, serializer):
        serializer.conversation_id = "conv-456"
        msg = {"type": "close", "id": "sess-001", "parameters": {"reason": "completed"}}
        events = await serializer.deserialize(json.dumps(msg))
        assert len(events) == 1
        assert isinstance(events[0], CallEnded)
        assert events[0].reason == "completed"

    @pytest.mark.asyncio
    async def test_dtmf_event(self, serializer):
        serializer.conversation_id = "conv-456"
        msg = {"type": "dtmf", "id": "sess-001", "parameters": {"digit": "3"}}
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], DTMFReceived)
        assert events[0].digit == "3"

    @pytest.mark.asyncio
    async def test_pause_resume(self, serializer):
        serializer.conversation_id = "conv-456"
        pause_events = await serializer.deserialize({"type": "pause"})
        assert isinstance(pause_events[0], HoldStarted)
        resume_events = await serializer.deserialize({"type": "resume"})
        assert isinstance(resume_events[0], HoldEnded)

    @pytest.mark.asyncio
    async def test_ping_ignored(self, serializer):
        msg = {"type": "ping", "id": "sess-001"}
        events = await serializer.deserialize(msg)
        assert events == []

    def test_handshake_open(self, serializer):
        msg = {
            "type": "open",
            "id": "sess-001",
            "parameters": {"conversationId": "conv-456"},
        }
        response = serializer.handshake_response(msg)
        assert response is not None
        assert response["type"] == "opened"
        assert response["id"] == "sess-001"

    def test_handshake_ping(self, serializer):
        msg = {"type": "ping", "id": "sess-001"}
        response = serializer.handshake_response(msg)
        assert response == {"type": "pong", "id": "sess-001"}

    def test_handshake_close(self, serializer):
        msg = {"type": "close", "id": "sess-001"}
        response = serializer.handshake_response(msg)
        assert response == {"type": "closed", "id": "sess-001"}

    @pytest.mark.asyncio
    async def test_serialize_audio(self, serializer):
        frame = AudioFrame(data=b"\xff\x00", codec=Codec.MULAW)
        result = await serializer.serialize(frame)
        assert result == b"\xff\x00"

    def test_properties(self, serializer):
        assert serializer.name == "genesys"
        assert serializer.audio_codec == Codec.MULAW
        assert serializer.sample_rate == 8000


# ==========================================================================
# Generic WebSocket Serializer Tests
# ==========================================================================


class TestGenericSerializer:

    @pytest.fixture
    def serializer(self):
        return GenericWebSocketSerializer()

    @pytest.mark.asyncio
    async def test_binary_audio(self, serializer):
        events = await serializer.deserialize(b"\x00\x01\x02\x03")
        assert len(events) == 1
        assert isinstance(events[0], AudioFrame)
        assert events[0].codec == Codec.PCM16

    @pytest.mark.asyncio
    async def test_start_event(self, serializer):
        msg = {"type": "start", "call_id": "call-1", "from": "+1555", "to": "+1666"}
        events = await serializer.deserialize(json.dumps(msg))
        assert len(events) == 1
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "call-1"

    @pytest.mark.asyncio
    async def test_stop_event(self, serializer):
        msg = {"type": "stop", "call_id": "call-1"}
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], CallEnded)

    def test_properties(self, serializer):
        assert serializer.name == "generic"
        assert serializer.audio_codec == Codec.PCM16
        assert serializer.sample_rate == 16000

    def test_custom_codec(self):
        s = GenericWebSocketSerializer(codec=Codec.MULAW, rate=8000)
        assert s.audio_codec == Codec.MULAW
        assert s.sample_rate == 8000


# ==========================================================================
# FreeSWITCH Serializer Tests
# ==========================================================================


class TestFreeSwitchSerializer:

    @pytest.fixture
    def serializer(self):
        return FreeSwitchSerializer()

    @pytest.mark.asyncio
    async def test_connect_event(self, serializer):
        msg = {"event": "connect", "uuid": "fs-uuid-123", "caller_id": "+1555"}
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "fs-uuid-123"

    @pytest.mark.asyncio
    async def test_binary_audio(self, serializer):
        events = await serializer.deserialize(b"\xff\x00")
        assert isinstance(events[0], AudioFrame)
        assert events[0].codec == Codec.MULAW

    @pytest.mark.asyncio
    async def test_disconnect_event(self, serializer):
        msg = {"event": "disconnect", "uuid": "fs-uuid-123", "cause": "NORMAL_CLEARING"}
        events = await serializer.deserialize(msg)
        assert isinstance(events[0], CallEnded)

    def test_properties(self, serializer):
        assert serializer.name == "freeswitch"
        assert serializer.audio_codec == Codec.MULAW


# ==========================================================================
# Asterisk Serializer Tests
# ==========================================================================


class TestAsteriskSerializer:

    @pytest.fixture
    def serializer(self):
        return AsteriskSerializer()

    @pytest.mark.asyncio
    async def test_stasis_start(self, serializer):
        msg = {
            "type": "StasisStart",
            "channel": {
                "id": "chan-123",
                "name": "SIP/test-001",
                "caller": {"number": "+1555"},
                "connected": {"number": "+1666"},
            },
            "args": [],
        }
        events = await serializer.deserialize(msg)
        assert len(events) == 1
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "chan-123"

    @pytest.mark.asyncio
    async def test_dtmf(self, serializer):
        msg = {
            "type": "ChannelDtmfReceived",
            "channel": {"id": "chan-123"},
            "digit": "9",
        }
        events = await serializer.deserialize(msg)
        assert isinstance(events[0], DTMFReceived)
        assert events[0].digit == "9"

    @pytest.mark.asyncio
    async def test_hold_unhold(self, serializer):
        serializer._channel_id = "chan-123"
        hold = await serializer.deserialize({"type": "ChannelHold", "channel": {"id": "chan-123"}})
        assert isinstance(hold[0], HoldStarted)
        unhold = await serializer.deserialize({"type": "ChannelUnhold", "channel": {"id": "chan-123"}})
        assert isinstance(unhold[0], HoldEnded)

    def test_properties(self, serializer):
        assert serializer.name == "asterisk"


# ==========================================================================
# Amazon Connect Serializer Tests
# ==========================================================================


class TestAmazonConnectSerializer:

    @pytest.fixture
    def serializer(self):
        return AmazonConnectSerializer()

    @pytest.mark.asyncio
    async def test_started_event(self, serializer):
        msg = {
            "event": "STARTED",
            "contactId": "ct-789",
            "instanceId": "inst-001",
            "contactAttributes": {"customerNumber": "+1555"},
        }
        events = await serializer.deserialize(msg)
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "ct-789"
        assert events[0].provider == "amazon_connect"

    @pytest.mark.asyncio
    async def test_binary_audio(self, serializer):
        serializer._contact_id = "ct-789"
        events = await serializer.deserialize(b"\x00\x01")
        assert isinstance(events[0], AudioFrame)
        assert events[0].codec == Codec.PCM16

    def test_properties(self, serializer):
        assert serializer.name == "amazon_connect"
        assert serializer.audio_codec == Codec.PCM16
        assert serializer.sample_rate == 8000


# ==========================================================================
# Avaya Serializer Tests
# ==========================================================================


class TestAvayaSerializer:

    @pytest.fixture
    def serializer(self):
        return AvayaSerializer()

    @pytest.mark.asyncio
    async def test_session_start(self, serializer):
        msg = {
            "type": "session.start",
            "sessionId": "avaya-sess-1",
            "callId": "avaya-call-1",
            "parameters": {"callerNumber": "+1555", "calledNumber": "+1666"},
        }
        events = await serializer.deserialize(msg)
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "avaya-call-1"

    @pytest.mark.asyncio
    async def test_hold_unhold(self, serializer):
        serializer._call_id = "test"
        hold = await serializer.deserialize({"type": "hold"})
        assert isinstance(hold[0], HoldStarted)
        unhold = await serializer.deserialize({"type": "unhold"})
        assert isinstance(unhold[0], HoldEnded)

    def test_properties(self, serializer):
        assert serializer.name == "avaya"


# ==========================================================================
# Cisco Serializer Tests
# ==========================================================================


class TestCiscoSerializer:

    @pytest.fixture
    def serializer(self):
        return CiscoSerializer()

    @pytest.mark.asyncio
    async def test_call_new(self, serializer):
        msg = {
            "event": "call.new",
            "interactionId": "cisco-int-1",
            "data": {"ani": "+1555", "dnis": "+1666"},
        }
        events = await serializer.deserialize(msg)
        assert isinstance(events[0], CallStarted)
        assert events[0].call_id == "cisco-int-1"
        assert events[0].provider == "cisco"

    @pytest.mark.asyncio
    async def test_hold_retrieved(self, serializer):
        serializer._interaction_id = "test"
        hold = await serializer.deserialize({"event": "call.held"})
        assert isinstance(hold[0], HoldStarted)
        retrieve = await serializer.deserialize({"event": "call.retrieved"})
        assert isinstance(retrieve[0], HoldEnded)

    def test_properties(self, serializer):
        assert serializer.name == "cisco"


# ==========================================================================
# Serializer Registry Tests
# ==========================================================================


class TestSerializerRegistry:

    def test_available_providers(self):
        registry = SerializerRegistry()
        available = registry.available
        assert "twilio" in available
        assert "genesys" in available
        assert "generic" in available
        assert "freeswitch" in available
        assert "asterisk" in available
        assert "amazon_connect" in available
        assert "avaya" in available
        assert "cisco" in available

    def test_create_twilio(self):
        registry = SerializerRegistry()
        s = registry.create("twilio")
        assert s.name == "twilio"

    def test_create_genesys(self):
        registry = SerializerRegistry()
        s = registry.create("genesys")
        assert s.name == "genesys"

    def test_unknown_provider_raises(self):
        registry = SerializerRegistry()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.get("nonexistent")

    def test_register_custom(self):
        from voxbridge.serializers.base import BaseSerializer

        class MySerializer(BaseSerializer):
            @property
            def name(self): return "my_provider"
            @property
            def audio_codec(self): return Codec.PCM16
            @property
            def sample_rate(self): return 16000
            async def deserialize(self, raw): return []
            async def serialize(self, event): return None
            def handshake_response(self, msg): return None

        registry = SerializerRegistry()
        registry.register("my_provider", MySerializer)
        assert "my_provider" in registry.available
        s = registry.create("my_provider")
        assert s.name == "my_provider"
