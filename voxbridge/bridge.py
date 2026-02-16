"""VoxBridge - Central bridge orchestrator.

The VoxBridge class is the heart of the SDK. It wires together:
- Provider transport + serializer (telephony side)
- Bot transport (voice bot side)
- Codec conversion pipeline
- Session management
- Event handler dispatching

It runs two bidirectional async loops per call:
1. provider_to_bot: Provider → Serializer → Codec → Bot WebSocket
2. bot_to_provider: Bot WebSocket → Codec → Serializer → Provider
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Awaitable

from loguru import logger

from voxbridge.audio.codecs import codec_registry
from voxbridge.config import BridgeConfig, load_config
from voxbridge.core.events import (
    AnyEvent,
    AudioFrame,
    BargeIn,
    CallEnded,
    CallStarted,
    ClearAudio,
    Codec,
    DTMFReceived,
    EventType,
    HoldEnded,
    HoldStarted,
    Mark,
)
from voxbridge.platform import PlatformClient
from voxbridge.serializers.base import BaseSerializer
from voxbridge.serializers.registry import serializer_registry
from voxbridge.session import CallSession, SessionStore
from voxbridge.transports.base import BaseTransport
from voxbridge.transports.websocket import (
    WebSocketClientTransport,
    WebSocketServer,
    WebSocketServerTransport,
)

# Type for event handler callbacks
EventHandler = Callable[..., Awaitable[Any]]


class VoxBridge:
    """Universal telephony bridge for voice bots.

    Connects any telephony provider to any WebSocket voice bot through
    a unified event model with automatic codec conversion.

    Usage (config-driven):
        bridge = VoxBridge("bridge.yaml")
        bridge.run()

    Usage (programmatic):
        bridge = VoxBridge({
            "provider": "twilio",
            "listen_port": 8765,
            "bot_url": "ws://localhost:9000/ws",
        })

        @bridge.on_call_start
        async def handle_call(session):
            print(f"Call from {session.from_number}")

        @bridge.on_audio
        async def process_audio(session, frame):
            return frame  # return None to drop

        bridge.run()
    """

    def __init__(self, config: BridgeConfig | dict | str | Path) -> None:
        self.config = load_config(config)
        self.sessions = SessionStore()

        # Event handlers
        self._handlers: dict[str, list[EventHandler]] = {
            "on_call_start": [],
            "on_call_end": [],
            "on_audio": [],
            "on_dtmf": [],
            "on_hold_start": [],
            "on_hold_end": [],
            "on_barge_in": [],
            "on_mark": [],
            "on_event": [],  # catch-all
        }

        # Server instance
        self._server: WebSocketServer | None = None

        # Optional HTTP handler for serving TwiML etc. on the same port
        self._http_handler = None

        # SaaS platform client (optional)
        self._platform: PlatformClient | None = None
        if self.config.saas.api_key:
            self._platform = PlatformClient(
                api_key=self.config.saas.api_key,
                platform_url=self.config.saas.platform_url,
                validate_on_start=self.config.saas.validate_on_start,
                report_usage=self.config.saas.report_usage,
            )

    # ------------------------------------------------------------------
    # Decorator API for event handlers
    # ------------------------------------------------------------------

    def on_call_start(self, fn: EventHandler) -> EventHandler:
        """Register a handler for call start events.

        The handler receives (session: CallSession).
        """
        self._handlers["on_call_start"].append(fn)
        return fn

    def on_call_end(self, fn: EventHandler) -> EventHandler:
        """Register a handler for call end events.

        The handler receives (session: CallSession, event: CallEnded).
        """
        self._handlers["on_call_end"].append(fn)
        return fn

    def on_audio(self, fn: EventHandler) -> EventHandler:
        """Register a handler for audio frames (provider → bot direction).

        The handler receives (session: CallSession, frame: AudioFrame).
        Return the frame to forward it, or None to drop it.
        """
        self._handlers["on_audio"].append(fn)
        return fn

    def on_dtmf(self, fn: EventHandler) -> EventHandler:
        """Register a handler for DTMF events.

        The handler receives (session: CallSession, digit: str).
        """
        self._handlers["on_dtmf"].append(fn)
        return fn

    def on_hold_start(self, fn: EventHandler) -> EventHandler:
        """Register a handler for hold start events."""
        self._handlers["on_hold_start"].append(fn)
        return fn

    def on_hold_end(self, fn: EventHandler) -> EventHandler:
        """Register a handler for hold end events."""
        self._handlers["on_hold_end"].append(fn)
        return fn

    def on_barge_in(self, fn: EventHandler) -> EventHandler:
        """Register a handler for barge-in events.

        Fired when the caller speaks while the bot is playing audio.
        The handler receives (session: CallSession).
        The bridge automatically clears queued audio on barge-in.
        """
        self._handlers["on_barge_in"].append(fn)
        return fn

    def on_mark(self, fn: EventHandler) -> EventHandler:
        """Register a handler for audio playback mark events.

        Fired when the provider confirms audio up to a mark has played.
        The handler receives (session: CallSession, mark_name: str).
        """
        self._handlers["on_mark"].append(fn)
        return fn

    def set_http_handler(self, handler) -> None:
        """Set an HTTP handler for non-WebSocket requests on the same port.

        This allows serving TwiML or other HTTP responses alongside the
        WebSocket server, so you only need a single port (and a single
        ngrok tunnel).

        The handler receives a websockets Request object and should
        return a websockets Response.
        """
        self._http_handler = handler

    def on_event(self, fn: EventHandler) -> EventHandler:
        """Register a catch-all handler for any event.

        The handler receives (session: CallSession, event: AnyEvent).
        """
        self._handlers["on_event"].append(fn)
        return fn

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the bridge (blocking). Runs the asyncio event loop."""
        logger.info(f"VoxBridge starting: provider={self.config.provider.type}")
        try:
            asyncio.run(self._run_async())
        except KeyboardInterrupt:
            logger.info("VoxBridge stopped by user")

    async def run_async(self) -> None:
        """Start the bridge (async). Use this if you manage your own event loop."""
        await self._run_async()

    async def _run_async(self) -> None:
        """Internal async entry point."""
        # Validate API key with platform if configured
        if self._platform and self._platform.validate_on_start:
            allowed = await self._platform.validate()
            if not allowed:
                logger.error("VoxBridge: API key rejected or usage limit exceeded. Exiting.")
                await self._platform.close()
                return

        self._server = WebSocketServer(
            host=self.config.provider.listen_host,
            port=self.config.provider.listen_port,
            path=self.config.provider.listen_path,
            handler=self._handle_provider_connection,
            http_handler=self._http_handler,
        )
        try:
            await self._server.serve_forever()
        finally:
            if self._platform:
                await self._platform.close()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_provider_connection(
        self, provider_transport: WebSocketServerTransport
    ) -> None:
        """Handle a new inbound connection from a telephony provider."""
        # Create serializer for this provider
        serializer = serializer_registry.create(self.config.provider.type)

        # Create session
        session = self.sessions.create(
            provider_transport=provider_transport,
            provider_serializer=serializer,
            provider=self.config.provider.type,
        )

        logger.info(f"New provider connection: session={session.session_id}")

        # Set up codec conversion
        provider_codec = Codec(self.config.audio.input_codec)
        bot_codec = Codec(self.config.bot.codec)
        provider_rate = self.config.audio.sample_rate
        bot_rate = self.config.bot.sample_rate
        session.setup_resamplers(provider_rate, bot_rate)

        # Configure barge-in VAD with the provider's codec
        session.barge_in_detector.codec = self.config.audio.input_codec

        # Connect to the voice bot
        bot_transport = WebSocketClientTransport(url=self.config.bot.url)
        try:
            await bot_transport.connect()
            session.bot_transport = bot_transport
        except Exception as e:
            logger.error(f"Failed to connect to bot at {self.config.bot.url}: {e}")
            session.end()
            return

        # Run bidirectional loops
        try:
            provider_to_bot = asyncio.create_task(
                self._provider_to_bot_loop(session, provider_codec, bot_codec)
            )
            bot_to_provider = asyncio.create_task(
                self._bot_to_provider_loop(session, bot_codec, provider_codec)
            )
            session._tasks = [provider_to_bot, bot_to_provider]

            # Wait for either direction to complete
            done, pending = await asyncio.wait(
                [provider_to_bot, bot_to_provider],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other direction
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error(f"Bridge error for session {session.session_id}: {e}")
        finally:
            session.end()
            await bot_transport.disconnect()

            # Report usage to platform
            if self._platform and self._platform.report_usage:
                try:
                    await self._platform.report_call(
                        session_id=session.session_id,
                        call_id=session.call_id,
                        provider=self.config.provider.type,
                        duration_seconds=session.duration_ms / 1000.0,
                        audio_bytes_in=session.audio_bytes_in,
                        audio_bytes_out=session.audio_bytes_out,
                        status="completed",
                    )
                except Exception as e:
                    logger.warning(f"Failed to report usage: {e}")

            self.sessions.remove(session.session_id)
            logger.info(
                f"Session ended: {session.session_id} "
                f"(duration: {session.duration_ms}ms)"
            )

    # ------------------------------------------------------------------
    # Bidirectional loops
    # ------------------------------------------------------------------

    async def _provider_to_bot_loop(
        self,
        session: CallSession,
        provider_codec: Codec,
        bot_codec: Codec,
    ) -> None:
        """Provider → Serializer → Codec → Bot WebSocket."""
        serializer = session.provider_serializer
        provider = session.provider_transport
        bot = session.bot_transport

        if not serializer or not provider or not bot:
            return

        try:
            while session.is_active and provider.is_connected():
                raw = await provider.recv()

                # Deserialize provider message to events
                events = await serializer.deserialize(raw)

                # Check if we need to send a handshake response
                if isinstance(raw, (str, dict)):
                    msg = json.loads(raw) if isinstance(raw, str) else raw
                    response = serializer.handshake_response(msg)
                    if response:
                        await provider.send(json.dumps(response))

                for event in events:
                    # Dispatch to handlers
                    await self._dispatch_event(session, event)

                    if isinstance(event, CallStarted):
                        session.call_id = event.call_id
                        session.from_number = event.from_number
                        session.to_number = event.to_number

                        # Store SIP headers from the provider
                        if event.sip_headers:
                            session.sip_headers = event.sip_headers

                        # Forward call start to bot (including SIP headers)
                        start_json = json.dumps({
                            "type": "start",
                            "call_id": event.call_id,
                            "from": event.from_number,
                            "to": event.to_number,
                            "provider": event.provider,
                            "sip_headers": event.sip_headers,
                            "metadata": event.metadata,
                        })
                        await bot.send(start_json)

                    elif isinstance(event, AudioFrame):
                        # Track inbound audio bytes
                        if event.data:
                            session.audio_bytes_in += len(event.data)

                        # Barge-in detection: caller speech while bot is speaking
                        # Uses energy-based VAD to avoid false triggers on silence
                        if session.is_bot_speaking and session.barge_in_enabled:
                            if event.data and session.barge_in_detector.check(event.data):
                                logger.info(
                                    f"Barge-in detected on session {session.session_id}"
                                )
                                # Clear outbound audio queue
                                cleared = session.clear_outbound_audio()
                                logger.debug(f"Cleared {cleared} audio chunks from queue")

                                # Send clear to provider (flush buffered TTS)
                                clear_event = ClearAudio(call_id=session.call_id)
                                clear_msg = await serializer.serialize(clear_event)
                                if clear_msg:
                                    await provider.send(clear_msg)

                                # Notify bot about barge-in
                                barge_json = json.dumps({
                                    "type": "barge_in",
                                    "call_id": session.call_id,
                                })
                                await bot.send(barge_json)

                                # Dispatch barge-in event to handlers
                                barge_event = BargeIn(call_id=session.call_id)
                                await self._dispatch_event(session, barge_event)

                        # Run through on_audio handlers
                        frame = event
                        for handler in self._handlers["on_audio"]:
                            result = await handler(session, frame)
                            if result is None:
                                frame = None
                                break
                            frame = result

                        if frame and frame.data:
                            # Convert codec and resample
                            converted = session.convert_inbound_audio(
                                frame.data, provider_codec, bot_codec
                            )
                            # Send raw audio to bot
                            await bot.send(converted)

                    elif isinstance(event, CallEnded):
                        session.end()
                        end_json = json.dumps({
                            "type": "stop",
                            "call_id": event.call_id,
                            "reason": event.reason,
                        })
                        await bot.send(end_json)
                        return

                    elif isinstance(event, DTMFReceived):
                        dtmf_json = json.dumps({
                            "type": "dtmf",
                            "call_id": event.call_id,
                            "digit": event.digit,
                        })
                        await bot.send(dtmf_json)

                    elif isinstance(event, Mark):
                        # Provider confirmed playback reached this mark
                        # Remove from pending marks
                        if event.name in session._pending_marks:
                            session._pending_marks.remove(event.name)
                        # If no more pending marks, bot is done speaking
                        if not session._pending_marks:
                            session.is_bot_speaking = False

                        # Notify bot that playback reached this mark
                        mark_json = json.dumps({
                            "type": "mark",
                            "call_id": session.call_id,
                            "name": event.name,
                        })
                        await bot.send(mark_json)

        except Exception as e:
            if session.is_active:
                logger.error(f"Provider-to-bot loop error: {e}")

    async def _bot_to_provider_loop(
        self,
        session: CallSession,
        bot_codec: Codec,
        provider_codec: Codec,
    ) -> None:
        """Bot WebSocket → Codec → Serializer → Provider."""
        serializer = session.provider_serializer
        provider = session.provider_transport
        bot = session.bot_transport

        if not serializer or not provider or not bot:
            return

        try:
            while session.is_active and bot.is_connected():
                raw = await bot.recv()

                if isinstance(raw, bytes):
                    # Track outbound audio bytes
                    session.audio_bytes_out += len(raw)

                    # Mark bot as speaking when sending audio
                    if not session.is_bot_speaking:
                        session.is_bot_speaking = True
                        # Reset VAD for this new speaking turn
                        session.barge_in_detector.reset()

                    # Binary audio from bot - convert and send to provider
                    converted = session.convert_outbound_audio(
                        raw, bot_codec, provider_codec
                    )
                    audio_event = AudioFrame(
                        call_id=session.call_id,
                        codec=provider_codec,
                        sample_rate=self.config.audio.sample_rate,
                        data=converted,
                    )
                    wire_msg = await serializer.serialize(audio_event)
                    if wire_msg is not None:
                        await provider.send(wire_msg)

                elif isinstance(raw, str):
                    # JSON control message from bot
                    try:
                        msg = json.loads(raw)
                        msg_type = msg.get("type", "")

                        if msg_type == "stop":
                            session.end()
                            end_event = CallEnded(
                                call_id=session.call_id,
                                reason=msg.get("reason", "normal"),
                            )
                            wire_msg = await serializer.serialize(end_event)
                            if wire_msg:
                                await provider.send(
                                    wire_msg if isinstance(wire_msg, str)
                                    else json.dumps(wire_msg)
                                )
                            return

                        elif msg_type == "clear":
                            # Bot requests clearing queued audio
                            logger.debug(
                                f"Bot requested audio clear for session "
                                f"{session.session_id}"
                            )
                            session.clear_outbound_audio()
                            clear_event = ClearAudio(call_id=session.call_id)
                            clear_msg = await serializer.serialize(clear_event)
                            if clear_msg:
                                await provider.send(clear_msg)

                        elif msg_type == "mark":
                            # Bot sends a playback mark
                            mark_name = msg.get("name", "")
                            if mark_name:
                                session._pending_marks.append(mark_name)
                                mark_event = Mark(
                                    call_id=session.call_id,
                                    name=mark_name,
                                )
                                mark_msg = await serializer.serialize(mark_event)
                                if mark_msg:
                                    await provider.send(mark_msg)

                        elif msg_type == "end_of_speech":
                            # Bot signals it finished sending TTS audio
                            # (if no marks pending, update speaking state)
                            if not session._pending_marks:
                                session.is_bot_speaking = False

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON from bot: {raw[:100]}")

        except Exception as e:
            if session.is_active:
                logger.error(f"Bot-to-provider loop error: {e}")

    # ------------------------------------------------------------------
    # Event dispatching
    # ------------------------------------------------------------------

    async def _dispatch_event(self, session: CallSession, event: AnyEvent) -> None:
        """Dispatch an event to registered handlers."""
        # Catch-all handler
        for handler in self._handlers["on_event"]:
            try:
                await handler(session, event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        # Type-specific handlers
        if isinstance(event, CallStarted):
            for handler in self._handlers["on_call_start"]:
                try:
                    await handler(session)
                except Exception as e:
                    logger.error(f"on_call_start handler error: {e}")

        elif isinstance(event, CallEnded):
            for handler in self._handlers["on_call_end"]:
                try:
                    await handler(session, event)
                except Exception as e:
                    logger.error(f"on_call_end handler error: {e}")

        elif isinstance(event, DTMFReceived):
            for handler in self._handlers["on_dtmf"]:
                try:
                    await handler(session, event.digit)
                except Exception as e:
                    logger.error(f"on_dtmf handler error: {e}")

        elif isinstance(event, HoldStarted):
            session.is_on_hold = True
            for handler in self._handlers["on_hold_start"]:
                try:
                    await handler(session)
                except Exception as e:
                    logger.error(f"on_hold_start handler error: {e}")

        elif isinstance(event, HoldEnded):
            session.is_on_hold = False
            for handler in self._handlers["on_hold_end"]:
                try:
                    await handler(session)
                except Exception as e:
                    logger.error(f"on_hold_end handler error: {e}")

        elif isinstance(event, BargeIn):
            for handler in self._handlers["on_barge_in"]:
                try:
                    await handler(session)
                except Exception as e:
                    logger.error(f"on_barge_in handler error: {e}")

        elif isinstance(event, Mark):
            for handler in self._handlers["on_mark"]:
                try:
                    await handler(session, event.name)
                except Exception as e:
                    logger.error(f"on_mark handler error: {e}")
