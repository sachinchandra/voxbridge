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

__version__ = "0.1.0"

# Core
from voxbridge.bridge import VoxBridge
from voxbridge.config import BridgeConfig, SaaSConfig, load_config
from voxbridge.platform import PlatformClient
from voxbridge.session import CallSession, SessionStore

# Events
from voxbridge.core.events import (
    AudioFrame,
    CallEnded,
    CallStarted,
    Codec,
    CustomEvent,
    DTMFReceived,
    ErrorEvent,
    Event,
    EventType,
    HoldEnded,
    HoldStarted,
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

__all__ = [
    # Core
    "VoxBridge",
    "BridgeConfig",
    "SaaSConfig",
    "PlatformClient",
    "load_config",
    "CallSession",
    "SessionStore",
    # Events
    "Event",
    "EventType",
    "AudioFrame",
    "CallStarted",
    "CallEnded",
    "DTMFReceived",
    "HoldStarted",
    "HoldEnded",
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
]
