<p align="center">
  <img src="https://img.shields.io/badge/VoxBridge-Universal%20Telephony%20Adapter-blueviolet?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiPjxwYXRoIGQ9Ik0yMiAxNi45MnYzYTIgMiAwIDAgMS0yLjE4IDIgMTkuNzkgMTkuNzkgMCAwIDEtOC42My0zLjA3IDE5LjUgMTkuNSAwIDAgMS02LTYgMTkuNzkgMTkuNzkgMCAwIDEtMy4wNy04LjY3QTIgMiAwIDAgMSA0LjExIDJoM2EyIDIgMCAwIDEgMiAxLjcyYy4xMjcuOTYuMzYxIDEuOTAzLjcgMi44MWEyIDIgMCAwIDEtLjQ1IDIuMTFMOC4wOSA5LjkxYTE2IDE2IDAgMCAwIDYgNmwxLjI3LTEuMjdhMiAyIDAgMCAxIDIuMTEtLjQ1Yy45MDcuMzM5IDEuODUuNTczIDIuODEuN0EyIDIgMCAwIDEgMjIgMTYuOTJ6Ij48L3BhdGg+PC9zdmc+" alt="VoxBridge">
</p>

<h1 align="center">VoxBridge</h1>

<p align="center">
  <strong>Universal telephony adapter SDK for voice bots</strong><br>
  Connect any WebSocket voice bot to any telephony platform with zero custom integration code.
</p>

<p align="center">
  <a href="https://pypi.org/project/voxbridge/"><img src="https://img.shields.io/pypi/v/voxbridge?color=blue" alt="PyPI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-green" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow" alt="License: MIT"></a>
  <a href="#supported-providers"><img src="https://img.shields.io/badge/providers-8-orange" alt="8 Providers"></a>
</p>

---

## The Problem

Building a voice bot? Great. Now connect it to Twilio. And Genesys. And Avaya. And Cisco. And Amazon Connect. And FreeSWITCH. And Asterisk.

Each platform has its own WebSocket protocol, message format, audio codec, handshake sequence, and session lifecycle. That's **7 custom integrations** you need to build and maintain.

## The Solution

**VoxBridge** is a Python SDK that sits between your voice bot and any telephony platform. You build your bot once with a standard WebSocket interface, and VoxBridge handles all the protocol translation, codec conversion, and session management.

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Telephony  │  ←WS→   │   VoxBridge  │  ←WS→   │  Your Voice  │
│   Platform   │         │    Bridge    │         │     Bot      │
│              │         │              │         │              │
│  Twilio      │         │ • Serializer │         │ • STT        │
│  Genesys     │  mulaw  │ • Codec Conv │  pcm16  │ • LLM        │
│  Avaya       │  8kHz   │ • Resample   │  16kHz  │ • TTS        │
│  Cisco       │         │ • Sessions   │         │              │
│  AWS Connect │         │              │         │              │
│  FreeSWITCH  │         │              │         │              │
│  Asterisk    │         │              │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
```

## Quick Start

### Install

```bash
pip install voxbridge
```

### Option 1: Zero Code (Config-Driven)

```bash
# Generate a starter config
voxbridge init

# Edit bridge.yaml — set your provider and bot URL
# Then run:
voxbridge run --config bridge.yaml
```

### Option 2: Three Lines of Python

```python
from voxbridge import VoxBridge

bridge = VoxBridge({
    "provider": "twilio",
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
})
bridge.run()
# Twilio connects to :8765, audio flows to your bot on :9000
```

### Option 3: Full Programmatic Control

```python
from voxbridge import VoxBridge, BridgeConfig

bridge = VoxBridge(BridgeConfig.from_dict({
    "provider": "genesys",
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
}))

@bridge.on_call_start
async def handle_call(session):
    print(f"Call from {session.from_number}")

@bridge.on_audio
async def process_audio(session, frame):
    # Custom audio processing before forwarding to bot
    if session.is_on_hold:
        return None  # mute during hold
    return frame

@bridge.on_dtmf
async def handle_dtmf(session, digit):
    if digit == "0":
        print("Transfer requested")

@bridge.on_call_end
async def handle_end(session, event):
    print(f"Call ended after {session.duration_ms}ms")

bridge.run()
```

## Supported Providers

| Provider | Protocol | Codec | Sample Rate | Status |
|----------|----------|-------|-------------|--------|
| **Twilio** | Media Streams WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Genesys Cloud** | AudioHook WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Avaya** | OCSAPI WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Cisco** | WebEx CC WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Amazon Connect** | Streaming WebSocket | PCM16 | 8 kHz | ✅ Ready |
| **FreeSWITCH** | mod_ws WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Asterisk** | ARI WebSocket | μ-law | 8 kHz | ✅ Ready |
| **Generic** | Raw WebSocket | PCM16 | 16 kHz | ✅ Ready |

### Adding a Custom Provider

Adding a new telephony provider requires **just one file** — implement the `BaseSerializer` interface:

```python
from voxbridge.serializers.base import BaseSerializer
from voxbridge.core.events import AnyEvent, Codec

class MyProviderSerializer(BaseSerializer):
    @property
    def name(self) -> str:
        return "my_provider"

    @property
    def audio_codec(self) -> Codec:
        return Codec.MULAW

    @property
    def sample_rate(self) -> int:
        return 8000

    async def deserialize(self, raw: bytes | str | dict) -> list[AnyEvent]:
        # Parse provider messages into VoxBridge events
        ...

    async def serialize(self, event: AnyEvent) -> bytes | str | dict | None:
        # Convert VoxBridge events to provider wire format
        ...

    def handshake_response(self, connect_msg: dict) -> dict | None:
        # Respond to provider's initial handshake
        ...

# Register it:
from voxbridge import serializer_registry
serializer_registry.register("my_provider", MyProviderSerializer)
```

## Architecture

```
voxbridge/
├── core/events.py          # Unified event model (AudioFrame, CallStarted, DTMF, etc.)
├── audio/
│   ├── codecs.py           # G.711 μ-law/A-law, PCM16, Opus codec engine
│   └── resampler.py        # Sample rate conversion (8kHz ↔ 16kHz ↔ 48kHz)
├── serializers/
│   ├── base.py             # BaseSerializer interface
│   ├── registry.py         # Provider lookup registry
│   ├── twilio.py           # Twilio Media Streams
│   ├── genesys.py          # Genesys AudioHook
│   ├── avaya.py            # Avaya OCSAPI
│   ├── cisco.py            # Cisco WebEx CC
│   ├── amazon_connect.py   # Amazon Connect
│   ├── freeswitch.py       # FreeSWITCH mod_ws
│   ├── asterisk.py         # Asterisk ARI
│   └── generic_ws.py       # Generic WebSocket
├── transports/
│   ├── websocket.py        # WebSocket client + server
│   └── sip.py              # SIP transport (optional, requires pjsua2)
├── bridge.py               # Central orchestrator
├── config.py               # YAML/dict/programmatic configuration
├── session.py              # Per-call session management
├── server.py               # FastAPI server (optional)
└── cli.py                  # CLI: voxbridge run | providers | init
```

### Key Design Decisions

- **Async-first**: Built on `asyncio`. Each call gets its own pair of bidirectional tasks.
- **PCM16 as lingua franca**: All codec conversion routes through PCM16, so adding a new codec needs just one encoder + one decoder (not N² converters).
- **Serializers are pure translators**: No I/O in serializers — they only convert between wire formats and events. Transports handle all networking.
- **Zero required native dependencies**: Core codecs (μ-law, A-law) are pure Python. Opus and SIP are optional extras.

## Configuration

### YAML Config

```yaml
provider:
  type: twilio
  listen_host: 0.0.0.0
  listen_port: 8765
  listen_path: /media-stream

bot:
  url: ws://localhost:9000/ws
  codec: pcm16
  sample_rate: 16000

audio:
  input_codec: mulaw
  output_codec: mulaw
  sample_rate: 8000

logging:
  level: INFO
```

### Shorthand Dict

```python
# These two are equivalent:
VoxBridge({"provider": "twilio", "listen_port": 8765, "bot_url": "ws://localhost:9000/ws"})
VoxBridge(BridgeConfig(
    provider=ProviderConfig(type="twilio", listen_port=8765),
    bot=BotConfig(url="ws://localhost:9000/ws"),
))
```

## CLI

```bash
# List all supported providers
voxbridge providers

# Generate a starter config file
voxbridge init --output bridge.yaml

# Run the bridge
voxbridge run --config bridge.yaml
```

## Deployment

### Docker

```bash
docker build -t voxbridge .
docker run -p 8765:8765 -v $(pwd)/bridge.yaml:/app/bridge.yaml voxbridge
```

### Fly.io

```bash
fly launch
fly deploy
```

See the [deployment guide](examples/) for detailed instructions.

## Optional Extras

```bash
# Opus codec support
pip install voxbridge[opus]

# FastAPI server with health/status endpoints
pip install voxbridge[server]

# SIP transport (requires PJSIP)
pip install voxbridge[sip]

# Everything
pip install voxbridge[all]
```

## Development

```bash
git clone https://github.com/sachinchandra/voxbridge.git
cd voxbridge
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built for voice bot developers who are tired of writing custom telephony integrations.
</p>
