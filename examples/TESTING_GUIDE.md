# VoxBridge Testing Guide

## Quick Test: Twilio + Echo Bot (Hear Your Own Voice)

### What You Need
- Python 3.10+
- A Twilio account (free trial works: https://www.twilio.com/try-twilio)
- ngrok (free: https://ngrok.com/download) to expose localhost to the internet

### Architecture
```
Your Phone → Twilio → ngrok → VoxBridge (port 8765) → Echo Bot (port 9000) → back to you
```

---

### Step 1: Install VoxBridge
```bash
pip install voxbridge-io
# or from local:
pip install -e .
```

### Step 2: Start the Echo Bot
```bash
python examples/test_echo_bot.py
```
You should see:
```
  VoxBridge Echo Bot - Test Server
  Listening on ws://localhost:9000/ws
```

### Step 3: Start the Bridge (new terminal)
```bash
python examples/test_bridge.py
```
You should see:
```
  Bridge:  ws://localhost:8765/media-stream
  Bot:     ws://localhost:9000/ws (echo bot)
```

### Step 4: Expose with ngrok (new terminal)
```bash
ngrok http 8765
```
ngrok will give you a URL like: `https://abc123.ngrok-free.app`

### Step 5: Configure Twilio
1. Go to https://console.twilio.com
2. Buy a phone number (free trial gives you one)
3. Go to **Phone Numbers** → Click your number
4. Under **Voice Configuration**:
   - **A Call Comes In**: select **TwiML Bin**
   - Create a new TwiML Bin with this content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://YOUR_NGROK_URL/media-stream" />
  </Connect>
</Response>
```

Replace `YOUR_NGROK_URL` with your ngrok URL (e.g., `abc123.ngrok-free.app`).

### Step 6: Call Your Twilio Number!
Call the Twilio phone number from your phone. You should:
1. See "Call started" in both the bridge and bot terminals
2. **Hear your own voice echoed back** (with a slight delay)
3. See audio bytes flowing in the logs

---

## Testing Without Twilio (Local WebSocket Test)

If you don't want to set up Twilio yet, you can test the serializers and codec pipeline directly:

```bash
# Run the SDK tests
python -m pytest tests/ -v
```

Or test with a generic WebSocket provider:

```python
from voxbridge import VoxBridge

bridge = VoxBridge({
    "provider": "generic",     # No Twilio needed
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
})

bridge.run()
```

Then send raw audio bytes to `ws://localhost:8765/media-stream` from any WebSocket client.

---

## Testing Other Providers

Just change the provider in the config:

| Provider | Config Value | Protocol |
|----------|-------------|----------|
| Twilio | `twilio` | JSON + base64 mulaw |
| Genesys | `genesys` | AudioHook (JSON + binary) |
| Amazon Connect | `amazon_connect` | JSON + binary PCM16 |
| FreeSWITCH | `freeswitch` | mod_ws (JSON + binary mulaw) |
| Asterisk | `asterisk` | ARI (JSON + binary mulaw) |
| Avaya | `avaya` | OCSAPI (JSON + binary mulaw) |
| Cisco | `cisco` | WebEx CC (JSON + binary mulaw) |
| Generic | `generic` | Raw binary + JSON |
