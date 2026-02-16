"""Combined server — TwiML webhook + VoxBridge WebSocket on ONE port.

This solves the ngrok free-plan limitation (1 tunnel only) by serving
both the HTTP TwiML webhook and the VoxBridge WebSocket on port 8765.

- POST /voice  → returns TwiML (tells Twilio to open a Media Stream)
- WebSocket /  → VoxBridge handles the Twilio Media Stream

Usage:
    python voice_bot.py   # Terminal 1 — AI bot on port 9000
    python server.py      # Terminal 2 — combined server on port 8765
    ngrok http 8765       # Terminal 3 — single tunnel

Then set Twilio webhook to: https://YOUR_NGROK/voice
That's it! Only 3 terminals needed.
"""

from __future__ import annotations

import asyncio

from voxbridge import VoxBridge, CallSession, AudioFrame

# -------------------------------------------------------------------
# VoxBridge Bridge setup
# -------------------------------------------------------------------

bridge = VoxBridge({
    "provider": "twilio",
    "listen_port": 8765,
    "listen_path": "/",
    "bot_url": "ws://localhost:9000/ws",
    "audio": {
        "input_codec": "mulaw",
        "output_codec": "mulaw",
        "sample_rate": 8000,
    },
    "bot": {
        "codec": "mulaw",
        "sample_rate": 8000,
    },
})


@bridge.on_call_start
async def handle_call_start(session: CallSession):
    print(f"\n[Bridge] Call started!")
    print(f"  Session:  {session.session_id}")
    print(f"  Call ID:  {session.call_id}")
    print(f"  From:     {session.from_number}")
    print(f"  To:       {session.to_number}")
    if session.sip_headers:
        print(f"  SIP Hdrs: {session.sip_headers}")


@bridge.on_call_end
async def handle_call_end(session: CallSession, event):
    print(f"\n[Bridge] Call ended: {session.call_id}")
    print(f"  Duration: {session.duration_ms}ms")
    print(f"  Audio in:  {session.audio_bytes_in} bytes")
    print(f"  Audio out: {session.audio_bytes_out} bytes")


@bridge.on_audio
async def handle_audio(session: CallSession, frame: AudioFrame) -> AudioFrame:
    return frame


@bridge.on_dtmf
async def handle_dtmf(session: CallSession, digit: str):
    print(f"[Bridge] DTMF digit: {digit}")


@bridge.on_barge_in
async def handle_barge_in(session: CallSession):
    print(f"[Bridge] Barge-in detected on call {session.call_id}")


@bridge.on_mark
async def handle_mark(session: CallSession, mark_name: str):
    print(f"[Bridge] Playback mark: {mark_name}")


# -------------------------------------------------------------------
# TwiML HTTP handler — served on the same port as WebSocket
#
# The http_handler receives an aiohttp request and must return a
# tuple of (status_code, content_type, body_string).
# -------------------------------------------------------------------

async def handle_http(request):
    """Handle plain HTTP requests on the WebSocket port.

    When Twilio calls POST /voice, we return TwiML that tells Twilio
    to open a Media Stream WebSocket back to the same host.
    """
    path = request.path

    if "/voice" in path:
        # Auto-detect the public host from the incoming request
        host = request.headers.get("Host", "localhost:8765")

        ws_url = f"wss://{host}/"

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="sip_caller_name" value="VoxBridge Test" />
        </Stream>
    </Connect>
</Response>"""

        print(f"[TwiML] Incoming call → streaming to {ws_url}")
        return (200, "text/xml", twiml)

    # Default 404
    return (404, "text/plain", "Not Found")


# Register the HTTP handler with VoxBridge
bridge.set_http_handler(handle_http)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  VoxBridge Combined Server (HTTP + WebSocket)")
    print(f"{'='*60}")
    print(f"  Port 8765:")
    print(f"    POST /voice  → TwiML webhook (for Twilio)")
    print(f"    WS   /       → Media Stream  (for Twilio)")
    print(f"")
    print(f"  Step 1: python voice_bot.py   (Terminal 1)")
    print(f"  Step 2: python server.py      (Terminal 2 — this)")
    print(f"  Step 3: ngrok http 8765       (Terminal 3)")
    print(f"  Step 4: Set Twilio webhook → https://YOUR_NGROK/voice")
    print(f"  Step 5: Call your Twilio number!")
    print(f"{'='*60}\n")

    bridge.run()
