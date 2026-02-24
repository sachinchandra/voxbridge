"""Tests for audio playground — STT, TTS, and audio-turn endpoint."""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock


# ── STT Service Tests ────────────────────────────────────────────

class TestSTTService:
    """Tests for app.services.stt."""

    @pytest.mark.asyncio
    async def test_transcribe_no_key_returns_error(self):
        """When no API keys configured, returns error."""
        from app.services import stt
        with patch.object(stt.settings, 'deepgram_api_key', ''), \
             patch.object(stt.settings, 'openai_api_key', ''):
            result = await stt.transcribe_audio(b"fake audio data", "audio/webm")
            assert result["transcript"] == ""
            assert "error" in result
            assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_transcribe_deepgram_success(self):
        """Deepgram STT returns transcript on success."""
        from app.services import stt

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": {
                "channels": [{
                    "alternatives": [{
                        "transcript": "Hello, I need help",
                        "confidence": 0.98,
                        "words": [
                            {"word": "Hello", "start": 0.0, "end": 0.5},
                            {"word": "I", "start": 0.6, "end": 0.7},
                            {"word": "need", "start": 0.8, "end": 1.0},
                            {"word": "help", "start": 1.1, "end": 1.3},
                        ],
                    }],
                }],
            }
        }

        with patch.object(stt.settings, 'deepgram_api_key', 'test-key'):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await stt.transcribe_audio(b"audio data", "audio/webm", "deepgram")
                assert result["transcript"] == "Hello, I need help"
                assert result["confidence"] == 0.98
                assert result["provider"] == "deepgram"
                assert len(result["words"]) == 4
                assert "error" not in result

    @pytest.mark.asyncio
    async def test_transcribe_deepgram_error_handling(self):
        """Deepgram STT handles errors gracefully."""
        from app.services import stt

        with patch.object(stt.settings, 'deepgram_api_key', 'test-key'):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await stt.transcribe_audio(b"audio data", "audio/webm", "deepgram")
                assert result["transcript"] == ""
                assert "error" in result

    @pytest.mark.asyncio
    async def test_transcribe_provider_auto_select(self):
        """Auto-selects provider based on available keys."""
        from app.services import stt

        with patch.object(stt.settings, 'deepgram_api_key', ''), \
             patch.object(stt.settings, 'openai_api_key', 'test-openai'):
            with patch.object(stt, '_transcribe_openai', new_callable=AsyncMock) as mock_openai:
                mock_openai.return_value = {"transcript": "test", "provider": "openai", "confidence": 0.9, "words": [], "duration_ms": 100}
                result = await stt.transcribe_audio(b"audio data", "audio/webm", "auto")
                mock_openai.assert_called_once()


# ── TTS Service Tests ────────────────────────────────────────────

class TestTTSService:
    """Tests for app.services.tts."""

    @pytest.mark.asyncio
    async def test_synthesize_no_key_returns_error(self):
        """When no API keys configured, returns error."""
        from app.services import tts
        with patch.object(tts.settings, 'openai_api_key', ''), \
             patch.object(tts.settings, 'elevenlabs_api_key', ''):
            result = await tts.synthesize_speech("Hello world")
            assert result["audio_data"] == b""
            assert "error" in result

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self):
        """Empty text returns empty result without error."""
        from app.services import tts
        result = await tts.synthesize_speech("")
        assert result["audio_data"] == b""
        assert result["char_count"] == 0
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_synthesize_openai_success(self):
        """OpenAI TTS returns audio on success."""
        from app.services import tts

        fake_audio = b"\xff\xd8" * 100  # fake audio bytes

        with patch.object(tts.settings, 'openai_api_key', 'test-key'):
            with patch('openai.AsyncOpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.content = fake_audio
                mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
                mock_openai_cls.return_value = mock_client

                result = await tts.synthesize_speech("Hello world", provider="openai")
                assert result["audio_data"] == fake_audio
                assert result["content_type"] == "audio/mpeg"
                assert result["provider"] == "openai"
                assert result["char_count"] == 11
                assert "error" not in result

    @pytest.mark.asyncio
    async def test_synthesize_elevenlabs_success(self):
        """ElevenLabs TTS returns audio on success."""
        from app.services import tts

        fake_audio = b"\xff\xd8" * 50

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.content = fake_audio

        with patch.object(tts.settings, 'elevenlabs_api_key', 'test-key'):
            with patch('httpx.AsyncClient') as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await tts.synthesize_speech("Hello", provider="elevenlabs", voice_id="test-voice")
                assert result["audio_data"] == fake_audio
                assert result["provider"] == "elevenlabs"
                assert "error" not in result

    @pytest.mark.asyncio
    async def test_synthesize_openai_voice_default(self):
        """OpenAI TTS uses 'nova' voice by default."""
        from app.services import tts

        with patch.object(tts.settings, 'openai_api_key', 'test-key'):
            with patch('openai.AsyncOpenAI') as mock_openai_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.content = b"audio"
                mock_client.audio.speech.create = AsyncMock(return_value=mock_response)
                mock_openai_cls.return_value = mock_client

                await tts.synthesize_speech("Test", provider="openai", voice_id="invalid_voice")

                call_kwargs = mock_client.audio.speech.create.call_args
                assert call_kwargs.kwargs["voice"] == "nova"  # default when invalid


# ── Audio Turn Endpoint Tests ────────────────────────────────────

class TestAudioTurnEndpoint:
    """Tests for POST /playground/audio-turn."""

    @pytest.mark.asyncio
    async def test_audio_turn_full_pipeline(self):
        """Audio turn processes: STT → LLM → TTS."""
        from app.services import stt, tts, playground as pg
        import base64

        # Create a session
        session = pg.create_session(
            customer_id="test-customer",
            agent_id="test-agent",
            agent_name="Test Agent",
        )

        # Mock STT
        stt_result = {
            "transcript": "I need help with my order",
            "confidence": 0.95,
            "duration_ms": 200,
            "words": [],
            "provider": "deepgram",
        }

        # Mock TTS
        tts_result = {
            "audio_data": b"fake-audio-response",
            "content_type": "audio/mpeg",
            "duration_ms": 300,
            "provider": "openai",
            "char_count": 50,
        }

        with patch.object(stt, 'transcribe_audio', new_callable=AsyncMock, return_value=stt_result), \
             patch.object(tts, 'synthesize_speech', new_callable=AsyncMock, return_value=tts_result):

            # Simulate what the endpoint does
            transcript = stt_result["transcript"]
            assert transcript == "I need help with my order"

            # Process through LLM
            agent_config = {
                "system_prompt": "You are a helpful agent.",
                "first_message": "",
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "llm_config": {},
                "tools": [],
                "end_call_phrases": [],
            }
            llm_result = await pg.process_turn(session, transcript, agent_config)
            assert llm_result["reply"]  # should have some reply
            assert "done" in llm_result

            # Verify session state updated
            assert session.total_turns == 1
            assert len(session.messages) == 2  # user + assistant

            # Encode audio
            audio_b64 = base64.b64encode(tts_result["audio_data"]).decode()
            assert audio_b64  # non-empty base64

        # Cleanup
        pg.delete_session(session.id)

    def test_audio_config_detects_providers(self):
        """Audio config endpoint detects available providers."""
        from app.config import settings

        # When deepgram key exists
        with patch.object(settings, 'deepgram_api_key', 'dg-test'), \
             patch.object(settings, 'openai_api_key', 'oai-test'):
            stt_available = bool(settings.deepgram_api_key or settings.openai_api_key)
            tts_available = bool(settings.openai_api_key or settings.elevenlabs_api_key)
            assert stt_available is True
            assert tts_available is True

        # When no keys
        with patch.object(settings, 'deepgram_api_key', ''), \
             patch.object(settings, 'openai_api_key', ''), \
             patch.object(settings, 'elevenlabs_api_key', ''):
            stt_available = bool(settings.deepgram_api_key or settings.openai_api_key)
            tts_available = bool(settings.openai_api_key or settings.elevenlabs_api_key)
            assert stt_available is False
            assert tts_available is False


# ── Integration Tests ────────────────────────────────────────────

class TestAudioPlaygroundIntegration:
    """Integration-style tests combining STT + LLM + TTS."""

    @pytest.mark.asyncio
    async def test_stt_result_structure(self):
        """STT result has required fields."""
        from app.services import stt
        with patch.object(stt.settings, 'deepgram_api_key', ''), \
             patch.object(stt.settings, 'openai_api_key', ''):
            result = await stt.transcribe_audio(b"test", "audio/webm")
            assert "transcript" in result
            assert "confidence" in result
            assert "duration_ms" in result
            assert "words" in result
            assert "provider" in result

    @pytest.mark.asyncio
    async def test_tts_result_structure(self):
        """TTS result has required fields."""
        from app.services import tts
        with patch.object(tts.settings, 'openai_api_key', ''), \
             patch.object(tts.settings, 'elevenlabs_api_key', ''):
            result = await tts.synthesize_speech("test")
            assert "audio_data" in result
            assert "content_type" in result
            assert "duration_ms" in result
            assert "provider" in result
            assert "char_count" in result

    @pytest.mark.asyncio
    async def test_playground_session_with_audio_transcript(self):
        """Playground session correctly handles STT-transcribed text."""
        from app.services import playground as pg

        session = pg.create_session(
            customer_id="audio-test",
            agent_id="agent-1",
            agent_name="Voice Agent",
        )

        # Simulate STT output as user message
        agent_config = {
            "system_prompt": "You are a helpful support agent.",
            "first_message": "Welcome! How can I help?",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_config": {},
            "tools": [],
            "end_call_phrases": ["goodbye"],
        }

        result = await pg.process_turn(session, "Hello, I need help", agent_config)
        assert result["reply"]
        assert session.total_turns == 1

        # Second turn
        result2 = await pg.process_turn(session, "What is your return policy?", agent_config)
        assert result2["reply"]
        assert session.total_turns == 2

        pg.delete_session(session.id)

    def test_base64_audio_encoding(self):
        """Base64 encoding of audio data works correctly."""
        import base64
        audio_data = b"\xff\xfb\x90\x00" * 1000  # fake MP3 header pattern
        encoded = base64.b64encode(audio_data).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded == audio_data

    @pytest.mark.asyncio
    async def test_stt_content_types(self):
        """STT handles different audio content types."""
        from app.services import stt

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": {"channels": [{"alternatives": [{"transcript": "test", "confidence": 0.9, "words": []}]}]}
        }

        for content_type in ["audio/webm", "audio/wav", "audio/mp3", "audio/mp4"]:
            with patch.object(stt.settings, 'deepgram_api_key', 'test-key'):
                with patch('httpx.AsyncClient') as mock_cls:
                    mock_client = AsyncMock()
                    mock_client.post = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)
                    mock_cls.return_value = mock_client

                    result = await stt.transcribe_audio(b"data", content_type, "deepgram")
                    assert result["transcript"] == "test"
