"""Configuration system for VoxBridge.

Supports loading from YAML files, dicts, or programmatic construction
via Pydantic models. The config drives the bridge's provider selection,
audio pipeline, and connection settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for the telephony provider side."""

    type: str = "twilio"
    listen_host: str = "0.0.0.0"
    listen_port: int = 8765
    listen_path: str = "/media-stream"
    # Provider-specific extra settings
    extra: dict[str, Any] = Field(default_factory=dict)


class BotConfig(BaseModel):
    """Configuration for the voice bot side."""

    url: str = "ws://localhost:9000/ws"
    codec: str = "pcm16"
    sample_rate: int = 16000


class AudioConfig(BaseModel):
    """Audio pipeline configuration."""

    input_codec: str = "mulaw"
    output_codec: str = "mulaw"
    sample_rate: int = 8000


class SaaSConfig(BaseModel):
    """SaaS platform configuration (optional)."""

    api_key: str = ""
    platform_url: str = "https://api.voxbridge.io"
    validate_on_start: bool = True
    report_usage: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"


class PipelineProviderConfig(BaseModel):
    """Configuration for an AI pipeline provider (STT, LLM, or TTS)."""

    provider: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineModeConfig(BaseModel):
    """Configuration for the built-in AI pipeline mode.

    When pipeline_mode is enabled, the bridge uses the internal
    STT→LLM→TTS pipeline instead of connecting to an external bot WebSocket.
    """

    enabled: bool = False
    stt: PipelineProviderConfig = Field(
        default_factory=lambda: PipelineProviderConfig(provider="deepgram")
    )
    llm: PipelineProviderConfig = Field(
        default_factory=lambda: PipelineProviderConfig(provider="openai")
    )
    tts: PipelineProviderConfig = Field(
        default_factory=lambda: PipelineProviderConfig(provider="elevenlabs")
    )

    # Agent configuration
    system_prompt: str = "You are a helpful AI assistant on a phone call. Be concise and conversational."
    first_message: str = ""
    tools: list[dict[str, Any]] = Field(default_factory=list)
    end_call_phrases: list[str] = Field(default_factory=lambda: [
        "goodbye", "bye bye", "end the call", "hang up",
    ])

    # Pipeline settings
    llm_temperature: float = 0.7
    llm_max_tokens: int = 512
    silence_threshold_ms: float = 700.0
    interruption_enabled: bool = True
    max_call_duration_seconds: int = 1800

    # Escalation
    escalation_enabled: bool = True
    escalation_config: dict[str, Any] = Field(default_factory=dict)


class BridgeConfig(BaseModel):
    """Top-level VoxBridge configuration.

    Can be constructed programmatically, from a dict, or loaded from YAML.

    Supports two modes:
    1. Bot mode (default): Connects to an external WebSocket voice bot.
    2. Pipeline mode: Uses the built-in STT→LLM→TTS AI pipeline.

    Examples:
        # Programmatic (bot mode)
        config = BridgeConfig(
            provider=ProviderConfig(type="twilio"),
            bot=BotConfig(url="ws://localhost:9000/ws"),
        )

        # Programmatic (pipeline mode)
        config = BridgeConfig(
            provider=ProviderConfig(type="twilio"),
            pipeline=PipelineModeConfig(
                enabled=True,
                stt=PipelineProviderConfig(provider="deepgram", config={"api_key": "..."}),
                llm=PipelineProviderConfig(provider="openai", config={"api_key": "..."}),
                tts=PipelineProviderConfig(provider="elevenlabs", config={"api_key": "..."}),
                system_prompt="You are a customer service agent...",
            ),
        )

        # From YAML
        config = BridgeConfig.from_yaml("bridge.yaml")

        # Shorthand
        config = BridgeConfig.from_dict({
            "provider": "twilio",
            "listen_port": 8765,
            "bot_url": "ws://localhost:9000/ws",
        })
    """

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    bot: BotConfig = Field(default_factory=BotConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    saas: SaaSConfig = Field(default_factory=SaaSConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    pipeline: PipelineModeConfig = Field(default_factory=PipelineModeConfig)

    @property
    def pipeline_mode(self) -> bool:
        """Whether the bridge is using the built-in AI pipeline."""
        return self.pipeline.enabled

    @classmethod
    def from_yaml(cls, path: str | Path) -> BridgeConfig:
        """Load configuration from a YAML file."""
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return cls._from_raw(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BridgeConfig:
        """Load configuration from a dictionary.

        Supports both the full nested format and a flat shorthand format:

        Full format:
            {"provider": {"type": "twilio", "listen_port": 8765}, "bot": {"url": "..."}}

        Shorthand format:
            {"provider": "twilio", "listen_port": 8765, "bot_url": "ws://..."}
        """
        return cls._from_raw(data)

    @classmethod
    def _from_raw(cls, data: dict[str, Any]) -> BridgeConfig:
        """Normalize and construct config from a raw dict."""
        # Handle shorthand format
        if isinstance(data.get("provider"), str):
            provider_type = data.pop("provider")
            data["provider"] = {"type": provider_type}

        # Map flat keys to nested structure
        flat_mappings = {
            "listen_host": ("provider", "listen_host"),
            "listen_port": ("provider", "listen_port"),
            "listen_path": ("provider", "listen_path"),
            "bot_url": ("bot", "url"),
            "bot_codec": ("bot", "codec"),
            "bot_sample_rate": ("bot", "sample_rate"),
            "api_key": ("saas", "api_key"),
            "platform_url": ("saas", "platform_url"),
            "log_level": ("logging", "level"),
        }

        for flat_key, (section, nested_key) in flat_mappings.items():
            if flat_key in data:
                if section not in data:
                    data[section] = {}
                data[section][nested_key] = data.pop(flat_key)

        return cls(**data)


def load_config(source: str | Path | dict[str, Any] | BridgeConfig) -> BridgeConfig:
    """Load a BridgeConfig from any supported source.

    Args:
        source: A YAML file path (str/Path), a dict, or an existing BridgeConfig.

    Returns:
        A BridgeConfig instance.
    """
    if isinstance(source, BridgeConfig):
        return source
    if isinstance(source, dict):
        return BridgeConfig.from_dict(source)
    if isinstance(source, (str, Path)):
        path = Path(source)
        if path.exists() and path.suffix in (".yaml", ".yml"):
            return BridgeConfig.from_yaml(path)
        # Maybe it's a provider name shorthand?
        return BridgeConfig.from_dict({"provider": str(source)})
    raise TypeError(f"Cannot load config from {type(source)}")


# Default YAML template for `voxbridge init`
DEFAULT_CONFIG_YAML = """\
# VoxBridge Configuration
# See: https://github.com/voxbridge/voxbridge

provider:
  type: twilio          # twilio | genesys | avaya | cisco | amazon_connect | freeswitch | asterisk | generic
  listen_host: 0.0.0.0
  listen_port: 8765
  listen_path: /media-stream

bot:
  url: ws://localhost:9000/ws
  codec: pcm16          # pcm16 | mulaw | alaw | opus
  sample_rate: 16000    # 8000 | 16000 | 48000

audio:
  input_codec: mulaw    # codec from provider
  output_codec: mulaw   # codec to provider
  sample_rate: 8000     # provider-side sample rate

logging:
  level: INFO

# AI Pipeline Mode (alternative to external bot WebSocket)
# When enabled, uses built-in STT→LLM→TTS pipeline instead of bot.url
# pipeline:
#   enabled: true
#   stt:
#     provider: deepgram
#     config:
#       api_key: ${DEEPGRAM_API_KEY}
#   llm:
#     provider: openai         # openai | anthropic
#     config:
#       api_key: ${OPENAI_API_KEY}
#       model: gpt-4o-mini
#   tts:
#     provider: elevenlabs
#     config:
#       api_key: ${ELEVENLABS_API_KEY}
#       voice_id: 21m00Tcm4TlvDq8ikWAM
#   system_prompt: "You are a helpful AI assistant..."
#   first_message: "Hello! How can I help you today?"
"""
