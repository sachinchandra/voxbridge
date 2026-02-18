"""VoxBridge - Universal telephony adapter SDK for voice bots.

Connect any WebSocket voice bot to any telephony platform:
Twilio, Genesys, Avaya, Cisco, Amazon Connect, FreeSWITCH, Asterisk.

Quick start (config-driven):
    $ pip install voxbridge
    $ voxbridge init          # generates bridge.yaml
    $ voxbridge run --config bridge.yaml

Quick start (programmatic):
    from voxbridge import VoxBridge

    bridge = VoxBridge({
        "provider": "twilio",
        "listen_port": 8765,
        "bot_url": "ws://localhost:9000/ws",
    })

    @bridge.on_call_start
    async def handle_call(session):
        print(f"Call from {session.from_number}")

    bridge.run()
"""

__version__ = "0.2.0"

# Core
from voxbridge.bridge import VoxBridge
from voxbridge.config import BridgeConfig, PipelineModeConfig, SaaSConfig, load_config
from voxbridge.platform import PlatformClient
from voxbridge.session import BargeInDetector, CallSession, SessionStore, compute_audio_energy

# Events
from voxbridge.core.events import (
    AudioFrame,
    BargeIn,
    CallEnded,
    CallStarted,
    ClearAudio,
    Codec,
    CustomEvent,
    DTMFReceived,
    ErrorEvent,
    Event,
    EventType,
    HoldEnded,
    HoldStarted,
    Mark,
    TransferRequested,
)

# Audio
from voxbridge.audio.codecs import CodecRegistry, codec_registry
from voxbridge.audio.resampler import Resampler

# Serializers
from voxbridge.serializers.base import BaseSerializer
from voxbridge.serializers.registry import serializer_registry

# Transports
from voxbridge.transports.base import BaseTransport
from voxbridge.transports.websocket import (
    WebSocketClientTransport,
    WebSocketServer,
    WebSocketServerTransport,
)

# AI Pipeline
from voxbridge.pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from voxbridge.pipeline.context import ConversationContext
from voxbridge.pipeline.turn_detector import TurnDetector
from voxbridge.pipeline.escalation import EscalationDetector, EscalationResult

# AI Providers
from voxbridge.providers.base import BaseLLM, BaseSTT, BaseTTS
from voxbridge.providers.registry import provider_registry

__all__ = [
    # Core
    "VoxBridge",
    "BridgeConfig",
    "PipelineModeConfig",
    "SaaSConfig",
    "PlatformClient",
    "load_config",
    "CallSession",
    "SessionStore",
    "BargeInDetector",
    "compute_audio_energy",
    # Events
    "Event",
    "EventType",
    "AudioFrame",
    "BargeIn",
    "CallStarted",
    "CallEnded",
    "ClearAudio",
    "DTMFReceived",
    "HoldStarted",
    "HoldEnded",
    "Mark",
    "TransferRequested",
    "CustomEvent",
    "ErrorEvent",
    "Codec",
    # Audio
    "CodecRegistry",
    "codec_registry",
    "Resampler",
    # Serializers
    "BaseSerializer",
    "serializer_registry",
    # Transports
    "BaseTransport",
    "WebSocketClientTransport",
    "WebSocketServerTransport",
    "WebSocketServer",
    # AI Pipeline
    "PipelineOrchestrator",
    "PipelineConfig",
    "ConversationContext",
    "TurnDetector",
    "EscalationDetector",
    "EscalationResult",
    # AI Providers
    "BaseSTT",
    "BaseLLM",
    "BaseTTS",
    "provider_registry",
]
