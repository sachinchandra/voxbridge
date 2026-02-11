"""Simple Echo Bot - A minimal WebSocket voice bot for testing VoxBridge.

This bot does two things:
1. Echoes back any audio it receives (loopback test)
2. Logs all events to the console

Run this bot, then point VoxBridge at it. When you call in via Twilio,
you should hear your own voice echoed back.

Usage:
    pip install websockets
    python test_echo_bot.py

The bot listens on ws://localhost:9000/ws
"""

import asyncio
import json
import websockets


async def echo_bot(websocket):
    """Handle a single voice bot session."""
    print("\n[BOT] New connection from VoxBridge!")

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # Audio data - echo it back
                print(f"[BOT] Audio received: {len(message)} bytes -> echoing back")
                await websocket.send(message)

            elif isinstance(message, str):
                # JSON control message
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "unknown")

                    if msg_type == "start":
                        print(f"[BOT] Call started!")
                        print(f"       Call ID:  {data.get('call_id', 'N/A')}")
                        print(f"       From:     {data.get('from', 'N/A')}")
                        print(f"       To:       {data.get('to', 'N/A')}")
                        print(f"       Provider: {data.get('provider', 'N/A')}")

                    elif msg_type == "stop":
                        print(f"[BOT] Call ended: {data.get('reason', 'normal')}")
                        break

                    elif msg_type == "dtmf":
                        print(f"[BOT] DTMF digit pressed: {data.get('digit', '?')}")

                    else:
                        print(f"[BOT] Message: {data}")

                except json.JSONDecodeError:
                    print(f"[BOT] Raw text: {message[:100]}")

    except websockets.exceptions.ConnectionClosed:
        print("[BOT] Connection closed")

    print("[BOT] Session ended\n")


async def main():
    print("=" * 50)
    print("  VoxBridge Echo Bot - Test Server")
    print("=" * 50)
    print(f"\n  Listening on ws://localhost:9000/ws")
    print(f"  Waiting for VoxBridge connections...\n")

    async with websockets.serve(echo_bot, "localhost", 9000, ping_interval=30):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
