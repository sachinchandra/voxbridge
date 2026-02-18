"""Provider registry — factory for creating STT, LLM, and TTS instances.

Supports registration of provider classes by name, with lazy imports to
avoid pulling in all provider dependencies unless they're actually used.
"""

from __future__ import annotations

from typing import Any, Type

from loguru import logger

from voxbridge.providers.base import BaseLLM, BaseSTT, BaseTTS


class ProviderRegistry:
    """Factory for creating AI provider instances.

    Providers are registered by name and created on demand. Built-in
    providers are registered automatically; custom providers can be
    added via register_stt/register_llm/register_tts.

    Example:
        stt = provider_registry.create_stt("deepgram", api_key="...")
        llm = provider_registry.create_llm("openai", api_key="...", model="gpt-4o")
        tts = provider_registry.create_tts("elevenlabs", api_key="...", voice_id="...")
    """

    def __init__(self) -> None:
        self._stt_providers: dict[str, Type[BaseSTT] | str] = {}
        self._llm_providers: dict[str, Type[BaseLLM] | str] = {}
        self._tts_providers: dict[str, Type[BaseTTS] | str] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in providers with lazy import paths."""
        # STT providers
        self._stt_providers["deepgram"] = "voxbridge.providers.stt.deepgram:DeepgramSTT"

        # LLM providers
        self._llm_providers["openai"] = "voxbridge.providers.llm.openai:OpenAILLM"
        self._llm_providers["anthropic"] = "voxbridge.providers.llm.anthropic:AnthropicLLM"

        # TTS providers
        self._tts_providers["elevenlabs"] = "voxbridge.providers.tts.elevenlabs:ElevenLabsTTS"

    def _resolve_class(self, ref: Type | str) -> Type:
        """Resolve a class reference, importing lazily if needed."""
        if isinstance(ref, str):
            module_path, class_name = ref.rsplit(":", 1)
            import importlib
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        return ref

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_stt(self, name: str, cls: Type[BaseSTT]) -> None:
        """Register a custom STT provider class."""
        self._stt_providers[name] = cls
        logger.debug(f"Registered STT provider: {name}")

    def register_llm(self, name: str, cls: Type[BaseLLM]) -> None:
        """Register a custom LLM provider class."""
        self._llm_providers[name] = cls
        logger.debug(f"Registered LLM provider: {name}")

    def register_tts(self, name: str, cls: Type[BaseTTS]) -> None:
        """Register a custom TTS provider class."""
        self._tts_providers[name] = cls
        logger.debug(f"Registered TTS provider: {name}")

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    def create_stt(self, name: str, **kwargs: Any) -> BaseSTT:
        """Create an STT provider instance.

        Args:
            name: Provider name (e.g., "deepgram").
            **kwargs: Provider-specific configuration (api_key, model, etc.).

        Returns:
            A configured BaseSTT instance.

        Raises:
            ValueError: If the provider name is not registered.
        """
        if name not in self._stt_providers:
            available = ", ".join(self._stt_providers.keys())
            raise ValueError(
                f"Unknown STT provider '{name}'. Available: {available}"
            )
        cls = self._resolve_class(self._stt_providers[name])
        logger.info(f"Creating STT provider: {name}")
        return cls(**kwargs)

    def create_llm(self, name: str, **kwargs: Any) -> BaseLLM:
        """Create an LLM provider instance.

        Args:
            name: Provider name (e.g., "openai", "anthropic").
            **kwargs: Provider-specific configuration (api_key, model, etc.).

        Returns:
            A configured BaseLLM instance.

        Raises:
            ValueError: If the provider name is not registered.
        """
        if name not in self._llm_providers:
            available = ", ".join(self._llm_providers.keys())
            raise ValueError(
                f"Unknown LLM provider '{name}'. Available: {available}"
            )
        cls = self._resolve_class(self._llm_providers[name])
        logger.info(f"Creating LLM provider: {name}")
        return cls(**kwargs)

    def create_tts(self, name: str, **kwargs: Any) -> BaseTTS:
        """Create a TTS provider instance.

        Args:
            name: Provider name (e.g., "elevenlabs").
            **kwargs: Provider-specific configuration (api_key, voice_id, etc.).

        Returns:
            A configured BaseTTS instance.

        Raises:
            ValueError: If the provider name is not registered.
        """
        if name not in self._tts_providers:
            available = ", ".join(self._tts_providers.keys())
            raise ValueError(
                f"Unknown TTS provider '{name}'. Available: {available}"
            )
        cls = self._resolve_class(self._tts_providers[name])
        logger.info(f"Creating TTS provider: {name}")
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def available_stt(self) -> list[str]:
        """List available STT provider names."""
        return list(self._stt_providers.keys())

    @property
    def available_llm(self) -> list[str]:
        """List available LLM provider names."""
        return list(self._llm_providers.keys())

    @property
    def available_tts(self) -> list[str]:
        """List available TTS provider names."""
        return list(self._tts_providers.keys())


# Global singleton
provider_registry = ProviderRegistry()
