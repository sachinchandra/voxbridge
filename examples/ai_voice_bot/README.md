# AI Voice Bot with VoxBridge

A complete voice bot using **Deepgram** (STT) + **OpenAI** (LLM) + **ElevenLabs** (TTS), connected to phone calls via **Twilio** through **VoxBridge**.

## Architecture

```
Phone Call → Twilio → VoxBridge Bridge → AI Voice Bot
                                           ├── Deepgram (STT)
                                           ├── OpenAI GPT (LLM)
                                           └── ElevenLabs (TTS)
```

## Prerequisites

1. **API Keys** (get these first):
   - [Deepgram](https://console.deepgram.com/) — Free tier: 12,000 minutes
   - [OpenAI](https://platform.openai.com/api-keys) — Pay-as-you-go
   - [ElevenLabs](https://elevenlabs.io/) — Free tier: 10,000 chars/month
   - [Twilio](https://console.twilio.com/) — Free trial with $15 credit

2. **Tools**:
   - Python 3.10+
   - [ngrok](https://ngrok.com/download) — Free account

## Quick Start (5 minutes)

### Step 1: Install Dependencies

```bash
cd examples/ai_voice_bot

pip install voxbridge-io websockets deepgram-sdk openai elevenlabs aiohttp flask
```

### Step 2: Set API Keys

```bash
export DEEPGRAM_API_KEY="your-deepgram-key"
export OPENAI_API_KEY="your-openai-key"
export ELEVENLABS_API_KEY="your-elevenlabs-key"
```

### Step 3: Start the AI Voice Bot (Terminal 1)

```bash
python voice_bot.py
```

You should see:
```
AI Voice Bot starting on ws://0.0.0.0:9000/ws
  STT:  Deepgram (streaming)
  LLM:  OpenAI (gpt-4o-mini)
  TTS:  ElevenLabs (voice: 21m00Tcm4TlvDq8ikWAM)

Waiting for VoxBridge to connect...
```

### Step 4: Start VoxBridge Bridge (Terminal 2)

```bash
python bridge.py
```

You should see:
```
VoxBridge starting...
  Provider: Twilio (ws://0.0.0.0:8765)
  Bot:      ws://localhost:9000/ws

Waiting for Twilio Media Streams connection...
```

### Step 5: Start ngrok Tunnels (Terminal 3)

You need TWO tunnels — one for the TwiML webhook (HTTP) and one for the VoxBridge WebSocket:

```bash
# Tunnel for VoxBridge WebSocket (port 8765)
ngrok http 8765
```

Copy the **Forwarding** URL (e.g., `https://abc123.ngrok-free.app`).

### Step 6: Start TwiML Server (Terminal 4)

Edit `twiml_server.py` and replace `VOXBRIDGE_WS_URL`:

```python
VOXBRIDGE_WS_URL = "wss://abc123.ngrok-free.app"  # your ngrok URL
```

Then run:

```bash
python twiml_server.py
```

### Step 7: Start ngrok for TwiML (Terminal 5)

```bash
ngrok http 5000
```

Copy this URL too (e.g., `https://def456.ngrok-free.app`).

### Step 8: Configure Twilio

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Phone Numbers** → **Manage** → **Active Numbers**
3. Click your Twilio phone number
4. Under **Voice Configuration**:
   - **A call comes in**: Webhook
   - **URL**: `https://def456.ngrok-free.app/voice` (your TwiML ngrok URL)
   - **HTTP Method**: POST
5. Click **Save**

### Step 9: Call Your Number!

Call your Twilio phone number from any phone. You should hear the AI bot greet you and respond to your questions!

## Simplified Setup (2 tunnels with one ngrok command)

If you have ngrok paid plan, you can run both tunnels at once:

```bash
# ngrok.yml
tunnels:
  voxbridge:
    proto: http
    addr: 8765
  twiml:
    proto: http
    addr: 5000
```

Then: `ngrok start --all`

## How It Works

### Audio Flow (Caller speaks):
1. Caller speaks → Twilio captures audio (mulaw 8kHz)
2. Twilio streams to VoxBridge via WebSocket
3. VoxBridge converts & forwards to Voice Bot
4. Voice Bot decodes mulaw → PCM16
5. PCM16 streams to Deepgram for transcription
6. Transcript sent to OpenAI for response
7. Response text sent to ElevenLabs for TTS
8. TTS audio (PCM16) converted to mulaw
9. Sent back through VoxBridge → Twilio → Caller hears response

### Barge-In:
If the caller speaks while the bot is talking:
1. VoxBridge detects audio during bot playback
2. Clears the audio queue (stops TTS playback)
3. Sends `{"type": "barge_in"}` to the bot
4. Bot can stop TTS and listen to new input

## Configuration

### Change the AI Voice

Browse voices at [ElevenLabs Voice Library](https://elevenlabs.io/voice-library).

```bash
export ELEVENLABS_VOICE_ID="pNInz6obpgDQGcFmaJgB"  # "Adam"
```

### Change the AI Personality

Edit `SYSTEM_PROMPT` in `voice_bot.py`:

```python
SYSTEM_PROMPT = """You are a pizza ordering assistant. Help customers
place orders, suggest toppings, and confirm delivery details."""
```

### Change the LLM Model

```bash
export OPENAI_MODEL="gpt-4o"  # More capable, slightly slower
```

### Use a Different Provider

Just change the bridge config! VoxBridge supports 8 providers:

```python
bridge = VoxBridge({
    "provider": "genesys",    # or: amazon_connect, freeswitch, asterisk, avaya, cisco, generic
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
})
```

## Files

| File | Purpose |
|------|---------|
| `voice_bot.py` | AI bot (Deepgram + OpenAI + ElevenLabs) |
| `bridge.py` | VoxBridge bridge (Twilio ↔ Bot) |
| `bridge.yaml` | Config-driven alternative to bridge.py |
| `twiml_server.py` | Twilio webhook (tells Twilio where to stream) |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Missing API keys" | Set all 3 environment variables |
| Bot doesn't respond | Check Deepgram connection in bot logs |
| No audio from bot | Verify ngrok tunnel is pointing to port 8765 |
| Twilio error "11200" | TwiML URL is wrong — check ngrok URL |
| Audio sounds choppy | Network latency; try a closer ngrok region |
| Bot responds too slowly | Use `gpt-4o-mini` (faster) or reduce `max_tokens` |
