"""VoxBridge AI Providers - STT, LLM, and TTS integrations.

Provides a unified interface for plugging in different AI service providers:
- STT (Speech-to-Text): Deepgram, Google, etc.
- LLM (Large Language Model): OpenAI GPT, Anthropic Claude, custom endpoints
- TTS (Text-to-Speech): ElevenLabs, OpenAI TTS, Deepgram Aura

Usage:
    from voxbridge.providers import provider_registry

    stt = provider_registry.create_stt("deepgram", api_key="...")
    llm = provider_registry.create_llm("openai", api_key="...", model="gpt-4o")
    tts = provider_registry.create_tts("elevenlabs", api_key="...", voice_id="...")
"""

from voxbridge.providers.base import BaseSTT, BaseLLM, BaseTTS
from voxbridge.providers.registry import provider_registry

__all__ = [
    "BaseSTT",
    "BaseLLM",
    "BaseTTS",
    "provider_registry",
]
