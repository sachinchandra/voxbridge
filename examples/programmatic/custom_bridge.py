"""Example: Programmatic bridge with custom event handlers.

This example shows how to use VoxBridge's decorator API to add
custom logic to the audio pipeline - useful for logging, analytics,
audio processing, or routing calls based on DTMF input.

Usage:
    python custom_bridge.py
"""

import asyncio

from voxbridge import VoxBridge, BridgeConfig, CallSession, AudioFrame


# Create the bridge with programmatic config
bridge = VoxBridge(BridgeConfig.from_dict({
    "provider": "twilio",
    "listen_port": 8765,
    "bot_url": "ws://localhost:9000/ws",
}))


@bridge.on_call_start
async def handle_call_start(session: CallSession):
    """Called when a new call connects through the bridge."""
    print(f"=== New call ===")
    print(f"  Session: {session.session_id}")
    print(f"  From: {session.from_number}")
    print(f"  To: {session.to_number}")
    print(f"  Provider: {session.provider}")


@bridge.on_audio
async def process_audio(session: CallSession, frame: AudioFrame) -> AudioFrame:
    """Called for each audio frame from provider to bot.

    Return the frame to forward it, return a modified frame to transform it,
    or return None to drop it (e.g., for muting during hold).
    """
    if session.is_on_hold:
        return None  # Don't send audio to bot while on hold

    # You could add audio processing here:
    # - Volume adjustment
    # - Noise filtering
    # - Audio recording
    # - Real-time analytics
    return frame


@bridge.on_dtmf
async def handle_dtmf(session: CallSession, digit: str):
    """Called when a DTMF digit is received."""
    print(f"DTMF: {digit} (call: {session.call_id})")

    # Example: Transfer to agent queue on digit 0
    if digit == "0":
        print("Transfer requested - routing to agent queue")
        # You could implement transfer logic here


@bridge.on_hold_start
async def handle_hold(session: CallSession):
    """Called when the call is placed on hold."""
    print(f"Call on hold: {session.call_id}")


@bridge.on_hold_end
async def handle_unhold(session: CallSession):
    """Called when the call is taken off hold."""
    print(f"Call off hold: {session.call_id}")


@bridge.on_call_end
async def handle_call_end(session: CallSession, event):
    """Called when a call ends."""
    print(f"=== Call ended ===")
    print(f"  Session: {session.session_id}")
    print(f"  Duration: {session.duration_ms}ms")
    print(f"  Reason: {event.reason}")


if __name__ == "__main__":
    print("VoxBridge custom bridge starting...")
    print("Listening for Twilio on ws://0.0.0.0:8765/media-stream")
    print("Forwarding to bot at ws://localhost:9000/ws")
    bridge.run()
