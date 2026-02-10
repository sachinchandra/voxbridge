"""Example: Simple echo bot that VoxBridge connects to.

This is a minimal voice bot that receives audio from VoxBridge
and echoes it back. It demonstrates the bot-side protocol.

Run this bot, then start VoxBridge with bridge.yaml.

Usage:
    python my_bot.py
    # In another terminal:
    voxbridge run --config bridge.yaml
"""

import asyncio
import json

import websockets


async def handle_connection(websocket):
    """Handle a connection from VoxBridge."""
    print("VoxBridge connected!")

    async for message in websocket:
        if isinstance(message, bytes):
            # Audio frame - echo it back
            await websocket.send(message)

        elif isinstance(message, str):
            # JSON control message
            msg = json.loads(message)
            msg_type = msg.get("type", "")

            if msg_type == "start":
                print(f"Call started: {msg.get('call_id')}")
                print(f"  From: {msg.get('from')}")
                print(f"  To: {msg.get('to')}")
                print(f"  Provider: {msg.get('provider')}")

            elif msg_type == "dtmf":
                print(f"DTMF: {msg.get('digit')}")

            elif msg_type == "stop":
                print(f"Call ended: {msg.get('call_id')}")
                break

    print("Connection closed")


async def main():
    print("Echo bot listening on ws://localhost:9000/ws")
    async with websockets.serve(handle_connection, "localhost", 9000):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
