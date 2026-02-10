"""Example: SIP-to-WebSocket bridge.

This example accepts incoming SIP calls and bridges the audio
to a WebSocket voice bot. Requires the SIP transport:
    pip install voxbridge[sip]

Usage:
    python sip_to_ws.py
"""

import asyncio

from loguru import logger

from voxbridge import VoxBridge, BridgeConfig


def main():
    """Run a SIP-to-WebSocket bridge.

    NOTE: SIP transport requires pjsua2 which needs native PJSIP libraries.
    This example shows the configuration pattern. For WebSocket-only usage,
    see the config_driven or programmatic examples.
    """
    config = BridgeConfig.from_dict({
        "provider": "generic",  # SIP audio arrives as raw PCM
        "listen_port": 5060,
        "bot_url": "ws://localhost:9000/ws",
        "bot_codec": "pcm16",
        "bot_sample_rate": 16000,
    })

    bridge = VoxBridge(config)

    @bridge.on_call_start
    async def handle_call(session):
        logger.info(f"SIP call received: {session.call_id}")

    @bridge.on_call_end
    async def handle_end(session, event):
        logger.info(f"SIP call ended: {session.call_id} ({session.duration_ms}ms)")

    print("SIP-to-WebSocket bridge starting...")
    print("Note: Requires pjsua2. Install with: pip install voxbridge[sip]")
    bridge.run()


if __name__ == "__main__":
    main()
