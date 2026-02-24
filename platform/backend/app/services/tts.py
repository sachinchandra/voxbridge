"""Text-to-Speech service — convert text to audio.

Supports OpenAI TTS and ElevenLabs with fallback handling.
Used by the playground audio endpoint and future telephony pipeline.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings


async def synthesize_speech(
    text: str,
    provider: str = "openai",
    voice_id: str = "",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert text to audio bytes.

    Args:
        text: Text to synthesize.
        provider: TTS provider ("openai", "elevenlabs").
        voice_id: Voice identifier.
        config: Provider-specific configuration.

    Returns:
        {audio_data, content_type, duration_ms, provider, char_count}
    """
    start = time.time()

    if not text.strip():
        return _empty_text_result(start)

    if provider == "elevenlabs":
        return await _synthesize_elevenlabs(text, voice_id, config or {}, start)
    elif provider == "openai":
        return await _synthesize_openai(text, voice_id, config or {}, start)
    else:
        # Auto-select: prefer OpenAI (simpler), fallback to ElevenLabs
        if settings.openai_api_key:
            return await _synthesize_openai(text, voice_id, config or {}, start)
        elif settings.elevenlabs_api_key:
            return await _synthesize_elevenlabs(text, voice_id, config or {}, start)
        else:
            return _no_key_error(start)


async def _synthesize_openai(
    text: str,
    voice_id: str,
    config: dict[str, Any],
    start: float,
) -> dict[str, Any]:
    """Use OpenAI TTS API."""
    api_key = settings.openai_api_key
    if not api_key:
        return _no_key_error(start, "OpenAI")

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)

        # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
        voice = voice_id if voice_id in ("alloy", "echo", "fable", "onyx", "nova", "shimmer") else "nova"
        model = config.get("model", "tts-1")  # tts-1 (fast) or tts-1-hd (quality)

        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
            speed=config.get("speed", 1.0),
        )

        audio_data = response.content
        latency_ms = int((time.time() - start) * 1000)

        logger.info(f"TTS OpenAI: {len(text)} chars → {len(audio_data)} bytes, voice={voice}, latency={latency_ms}ms")

        return {
            "audio_data": audio_data,
            "content_type": "audio/mpeg",
            "duration_ms": latency_ms,
            "provider": "openai",
            "char_count": len(text),
        }

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"TTS OpenAI error: {e}")
        return {
            "audio_data": b"",
            "content_type": "audio/mpeg",
            "duration_ms": latency_ms,
            "provider": "openai",
            "char_count": len(text),
            "error": str(e),
        }


async def _synthesize_elevenlabs(
    text: str,
    voice_id: str,
    config: dict[str, Any],
    start: float,
) -> dict[str, Any]:
    """Use ElevenLabs TTS API."""
    api_key = settings.elevenlabs_api_key
    if not api_key:
        return _no_key_error(start, "ElevenLabs")

    # Default voice: Rachel (21m00Tcm4TlvDq8ikWAM)
    vid = voice_id or config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": config.get("model_id", "eleven_monolingual_v1"),
        "voice_settings": {
            "stability": config.get("stability", 0.5),
            "similarity_boost": config.get("similarity_boost", 0.75),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            audio_data = resp.content

        latency_ms = int((time.time() - start) * 1000)

        logger.info(f"TTS ElevenLabs: {len(text)} chars → {len(audio_data)} bytes, voice={vid[:8]}..., latency={latency_ms}ms")

        return {
            "audio_data": audio_data,
            "content_type": "audio/mpeg",
            "duration_ms": latency_ms,
            "provider": "elevenlabs",
            "char_count": len(text),
        }

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"TTS ElevenLabs error: {e}")
        return {
            "audio_data": b"",
            "content_type": "audio/mpeg",
            "duration_ms": latency_ms,
            "provider": "elevenlabs",
            "char_count": len(text),
            "error": str(e),
        }


def _empty_text_result(start: float) -> dict[str, Any]:
    return {
        "audio_data": b"",
        "content_type": "audio/mpeg",
        "duration_ms": int((time.time() - start) * 1000),
        "provider": "none",
        "char_count": 0,
    }


def _no_key_error(start: float, provider: str = "TTS") -> dict[str, Any]:
    return {
        "audio_data": b"",
        "content_type": "audio/mpeg",
        "duration_ms": int((time.time() - start) * 1000),
        "provider": "none",
        "char_count": 0,
        "error": f"{provider} API key not configured. Set the API key in your environment.",
    }
