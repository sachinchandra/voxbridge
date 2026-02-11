"""Test Bridge - Run VoxBridge connecting Twilio to the Echo Bot.

This script starts VoxBridge configured for Twilio Media Streams,
pointing to the echo bot running on localhost:9000.

Usage:
    1. Start the echo bot first:    python test_echo_bot.py
    2. Then start this bridge:      python test_bridge.py
    3. Configure Twilio to point to this server (see instructions below)
    4. Call your Twilio number - you should hear your voice echoed back!

The bridge listens on port 8765 for Twilio WebSocket connections.
"""

from voxbridge import VoxBridge

# Create bridge: Twilio -> Echo Bot
bridge = VoxBridge({
    "provider": "twilio",
    "listen_port": 8765,
    "listen_path": "/media-stream",
    "bot_url": "ws://localhost:9000/ws",
    "bot_codec": "pcm16",
    "bot_sample_rate": 16000,
    # Uncomment and add your API key for SaaS usage tracking:
    # "api_key": "vxb_your_api_key_here",
})


@bridge.on_call_start
async def on_call(session):
    print(f"\n{'='*50}")
    print(f"  CALL STARTED")
    print(f"  Session: {session.session_id[:8]}...")
    print(f"  From:    {session.from_number}")
    print(f"  To:      {session.to_number}")
    print(f"{'='*50}\n")


@bridge.on_audio
async def on_audio(session, frame):
    # Just pass audio through - the echo bot will echo it back
    return frame


@bridge.on_dtmf
async def on_dtmf(session, digit):
    print(f"  DTMF: {digit}")


@bridge.on_call_end
async def on_end(session, event):
    print(f"\n{'='*50}")
    print(f"  CALL ENDED")
    print(f"  Duration: {session.duration_ms / 1000:.1f}s")
    print(f"  Reason:   {event.reason}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════╗
║         VoxBridge Test Bridge (Twilio)           ║
╠══════════════════════════════════════════════════╣
║  Bridge:  ws://localhost:8765/media-stream       ║
║  Bot:     ws://localhost:9000/ws (echo bot)      ║
║                                                  ║
║  Make sure the echo bot is running first!        ║
╚══════════════════════════════════════════════════╝
""")
    bridge.run()
