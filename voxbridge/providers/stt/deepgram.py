"""Deepgram streaming Speech-to-Text provider.

Uses Deepgram's real-time WebSocket API for low-latency transcription.
Supports partial results, endpointing, and word-level timestamps.

Requires: pip install websockets (already a voxbridge dependency)
API key: https://console.deepgram.com/
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from loguru import logger

from voxbridge.providers.base import BaseSTT, STTResult

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    websockets = None  # type: ignore


class DeepgramSTT(BaseSTT):
    """Deepgram real-time streaming STT.

    Connects to Deepgram's WebSocket API and streams audio for transcription.
    Returns both interim (partial) and final transcription results.

    Args:
        api_key: Deepgram API key.
        model: Deepgram model (default: "nova-2").
        language: Language code (default: "en-US").
        sample_rate_hz: Input audio sample rate (default: 16000).
        encoding: Audio encoding (default: "linear16" for PCM16).
        interim_results: Whether to return partial results (default: True).
        endpointing: Silence duration in ms to trigger endpointing (default: 300).
        smart_format: Enable smart formatting (default: True).
        vad_events: Enable VAD events (default: True).
        utterance_end_ms: Duration of silence to end utterance (default: 1000).
        extra_params: Additional Deepgram query parameters.
    """

    DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(
        self,
        api_key: str,
        model: str = "nova-2",
        language: str = "en-US",
        sample_rate_hz: int = 16000,
        encoding: str = "linear16",
        interim_results: bool = True,
        endpointing: int = 300,
        smart_format: bool = True,
        vad_events: bool = True,
        utterance_end_ms: int = 1000,
        extra_params: dict[str, Any] | None = None,
    ):
        if websockets is None:
            raise ImportError(
                "websockets is required for DeepgramSTT. "
                "Install with: pip install websockets"
            )

        self._api_key = api_key
        self._model = model
        self._language = language
        self._sample_rate_hz = sample_rate_hz
        self._encoding = encoding
        self._interim_results = interim_results
        self._endpointing = endpointing
        self._smart_format = smart_format
        self._vad_events = vad_events
        self._utterance_end_ms = utterance_end_ms
        self._extra_params = extra_params or {}

        self._ws: WebSocketClientProtocol | None = None
        self._result_queue: asyncio.Queue[STTResult | None] = asyncio.Queue()
        self._recv_task: asyncio.Task | None = None
        self._connected = False

    async def connect(self) -> None:
        """Open a streaming WebSocket connection to Deepgram."""
        params = {
            "model": self._model,
            "language": self._language,
            "sample_rate": str(self._sample_rate_hz),
            "encoding": self._encoding,
            "channels": "1",
            "interim_results": str(self._interim_results).lower(),
            "endpointing": str(self._endpointing),
            "smart_format": str(self._smart_format).lower(),
            "vad_events": str(self._vad_events).lower(),
            "utterance_end_ms": str(self._utterance_end_ms),
        }
        params.update(self._extra_params)

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.DEEPGRAM_WS_URL}?{query}"

        headers = {"Authorization": f"Token {self._api_key}"}

        logger.info(f"Connecting to Deepgram STT (model={self._model})")

        self._ws = await websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=5,
            ping_timeout=20,
        )
        self._connected = True

        # Start background receiver
        self._recv_task = asyncio.create_task(self._receive_loop())
        logger.info("Deepgram STT connected")

    async def send_audio(self, audio: bytes) -> None:
        """Send audio chunk to Deepgram for transcription."""
        if self._ws and self._connected:
            try:
                await self._ws.send(audio)
            except Exception as e:
                logger.error(f"Deepgram send error: {e}")
                self._connected = False

    async def results(self) -> AsyncIterator[STTResult]:
        """Yield transcription results as they arrive from Deepgram."""
        while True:
            result = await self._result_queue.get()
            if result is None:
                break
            yield result

    async def close(self) -> None:
        """Close the Deepgram WebSocket connection."""
        self._connected = False

        if self._ws:
            try:
                # Send close frame to Deepgram
                await self._ws.send(json.dumps({"type": "CloseStream"}))
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

        # Signal end of results
        await self._result_queue.put(None)
        logger.info("Deepgram STT closed")

    @property
    def sample_rate(self) -> int:
        return self._sample_rate_hz

    @property
    def codec(self) -> str:
        return "pcm16" if self._encoding == "linear16" else self._encoding

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """Background task that reads messages from Deepgram WebSocket."""
        try:
            async for message in self._ws:
                if isinstance(message, str):
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "Results":
                        result = self._parse_result(data)
                        if result:
                            await self._result_queue.put(result)

                    elif msg_type == "UtteranceEnd":
                        # Signal utterance boundary with empty final result
                        await self._result_queue.put(
                            STTResult(text="", is_final=True)
                        )

                    elif msg_type == "Metadata":
                        logger.debug(f"Deepgram metadata: {data}")

                    elif msg_type == "Error":
                        logger.error(f"Deepgram error: {data}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self._connected:
                logger.error(f"Deepgram receive error: {e}")
        finally:
            self._connected = False
            await self._result_queue.put(None)

    def _parse_result(self, data: dict) -> STTResult | None:
        """Parse a Deepgram Results message into an STTResult."""
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])

        if not alternatives:
            return None

        best = alternatives[0]
        transcript = best.get("transcript", "").strip()

        if not transcript:
            return None

        is_final = data.get("is_final", False)
        confidence = best.get("confidence", 0.0)

        # Word-level timestamps
        words = []
        for w in best.get("words", []):
            words.append({
                "word": w.get("word", ""),
                "start": w.get("start", 0.0),
                "end": w.get("end", 0.0),
                "confidence": w.get("confidence", 0.0),
            })

        return STTResult(
            text=transcript,
            is_final=is_final,
            confidence=confidence,
            language=self._language,
            words=words,
        )
