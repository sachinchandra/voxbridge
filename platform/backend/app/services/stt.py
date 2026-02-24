"""Speech-to-Text service — convert audio to text.

Supports Deepgram (pre-recorded API) with fallback simulation.
Used by the playground audio endpoint and future telephony pipeline.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger

from app.config import settings


async def transcribe_audio(
    audio_data: bytes,
    content_type: str = "audio/webm",
    provider: str = "deepgram",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Transcribe audio bytes to text.

    Args:
        audio_data: Raw audio bytes (webm, wav, mp3, etc.)
        content_type: MIME type of the audio.
        provider: STT provider ("deepgram", "openai").
        config: Provider-specific configuration.

    Returns:
        {transcript, confidence, duration_ms, words, provider}
    """
    start = time.time()

    if provider == "deepgram":
        return await _transcribe_deepgram(audio_data, content_type, config or {}, start)
    elif provider == "openai":
        return await _transcribe_openai(audio_data, content_type, config or {}, start)
    else:
        # Fallback to deepgram if available, else openai
        if settings.deepgram_api_key:
            return await _transcribe_deepgram(audio_data, content_type, config or {}, start)
        elif settings.openai_api_key:
            return await _transcribe_openai(audio_data, content_type, config or {}, start)
        else:
            return _no_key_error(start)


async def _transcribe_deepgram(
    audio_data: bytes,
    content_type: str,
    config: dict[str, Any],
    start: float,
) -> dict[str, Any]:
    """Use Deepgram pre-recorded (batch) API."""
    api_key = settings.deepgram_api_key
    if not api_key:
        return _no_key_error(start, "Deepgram")

    url = "https://api.deepgram.com/v1/listen"
    params = {
        "model": config.get("model", "nova-2"),
        "language": config.get("language", "en"),
        "smart_format": "true",
        "punctuate": "true",
    }

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params=params, headers=headers, content=audio_data)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.time() - start) * 1000)

        # Parse Deepgram response
        alt = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        confidence = alt.get("confidence", 0.0)
        words = alt.get("words", [])

        logger.info(f"STT Deepgram: '{transcript[:50]}...' conf={confidence:.2f} latency={latency_ms}ms")

        return {
            "transcript": transcript,
            "confidence": confidence,
            "duration_ms": latency_ms,
            "words": [{"word": w["word"], "start": w.get("start", 0), "end": w.get("end", 0)} for w in words],
            "provider": "deepgram",
        }

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"STT Deepgram error: {e}")
        return {
            "transcript": "",
            "confidence": 0.0,
            "duration_ms": latency_ms,
            "words": [],
            "provider": "deepgram",
            "error": str(e),
        }


async def _transcribe_openai(
    audio_data: bytes,
    content_type: str,
    config: dict[str, Any],
    start: float,
) -> dict[str, Any]:
    """Use OpenAI Whisper API."""
    api_key = settings.openai_api_key
    if not api_key:
        return _no_key_error(start, "OpenAI")

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)

        # Whisper needs a file-like object with a name
        import io
        ext = "webm" if "webm" in content_type else "wav"
        audio_file = io.BytesIO(audio_data)
        audio_file.name = f"audio.{ext}"

        response = await client.audio.transcriptions.create(
            model=config.get("model", "whisper-1"),
            file=audio_file,
            language=config.get("language", "en"),
        )

        latency_ms = int((time.time() - start) * 1000)
        transcript = response.text

        logger.info(f"STT OpenAI: '{transcript[:50]}...' latency={latency_ms}ms")

        return {
            "transcript": transcript,
            "confidence": 0.95,  # Whisper doesn't return confidence
            "duration_ms": latency_ms,
            "words": [],
            "provider": "openai",
        }

    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"STT OpenAI error: {e}")
        return {
            "transcript": "",
            "confidence": 0.0,
            "duration_ms": latency_ms,
            "words": [],
            "provider": "openai",
            "error": str(e),
        }


def _no_key_error(start: float, provider: str = "STT") -> dict[str, Any]:
    return {
        "transcript": "",
        "confidence": 0.0,
        "duration_ms": int((time.time() - start) * 1000),
        "words": [],
        "provider": "none",
        "error": f"{provider} API key not configured. Set the API key in your environment.",
    }
