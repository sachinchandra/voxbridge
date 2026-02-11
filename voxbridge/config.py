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


class BridgeConfig(BaseModel):
    """Top-level VoxBridge configuration.

    Can be constructed programmatically, from a dict, or loaded from YAML.

    Examples:
        # Programmatic
        config = BridgeConfig(
            provider=ProviderConfig(type="twilio"),
            bot=BotConfig(url="ws://localhost:9000/ws"),
        )

        # From dict
        config = BridgeConfig(**config_dict)

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
"""
