"""Tests for the VoxBridge AI Pipeline engine.

Tests cover:
- Provider base interfaces and data classes
- Provider registry and factory
- ConversationContext management
- TurnDetector behavior
- EscalationDetector logic
- PipelineConfig construction
- Pipeline integration with bridge config
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from voxbridge.providers.base import (
    BaseSTT,
    BaseLLM,
    BaseTTS,
    STTResult,
    LLMChunk,
    LLMToolCall,
    TTSChunk,
    Message,
)
from voxbridge.providers.registry import ProviderRegistry, provider_registry
from voxbridge.pipeline.context import ConversationContext
from voxbridge.pipeline.turn_detector import TurnDetector
from voxbridge.pipeline.escalation import EscalationDetector, EscalationResult
from voxbridge.pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from voxbridge.config import (
    BridgeConfig,
    PipelineModeConfig,
    PipelineProviderConfig,
)


# =========================================================================
# Data class tests
# =========================================================================


class TestSTTResult:
    """Tests for STTResult data class."""

    def test_default_values(self):
        result = STTResult(text="hello")
        assert result.text == "hello"
        assert result.is_final is False
        assert result.confidence == 0.0
        assert result.language == ""
        assert result.words == []

    def test_final_result(self):
        result = STTResult(
            text="How can I help you?",
            is_final=True,
            confidence=0.95,
            language="en-US",
            words=[{"word": "How", "start": 0.0, "end": 0.2, "confidence": 0.98}],
        )
        assert result.is_final is True
        assert result.confidence == 0.95
        assert len(result.words) == 1


class TestLLMChunk:
    """Tests for LLMChunk data class."""

    def test_text_chunk(self):
        chunk = LLMChunk(text="Hello")
        assert chunk.text == "Hello"
        assert chunk.is_final is False
        assert chunk.tool_call_id == ""

    def test_tool_call_chunk(self):
        chunk = LLMChunk(
            tool_call_id="tc_123",
            tool_name="lookup_order",
            tool_arguments='{"order_id": "123"}',
        )
        assert chunk.tool_call_id == "tc_123"
        assert chunk.tool_name == "lookup_order"

    def test_final_chunk_with_usage(self):
        chunk = LLMChunk(is_final=True, input_tokens=150, output_tokens=80)
        assert chunk.is_final is True
        assert chunk.input_tokens == 150
        assert chunk.output_tokens == 80


class TestLLMToolCall:
    """Tests for LLMToolCall data class."""

    def test_tool_call(self):
        tc = LLMToolCall(
            id="tc_123",
            name="get_weather",
            arguments={"city": "San Francisco"},
        )
        assert tc.id == "tc_123"
        assert tc.name == "get_weather"
        assert tc.arguments["city"] == "San Francisco"


class TestTTSChunk:
    """Tests for TTSChunk data class."""

    def test_audio_chunk(self):
        chunk = TTSChunk(audio=b"\x00\x01\x02", sample_rate=24000)
        assert chunk.audio == b"\x00\x01\x02"
        assert chunk.sample_rate == 24000
        assert chunk.is_final is False

    def test_final_chunk(self):
        chunk = TTSChunk(audio=b"", sample_rate=24000, is_final=True)
        assert chunk.is_final is True


class TestMessage:
    """Tests for Message data class."""

    def test_user_message(self):
        msg = Message(role="user", content="What's my order status?")
        assert msg.role == "user"
        assert msg.content == "What's my order status?"
        assert msg.tool_calls == []

    def test_system_message(self):
        msg = Message(role="system", content="You are a helpful agent.")
        assert msg.role == "system"

    def test_assistant_message_with_tools(self):
        tc = LLMToolCall(id="tc_1", name="check_order", arguments={"id": "123"})
        msg = Message(role="assistant", content="Let me check.", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "check_order"

    def test_tool_result_message(self):
        msg = Message(role="tool", content='{"status": "shipped"}', tool_call_id="tc_1", name="check_order")
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc_1"


# =========================================================================
# Provider registry tests
# =========================================================================


class TestProviderRegistry:
    """Tests for the ProviderRegistry factory."""

    def test_available_providers(self):
        registry = ProviderRegistry()
        assert "deepgram" in registry.available_stt
        assert "openai" in registry.available_llm
        assert "anthropic" in registry.available_llm
        assert "elevenlabs" in registry.available_tts

    def test_unknown_stt_provider(self):
        registry = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown STT provider"):
            registry.create_stt("nonexistent")

    def test_unknown_llm_provider(self):
        registry = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            registry.create_llm("nonexistent")

    def test_unknown_tts_provider(self):
        registry = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            registry.create_tts("nonexistent")

    def test_register_custom_stt(self):
        registry = ProviderRegistry()

        class CustomSTT(BaseSTT):
            async def connect(self): pass
            async def send_audio(self, audio): pass
            async def results(self):
                yield STTResult(text="test")
            async def close(self): pass
            @property
            def sample_rate(self): return 16000
            @property
            def codec(self): return "pcm16"

        registry.register_stt("custom", CustomSTT)
        assert "custom" in registry.available_stt
        stt = registry.create_stt("custom")
        assert isinstance(stt, CustomSTT)

    def test_register_custom_llm(self):
        registry = ProviderRegistry()

        class CustomLLM(BaseLLM):
            async def generate(self, messages, tools=None, temperature=0.7, max_tokens=1024):
                yield LLMChunk(text="test", is_final=True)
            @property
            def model(self): return "custom-1"

        registry.register_llm("custom", CustomLLM)
        assert "custom" in registry.available_llm
        llm = registry.create_llm("custom")
        assert isinstance(llm, CustomLLM)
        assert llm.model == "custom-1"

    def test_register_custom_tts(self):
        registry = ProviderRegistry()

        class CustomTTS(BaseTTS):
            async def connect(self): pass
            async def synthesize(self, text):
                yield TTSChunk(audio=b"audio")
            async def close(self): pass
            async def flush(self):
                yield TTSChunk(audio=b"", is_final=True)
            @property
            def sample_rate(self): return 22050
            @property
            def codec(self): return "pcm16"

        registry.register_tts("custom", CustomTTS)
        assert "custom" in registry.available_tts

    def test_global_registry_exists(self):
        assert provider_registry is not None
        assert "deepgram" in provider_registry.available_stt


# =========================================================================
# Conversation context tests
# =========================================================================


class TestConversationContext:
    """Tests for ConversationContext management."""

    def test_init_with_system_prompt(self):
        ctx = ConversationContext(system_prompt="You are a helpful agent.")
        assert ctx.message_count == 1
        msgs = ctx.get_messages()
        assert msgs[0].role == "system"
        assert msgs[0].content == "You are a helpful agent."

    def test_init_with_first_message(self):
        ctx = ConversationContext(
            system_prompt="You are helpful.",
            first_message="Hello! How can I help?",
        )
        assert ctx.message_count == 2
        msgs = ctx.get_messages()
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "Hello! How can I help?"

    def test_add_user_message(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.add_user_message("What is my order status?")
        assert ctx.message_count == 2
        assert ctx.last_user_message == "What is my order status?"

    def test_add_assistant_message(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.add_assistant_message("Your order is on the way!")
        assert ctx.message_count == 2
        assert ctx.last_assistant_message == "Your order is on the way!"

    def test_empty_assistant_message_ignored(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.add_assistant_message("")
        ctx.add_assistant_message("   ")
        assert ctx.message_count == 1  # Only system

    def test_tool_call_flow(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.add_user_message("Check my order 123")

        tc = LLMToolCall(id="tc_1", name="check_order", arguments={"id": "123"})
        ctx.add_assistant_tool_calls("Let me check.", [tc])

        ctx.add_tool_result("tc_1", "check_order", {"status": "shipped"})
        assert ctx.message_count == 4

    def test_get_transcript(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.add_user_message("Hello")
        ctx.add_assistant_message("Hi there!")
        transcript = ctx.get_transcript()
        assert len(transcript) == 2
        assert transcript[0] == {"role": "user", "content": "Hello"}
        assert transcript[1] == {"role": "assistant", "content": "Hi there!"}

    def test_token_usage_tracking(self):
        ctx = ConversationContext(system_prompt="test")
        ctx.update_token_usage(100, 50)
        ctx.update_token_usage(120, 60)
        assert ctx.total_tokens == 330

    def test_trim_by_message_count(self):
        ctx = ConversationContext(system_prompt="test", max_messages=5)
        for i in range(10):
            ctx.add_user_message(f"Message {i}")
        # Should be: system + last 4 user messages
        assert ctx.message_count <= 5

    def test_trim_by_char_count(self):
        ctx = ConversationContext(system_prompt="test", max_context_chars=100)
        for i in range(20):
            ctx.add_user_message("A" * 20)
        # Should have trimmed old messages
        total_chars = sum(len(m.content) for m in ctx.get_messages())
        assert total_chars <= 120  # Some tolerance

    def test_clear(self):
        ctx = ConversationContext(system_prompt="Keep me")
        ctx.add_user_message("Remove me")
        ctx.add_assistant_message("Remove me too")
        ctx.clear()
        assert ctx.message_count == 1
        assert ctx.get_messages()[0].role == "system"

    def test_get_tools(self):
        tools = [{"type": "function", "function": {"name": "test"}}]
        ctx = ConversationContext(system_prompt="test", tools=tools)
        assert ctx.get_tools() == tools

    def test_get_tools_none(self):
        ctx = ConversationContext(system_prompt="test")
        assert ctx.get_tools() is None


# =========================================================================
# Turn detector tests
# =========================================================================


class TestTurnDetector:
    """Tests for TurnDetector behavior."""

    def test_default_settings(self):
        td = TurnDetector()
        assert td.silence_threshold_ms == 700.0
        assert td.min_turn_length == 2
        assert not td.is_speaking

    @pytest.mark.asyncio
    async def test_final_stt_result_triggers_callback(self):
        td = TurnDetector()
        received_text = []

        async def on_turn_end(text):
            received_text.append(text)

        td.set_turn_end_callback(on_turn_end)

        # Send interim result
        await td.on_stt_result(STTResult(text="Hello", is_final=False))
        assert td.is_speaking

        # Send final result
        await td.on_stt_result(STTResult(text="Hello world", is_final=True))

        # Empty final triggers turn end
        await td.on_stt_result(STTResult(text="", is_final=True))

        assert len(received_text) == 1
        assert received_text[0] == "Hello world"

    @pytest.mark.asyncio
    async def test_short_turn_ignored(self):
        td = TurnDetector(min_turn_length=5)
        received_text = []

        async def on_turn_end(text):
            received_text.append(text)

        td.set_turn_end_callback(on_turn_end)

        await td.on_stt_result(STTResult(text="Hi", is_final=True))
        await td.on_stt_result(STTResult(text="", is_final=True))

        assert len(received_text) == 0

    def test_reset(self):
        td = TurnDetector()
        td._current_transcript = "some text"
        td._is_speaking = True
        td.reset()
        assert td.current_text == ""
        assert not td.is_speaking

    def test_cancel(self):
        td = TurnDetector()
        td._is_speaking = True
        td._current_transcript = "interrupted"
        td.cancel()
        assert not td.is_speaking
        assert td.current_text == ""

    @pytest.mark.asyncio
    async def test_accumulates_final_results(self):
        td = TurnDetector()
        received_text = []

        async def on_turn_end(text):
            received_text.append(text)

        td.set_turn_end_callback(on_turn_end)

        await td.on_stt_result(STTResult(text="I need", is_final=True))
        await td.on_stt_result(STTResult(text="help with my order", is_final=True))
        await td.on_stt_result(STTResult(text="", is_final=True))

        assert len(received_text) == 1
        assert "I need" in received_text[0]
        assert "help with my order" in received_text[0]

    def test_current_text_includes_interim(self):
        td = TurnDetector()
        td._current_transcript = "Hello"
        td._interim_transcript = "world"
        assert td.current_text == "Hello world"


# =========================================================================
# Escalation detector tests
# =========================================================================


class TestEscalationDetector:
    """Tests for EscalationDetector logic."""

    def test_keyword_detection(self):
        ed = EscalationDetector()
        result = ed.check_user_message("I want to speak to a human")
        assert result.should_escalate is True
        assert result.trigger == "keyword"
        assert result.confidence >= 0.9

    def test_no_escalation_normal_message(self):
        ed = EscalationDetector()
        result = ed.check_user_message("What is my order status?")
        assert result.should_escalate is False

    def test_anger_detection(self):
        ed = EscalationDetector()
        result = ed.check_user_message("This is so frustrating!")
        assert result.should_escalate is True
        assert result.trigger == "sentiment"

    def test_turn_count_escalation(self):
        ed = EscalationDetector(max_turns_before_escalation=3)
        ed.check_user_message("Question 1?")
        ed.check_user_message("Question 2?")
        result = ed.check_user_message("Question 3?")
        assert result.should_escalate is True
        assert result.trigger == "turns"

    def test_repeated_question_detection(self):
        ed = EscalationDetector(repeated_question_threshold=3)
        ed.check_user_message("What is my order status?")
        ed.check_user_message("What is my order status?")
        result = ed.check_user_message("What is my order status?")
        assert result.should_escalate is True
        assert result.trigger == "repeated"

    def test_dtmf_escalation(self):
        ed = EscalationDetector()
        result = ed.check_dtmf("0")
        assert result.should_escalate is True
        assert result.trigger == "dtmf"

    def test_dtmf_no_escalation(self):
        ed = EscalationDetector()
        result = ed.check_dtmf("5")
        assert result.should_escalate is False

    def test_disabled(self):
        ed = EscalationDetector(enabled=False)
        result = ed.check_user_message("speak to a human")
        assert result.should_escalate is False

    def test_reset(self):
        ed = EscalationDetector()
        ed.check_user_message("message 1")
        ed.check_user_message("message 2")
        assert ed.turn_count == 2
        ed.reset()
        assert ed.turn_count == 0

    def test_case_insensitive_keywords(self):
        ed = EscalationDetector()
        result = ed.check_user_message("SPEAK TO A HUMAN please")
        assert result.should_escalate is True

    def test_multiple_anger_patterns(self):
        ed = EscalationDetector()
        # Test "I'm angry" pattern
        ed2 = EscalationDetector()
        result = ed2.check_user_message("I am so angry right now")
        assert result.should_escalate is True

    def test_similar_messages_detection(self):
        assert EscalationDetector._are_similar(
            ["what is my order status", "what is my order status"],
            threshold=0.6,
        )

    def test_dissimilar_messages(self):
        assert not EscalationDetector._are_similar(
            ["hello how are you", "the weather is nice today"],
            threshold=0.6,
        )

    def test_custom_keyword_triggers(self):
        ed = EscalationDetector(keyword_triggers=["custom trigger"])
        result = ed.check_user_message("I need a custom trigger now")
        assert result.should_escalate is True


# =========================================================================
# Pipeline config tests
# =========================================================================


class TestPipelineConfig:
    """Tests for PipelineConfig construction."""

    def test_default_config(self):
        config = PipelineConfig()
        assert config.stt_provider == "deepgram"
        assert config.llm_provider == "openai"
        assert config.tts_provider == "elevenlabs"
        assert config.llm_temperature == 0.7
        assert config.silence_threshold_ms == 700.0
        assert config.interruption_enabled is True

    def test_custom_config(self):
        config = PipelineConfig(
            stt_provider="deepgram",
            stt_config={"api_key": "test"},
            llm_provider="anthropic",
            llm_config={"api_key": "test", "model": "claude-sonnet-4-20250514"},
            tts_provider="elevenlabs",
            tts_config={"api_key": "test", "voice_id": "abc"},
            system_prompt="You are a pizza ordering bot.",
            first_message="Welcome! What pizza would you like?",
            llm_temperature=0.5,
            max_call_duration_seconds=600,
        )
        assert config.llm_provider == "anthropic"
        assert config.system_prompt == "You are a pizza ordering bot."
        assert config.max_call_duration_seconds == 600

    def test_end_call_phrases(self):
        config = PipelineConfig()
        assert "goodbye" in config.end_call_phrases
        assert "hang up" in config.end_call_phrases

    def test_escalation_config(self):
        config = PipelineConfig(
            escalation_enabled=True,
            escalation_config={
                "transfer_number": "+15551234567",
                "max_turns_before_escalation": 10,
            },
        )
        assert config.escalation_enabled is True
        assert config.escalation_config["transfer_number"] == "+15551234567"


# =========================================================================
# Bridge config integration tests
# =========================================================================


class TestBridgeConfigPipeline:
    """Tests for PipelineModeConfig in BridgeConfig."""

    def test_pipeline_mode_disabled_by_default(self):
        config = BridgeConfig()
        assert config.pipeline_mode is False

    def test_pipeline_mode_enabled(self):
        config = BridgeConfig(
            pipeline=PipelineModeConfig(enabled=True)
        )
        assert config.pipeline_mode is True

    def test_pipeline_config_from_dict(self):
        config = BridgeConfig.from_dict({
            "provider": "twilio",
            "pipeline": {
                "enabled": True,
                "stt": {"provider": "deepgram", "config": {"api_key": "test"}},
                "llm": {"provider": "openai", "config": {"api_key": "test"}},
                "tts": {"provider": "elevenlabs", "config": {"api_key": "test"}},
                "system_prompt": "You are a test agent.",
            },
        })
        assert config.pipeline_mode is True
        assert config.pipeline.stt.provider == "deepgram"
        assert config.pipeline.llm.provider == "openai"
        assert config.pipeline.system_prompt == "You are a test agent."

    def test_pipeline_provider_config(self):
        pc = PipelineProviderConfig(
            provider="deepgram",
            config={"api_key": "dg_test", "model": "nova-2"},
        )
        assert pc.provider == "deepgram"
        assert pc.config["api_key"] == "dg_test"

    def test_pipeline_mode_config_defaults(self):
        pmc = PipelineModeConfig()
        assert pmc.enabled is False
        assert pmc.stt.provider == "deepgram"
        assert pmc.llm.provider == "openai"
        assert pmc.tts.provider == "elevenlabs"
        assert pmc.llm_temperature == 0.7
        assert pmc.interruption_enabled is True
        assert pmc.max_call_duration_seconds == 1800
        assert pmc.escalation_enabled is True


# =========================================================================
# Pipeline orchestrator tests (unit, with mocks)
# =========================================================================


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator setup and configuration."""

    def test_create_orchestrator(self):
        config = PipelineConfig(
            system_prompt="Test agent",
            first_message="Hello!",
        )
        orch = PipelineOrchestrator(config)
        assert orch.config == config
        assert not orch.is_running
        assert not orch.is_speaking

    def test_set_callbacks(self):
        config = PipelineConfig()
        orch = PipelineOrchestrator(config)

        audio_cb = AsyncMock()
        tool_cb = AsyncMock()
        esc_cb = AsyncMock()
        end_cb = AsyncMock()
        transcript_cb = AsyncMock()

        orch.set_audio_output_callback(audio_cb)
        orch.set_tool_executor(tool_cb)
        orch.set_escalation_callback(esc_cb)
        orch.set_call_end_callback(end_cb)
        orch.set_transcript_callback(transcript_cb)

        assert orch._audio_output_cb == audio_cb
        assert orch._tool_executor == tool_cb
        assert orch._on_escalation == esc_cb
        assert orch._on_call_end == end_cb
        assert orch._on_transcript == transcript_cb

    def test_sentence_extraction(self):
        sentences = PipelineOrchestrator._extract_sentences(
            "Hello there. How are you? I'm fine!"
        )
        assert len(sentences) == 3
        assert sentences[0] == "Hello there."
        assert sentences[1] == "How are you?"
        assert sentences[2] == "I'm fine!"

    def test_sentence_extraction_incomplete(self):
        sentences = PipelineOrchestrator._extract_sentences(
            "This is complete. This is not"
        )
        assert len(sentences) == 2
        assert sentences[0] == "This is complete."
        assert sentences[1] == "This is not"

    def test_sentence_extraction_empty(self):
        assert PipelineOrchestrator._extract_sentences("") == []

    def test_context_accessible(self):
        config = PipelineConfig(system_prompt="test")
        orch = PipelineOrchestrator(config)
        assert orch.context.message_count == 1  # system prompt

    def test_duration_before_start(self):
        config = PipelineConfig()
        orch = PipelineOrchestrator(config)
        assert orch.duration_seconds == 0.0


# =========================================================================
# Escalation result tests
# =========================================================================


class TestEscalationResult:
    """Tests for EscalationResult data class."""

    def test_default_no_escalation(self):
        result = EscalationResult()
        assert result.should_escalate is False
        assert result.reason == ""
        assert result.confidence == 0.0
        assert result.trigger == ""

    def test_escalation_with_metadata(self):
        result = EscalationResult(
            should_escalate=True,
            reason="Caller frustrated",
            confidence=0.8,
            trigger="sentiment",
            metadata={"pattern": "frustrating"},
        )
        assert result.should_escalate is True
        assert result.metadata["pattern"] == "frustrating"
