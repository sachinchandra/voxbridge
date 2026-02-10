"""Tests for the VoxBridge bridge orchestrator and config system."""

import pytest

from voxbridge.config import BridgeConfig, load_config, DEFAULT_CONFIG_YAML
from voxbridge.session import CallSession, SessionStore
from voxbridge.core.events import Codec


class TestBridgeConfig:

    def test_default_config(self):
        config = BridgeConfig()
        assert config.provider.type == "twilio"
        assert config.provider.listen_port == 8765
        assert config.bot.url == "ws://localhost:9000/ws"
        assert config.bot.codec == "pcm16"

    def test_from_dict_full(self):
        config = BridgeConfig.from_dict({
            "provider": {"type": "genesys", "listen_port": 9000},
            "bot": {"url": "ws://mybot:8080/ws", "codec": "mulaw"},
        })
        assert config.provider.type == "genesys"
        assert config.provider.listen_port == 9000
        assert config.bot.url == "ws://mybot:8080/ws"

    def test_from_dict_shorthand(self):
        config = BridgeConfig.from_dict({
            "provider": "twilio",
            "listen_port": 8765,
            "bot_url": "ws://localhost:9000/ws",
        })
        assert config.provider.type == "twilio"
        assert config.provider.listen_port == 8765
        assert config.bot.url == "ws://localhost:9000/ws"

    def test_load_config_from_dict(self):
        config = load_config({"provider": "genesys"})
        assert config.provider.type == "genesys"

    def test_load_config_from_bridgeconfig(self):
        original = BridgeConfig()
        config = load_config(original)
        assert config is original

    def test_load_config_from_string_provider(self):
        # When a string that's not a file path is given, treat it as provider name
        config = load_config("twilio")
        assert config.provider.type == "twilio"

    def test_default_yaml_is_valid(self):
        """The default YAML template should parse into a valid config."""
        import yaml
        data = yaml.safe_load(DEFAULT_CONFIG_YAML)
        config = BridgeConfig.from_dict(data)
        assert config.provider.type == "twilio"
        assert config.audio.input_codec == "mulaw"


class TestCallSession:

    def test_session_defaults(self):
        session = CallSession()
        assert session.is_active is True
        assert session.is_on_hold is False
        assert session.call_id == ""
        assert session.duration_ms > 0 or session.duration_ms == 0

    def test_session_end(self):
        session = CallSession()
        assert session.is_active is True
        session.end()
        assert session.is_active is False
        assert session.ended_at is not None

    def test_codec_conversion_same(self):
        session = CallSession()
        data = b"\x01\x02\x03\x04"
        result = session.convert_inbound_audio(data, Codec.PCM16, Codec.PCM16)
        assert result == data

    def test_resample_setup(self):
        session = CallSession()
        session.setup_resamplers(8000, 16000)
        assert session._inbound_resampler is not None
        assert session._outbound_resampler is not None

    def test_no_resample_same_rate(self):
        session = CallSession()
        session.setup_resamplers(8000, 8000)
        assert session._inbound_resampler is None
        assert session._outbound_resampler is None


class TestSessionStore:

    def test_create_and_get(self):
        store = SessionStore()
        session = store.create(call_id="call-1")
        assert store.get(session.session_id) is session
        assert store.get_by_call_id("call-1") is session

    def test_active_count(self):
        store = SessionStore()
        store.create(call_id="call-1")
        store.create(call_id="call-2")
        assert store.active_count == 2

    def test_remove(self):
        store = SessionStore()
        session = store.create(call_id="call-1")
        store.remove(session.session_id)
        assert store.get(session.session_id) is None
        assert store.active_count == 0

    def test_cleanup(self):
        store = SessionStore()
        s1 = store.create(call_id="call-1")
        s2 = store.create(call_id="call-2")
        s1.end()
        removed = store.cleanup()
        assert removed == 1
        assert store.active_count == 1
