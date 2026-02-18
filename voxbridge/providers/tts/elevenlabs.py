"""ElevenLabs streaming Text-to-Speech provider.

Uses ElevenLabs' WebSocket streaming API for ultra-low-latency TTS.
Audio is streamed as PCM16 chunks for immediate playback.

Requires: pip install websockets (already a voxbridge dependency)
API key: https://elevenlabs.io/
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any, AsyncIterator

from loguru import logger

from voxbridge.providers.base import BaseTTS, TTSChunk

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None  # type: ignore


class ElevenLabsTTS(BaseTTS):
    """ElevenLabs real-time streaming TTS.

    Uses the WebSocket streaming API for low-latency text-to-speech.
    Text is sent incrementally and audio chunks are received as they're
    generated, enabling sub-second time-to-first-byte.

    Args:
        api_key: ElevenLabs API key.
        voice_id: Voice identifier.
        model_id: TTS model (default: "eleven_turbo_v2_5").
        output_format: Audio output format (default: "pcm_24000").
        stability: Voice stability (0.0-1.0, default: 0.5).
        similarity_boost: Voice similarity (0.0-1.0, default: 0.75).
        style: Style exaggeration (0.0-1.0, default: 0.0).
        optimize_streaming_latency: Latency optimization level (0-4, default: 3).
    """

    BASE_WS_URL = "wss://api.elevenlabs.io/v1/text-to-speech"

    def __init__(
        self,
        api_key: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel (default)
        model_id: str = "eleven_turbo_v2_5",
        output_format: str = "pcm_24000",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        optimize_streaming_latency: int = 3,
    ):
        if websockets is None:
            raise ImportError(
                "websockets is required for ElevenLabsTTS. "
                "Install with: pip install websockets"
            )

        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._optimize_streaming_latency = optimize_streaming_latency

        self._ws: WebSocketClientProtocol | None = None
        self._audio_queue: asyncio.Queue[TTSChunk | None] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None
        self._connected = False

        # Parse sample rate from output_format
        self._sample_rate_hz = self._parse_sample_rate(output_format)

    async def connect(self) -> None:
        """Open a WebSocket connection to ElevenLabs TTS."""
        url = (
            f"{self.BASE_WS_URL}/{self._voice_id}/stream-input"
            f"?model_id={self._model_id}"
            f"&output_format={self._output_format}"
            f"&optimize_streaming_latency={self._optimize_streaming_latency}"
        )

        logger.info(
            f"Connecting to ElevenLabs TTS "
            f"(voice={self._voice_id}, model={self._model_id})"
        )

        self._ws = await websockets.connect(
            url,
            additional_headers={"xi-api-key": self._api_key},
            ping_interval=5,
            ping_timeout=20,
        )
        self._connected = True

        # Send initial configuration (BOS - Beginning of Stream)
        bos_message = {
            "text": " ",
            "voice_settings": {
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
                "style": self._style,
            },
            "xi_api_key": self._api_key,
        }
        await self._ws.send(json.dumps(bos_message))

        # Start background receiver
        self._recv_task = asyncio.create_task(self._receive_loop())
        logger.info("ElevenLabs TTS connected")

    async def synthesize(self, text: str) -> AsyncIterator[TTSChunk]:
        """Send text to ElevenLabs and yield audio chunks.

        For best results, send complete sentences. The text is buffered
        and audio is streamed back as it's generated.

        Args:
            text: Text to synthesize. Complete sentences work best.

        Yields:
            TTSChunk objects with PCM16 audio data.
        """
        if not self._ws or not self._connected:
            logger.warning("ElevenLabs TTS not connected, skipping synthesis")
            return

        # Send text chunk
        msg = {
            "text": text,
            "try_trigger_generation": True,
        }
        try:
            await self._ws.send(json.dumps(msg))
        except Exception as e:
            logger.error(f"ElevenLabs send error: {e}")
            return

        # Yield audio chunks as they arrive
        # Note: we yield from the shared queue, which receives audio
        # for all synthesize calls on this connection. The pipeline
        # orchestrator handles this correctly since it calls synthesize
        # sentence by sentence.
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                # No audio received for 5s, assume this sentence is done
                break

            if chunk is None:
                break

            yield chunk

            if chunk.is_final:
                break

    async def flush(self) -> AsyncIterator[TTSChunk]:
        """Flush remaining audio by sending EOS (End of Stream).

        Tells ElevenLabs to generate any remaining buffered audio.

        Yields:
            Any remaining TTSChunk objects.
        """
        if not self._ws or not self._connected:
            return

        # Send empty string to signal end of input for this generation
        eos_msg = {"text": ""}
        try:
            await self._ws.send(json.dumps(eos_msg))
        except Exception as e:
            logger.error(f"ElevenLabs flush error: {e}")
            return

        # Drain remaining audio
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=3.0
                )
            except asyncio.TimeoutError:
                break

            if chunk is None:
                break
            yield chunk

    async def close(self) -> None:
        """Close the ElevenLabs WebSocket connection."""
        self._connected = False

        if self._ws:
            try:
                # Send EOS
                await self._ws.send(json.dumps({"text": ""}))
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        logger.info("ElevenLabs TTS closed")

    @property
    def sample_rate(self) -> int:
        return self._sample_rate_hz

    @property
    def codec(self) -> str:
        return "pcm16"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """Background task that reads audio from ElevenLabs WebSocket."""
        try:
            async for message in self._ws:
                if isinstance(message, str):
                    data = json.loads(message)

                    # Audio data (base64 encoded)
                    audio_b64 = data.get("audio")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        if audio_bytes:
                            await self._audio_queue.put(
                                TTSChunk(
                                    audio=audio_bytes,
                                    sample_rate=self._sample_rate_hz,
                                    is_final=False,
                                )
                            )

                    # Check for final response
                    if data.get("isFinal"):
                        await self._audio_queue.put(
                            TTSChunk(
                                audio=b"",
                                sample_rate=self._sample_rate_hz,
                                is_final=True,
                            )
                        )

                    # Alignment info (optional, for lip sync etc.)
                    if data.get("normalizedAlignment"):
                        logger.debug("ElevenLabs alignment received")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self._connected:
                logger.error(f"ElevenLabs receive error: {e}")
        finally:
            self._connected = False
            await self._audio_queue.put(None)

    @staticmethod
    def _parse_sample_rate(output_format: str) -> int:
        """Extract sample rate from ElevenLabs output format string."""
        # Formats: pcm_16000, pcm_22050, pcm_24000, pcm_44100
        # Also: mp3_44100_128, ulaw_8000, etc.
        parts = output_format.split("_")
        for part in parts:
            try:
                rate = int(part)
                if rate >= 8000:
                    return rate
            except ValueError:
                continue
        return 24000  # default
