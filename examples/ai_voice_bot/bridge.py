"""VoxBridge — connects Twilio to the AI Voice Bot.

This is the bridge script that:
1. Listens for incoming Twilio Media Streams WebSocket connections
2. Connects to the AI voice bot WebSocket
3. Handles audio routing, codec conversion, and barge-in

Usage:
    python bridge.py

Make sure voice_bot.py is running first!
"""

from voxbridge import VoxBridge, CallSession, AudioFrame

# Create bridge: Twilio on port 8765 → Bot on port 9000
bridge = VoxBridge({
    "provider": "twilio",
    "listen_port": 8765,
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
    print(f"  Audio in: {session.audio_bytes_in} bytes")
    print(f"  Audio out: {session.audio_bytes_out} bytes")


@bridge.on_audio
async def handle_audio(session: CallSession, frame: AudioFrame) -> AudioFrame:
    """Pass-through audio handler. Return the frame to forward it."""
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


if __name__ == "__main__":
    print("VoxBridge starting...")
    print("  Provider: Twilio (ws://0.0.0.0:8765)")
    print("  Bot:      ws://localhost:9000/ws")
    print("\nWaiting for Twilio Media Streams connection...\n")
    bridge.run()
