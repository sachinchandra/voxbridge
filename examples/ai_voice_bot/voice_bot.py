"""AI Voice Bot — Deepgram STT + OpenAI LLM + ElevenLabs TTS.

A low-latency WebSocket voice bot that:
1. Receives raw audio from VoxBridge (mulaw 8kHz)
2. Streams it to Deepgram for real-time speech-to-text
3. Streams OpenAI GPT response token-by-token
4. Streams ElevenLabs TTS audio back in real-time (no buffering!)

Optimizations over v1:
- OpenAI streaming (first token → TTS in ~200ms instead of ~1s)
- ElevenLabs streaming (audio starts playing as it arrives)
- Shared aiohttp session (no TLS handshake per request)
- Sentence-level TTS chunking with streaming overlap
- Reduced Deepgram endpointing for faster turn detection
- Barge-in cancellation of in-flight TTS

Usage:
    pip install websockets aiohttp
    export DEEPGRAM_API_KEY="your-key"
    export OPENAI_API_KEY="your-key"
    export ELEVENLABS_API_KEY="your-key"
    python voice_bot.py
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import sys
import time
from typing import Any

import aiohttp
import websockets
from websockets.server import WebSocketServerProtocol

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# ElevenLabs voice ID — "Rachel" is a good default
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

# OpenAI model
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Bot personality
SYSTEM_PROMPT = """You are a friendly AI phone assistant. Keep responses short
and conversational — 1 to 2 sentences max. You're talking on a phone call, so
be natural and concise. Don't use markdown or special formatting."""

BOT_HOST = "0.0.0.0"
BOT_PORT = 9000


# ---------------------------------------------------------------------------
# Audio conversion helpers
# ---------------------------------------------------------------------------

# mu-law decompression table (ITU-T G.711)
MULAW_DECODE_TABLE = []
for _i in range(256):
    _i_inv = ~_i & 0xFF
    _sign = -1 if (_i_inv & 0x80) else 1
    _exp = (_i_inv >> 4) & 0x07
    _mant = _i_inv & 0x0F
    _sample = _sign * (((_mant << 1) + 33) * (1 << (_exp + 2)) - 132)
    MULAW_DECODE_TABLE.append(max(-32768, min(32767, _sample)))


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """Convert mu-law bytes to signed 16-bit PCM (little-endian)."""
    samples = [MULAW_DECODE_TABLE[b] for b in mulaw_bytes]
    return struct.pack(f"<{len(samples)}h", *samples)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert signed 16-bit PCM (little-endian) to mu-law."""
    n_samples = len(pcm_bytes) // 2
    samples = struct.unpack(f"<{n_samples}h", pcm_bytes)
    result = bytearray(n_samples)
    for i, sample in enumerate(samples):
        sign = 0x80 if sample >= 0 else 0
        if sample < 0:
            sample = -sample
        sample = min(sample, 32635)
        sample += 0x84

        exponent = 7
        exp_mask = 0x4000
        while exponent > 0:
            if sample & exp_mask:
                break
            exponent -= 1
            exp_mask >>= 1

        mantissa = (sample >> (exponent + 3)) & 0x0F
        mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
        result[i] = mulaw_byte

    return bytes(result)


def downsample_16k_to_8k(pcm16_data: bytes) -> bytes:
    """Simple 2:1 downsampling from 16kHz to 8kHz PCM16."""
    n_samples = len(pcm16_data) // 2
    if n_samples == 0:
        return b""
    samples = struct.unpack(f"<{n_samples}h", pcm16_data)
    downsampled = samples[::2]
    return struct.pack(f"<{len(downsampled)}h", *downsampled)


# ---------------------------------------------------------------------------
# Shared HTTP session — reuse TCP connections across all API calls
# ---------------------------------------------------------------------------

_http_session: aiohttp.ClientSession | None = None


async def get_http_session() -> aiohttp.ClientSession:
    """Get or create a shared aiohttp session (reuses TCP + TLS)."""
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session


# ---------------------------------------------------------------------------
# Deepgram STT (streaming)
# ---------------------------------------------------------------------------

class DeepgramSTT:
    """Real-time speech-to-text via Deepgram WebSocket API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws: Any = None
        self.transcript_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False

    async def connect(self) -> None:
        """Open a streaming connection to Deepgram."""
        url = (
            "wss://api.deepgram.com/v1/listen"
            "?encoding=linear16"
            "&sample_rate=8000"
            "&channels=1"
            "&punctuate=true"
            "&interim_results=false"
            "&endpointing=200"       # 200ms silence = end of utterance (faster than 300)
            "&vad_events=true"
            "&smart_format=true"
        )
        headers = {"Authorization": f"Token {self.api_key}"}
        self.ws = await websockets.connect(url, additional_headers=headers)
        self._running = True
        asyncio.create_task(self._recv_loop())
        print("[Deepgram] Connected (endpointing=200ms)")

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """Send PCM16 audio to Deepgram."""
        if self.ws and self._running:
            try:
                await self.ws.send(pcm16_bytes)
            except Exception:
                pass

    async def _recv_loop(self) -> None:
        """Receive transcripts from Deepgram."""
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                if data.get("type") == "Results":
                    # Only use final results (is_final=true)
                    if not data.get("is_final", False):
                        continue
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "").strip()
                        if transcript:
                            print(f"[Deepgram] Final: {transcript}")
                            await self.transcript_queue.put(transcript)
        except Exception as e:
            if self._running:
                print(f"[Deepgram] Recv error: {e}")
        finally:
            self._running = False

    async def close(self) -> None:
        self._running = False
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# OpenAI LLM — STREAMING
# ---------------------------------------------------------------------------

class OpenAILLM:
    """Streaming chat completion via OpenAI API.

    Yields tokens as they arrive instead of waiting for the full response.
    This cuts time-to-first-word from ~1s to ~200ms.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.conversation: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def stream_response(self, user_text: str):
        """Yield text chunks as they stream from OpenAI.

        This is an async generator that yields partial text as tokens arrive.
        The caller can start TTS on the first sentence while the rest streams in.
        """
        self.conversation.append({"role": "user", "content": user_text})

        # Keep conversation short to avoid context bloat
        if len(self.conversation) > 20:
            self.conversation = [self.conversation[0]] + self.conversation[-10:]

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": self.conversation,
            "max_tokens": 150,
            "temperature": 0.7,
            "stream": True,  # ← KEY: enable streaming
        }

        full_response = ""
        session = await get_http_session()

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[OpenAI] Error {resp.status}: {error_text}")
                    yield "Sorry, I had trouble thinking of a response."
                    return

                # Parse SSE stream
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # strip "data: "
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            full_response += token
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        except Exception as e:
            print(f"[OpenAI] Stream error: {e}")
            yield "Sorry, something went wrong."
            return

        self.conversation.append({"role": "assistant", "content": full_response})
        print(f"[OpenAI] Full response: {full_response}")


# ---------------------------------------------------------------------------
# ElevenLabs TTS — TRUE STREAMING
# ---------------------------------------------------------------------------

class ElevenLabsTTS:
    """Streaming text-to-speech via ElevenLabs.

    Instead of buffering the entire audio response, this streams chunks
    back as they arrive from ElevenLabs, converting and sending each one
    immediately. This cuts TTS latency from ~1.5s to ~300ms.
    """

    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id

    async def synthesize_streaming(self, text: str, ws, cancel_event: asyncio.Event):
        """Stream TTS audio directly to VoxBridge WebSocket as it arrives.

        Args:
            text: Text to synthesize
            ws: WebSocket to send audio chunks to
            cancel_event: Set this to cancel mid-stream (barge-in)

        Returns:
            True if completed, False if cancelled
        """
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
            f"?output_format=pcm_16000"
            f"&optimize_streaming_latency=3"  # ← Aggressive latency optimization
        )
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        session = await get_http_session()
        total_bytes = 0
        t_start = time.monotonic()
        first_chunk = True

        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[ElevenLabs] Error {resp.status}: {error_text}")
                    return False

                # Buffer for accumulating PCM data for aligned processing
                pcm_buffer = b""

                async for chunk in resp.content.iter_chunked(4096):
                    # Check for barge-in cancellation
                    if cancel_event.is_set():
                        print("[ElevenLabs] Cancelled (barge-in)")
                        return False

                    if first_chunk:
                        elapsed = (time.monotonic() - t_start) * 1000
                        print(f"[ElevenLabs] First audio chunk in {elapsed:.0f}ms")
                        first_chunk = False

                    pcm_buffer += chunk

                    # Process in 640-byte blocks (20ms at 16kHz, 16-bit)
                    # which becomes 320 bytes at 8kHz → 160 mulaw bytes (20ms)
                    block_size = 640
                    while len(pcm_buffer) >= block_size:
                        block = pcm_buffer[:block_size]
                        pcm_buffer = pcm_buffer[block_size:]

                        # Downsample 16kHz → 8kHz
                        pcm_8k = downsample_16k_to_8k(block)
                        # Convert to mulaw
                        mulaw_chunk = pcm16_to_mulaw(pcm_8k)
                        total_bytes += len(mulaw_chunk)

                        try:
                            await ws.send(mulaw_chunk)
                        except Exception:
                            return False

                # Flush remaining buffer
                if pcm_buffer and not cancel_event.is_set():
                    # Pad to even sample count
                    if len(pcm_buffer) % 2 != 0:
                        pcm_buffer += b"\x00"
                    pcm_8k = downsample_16k_to_8k(pcm_buffer)
                    if pcm_8k:
                        mulaw_chunk = pcm16_to_mulaw(pcm_8k)
                        total_bytes += len(mulaw_chunk)
                        try:
                            await ws.send(mulaw_chunk)
                        except Exception:
                            return False

        except Exception as e:
            print(f"[ElevenLabs] Stream error: {e}")
            return False

        elapsed = (time.monotonic() - t_start) * 1000
        duration_ms = (total_bytes / 8000) * 1000  # 8kHz mulaw = 8000 bytes/sec
        print(f"[ElevenLabs] Streamed {total_bytes} bytes ({duration_ms:.0f}ms audio) in {elapsed:.0f}ms")
        return True


# ---------------------------------------------------------------------------
# Voice Bot — the WebSocket server that VoxBridge connects to
# ---------------------------------------------------------------------------

class VoiceBot:
    """Low-latency WebSocket voice bot server.

    Pipeline: Deepgram STT → OpenAI streaming → ElevenLabs streaming → VoxBridge

    Key optimizations:
    - Sentence-level TTS: starts speaking the first sentence while LLM
      is still generating the rest
    - Streaming TTS: audio plays as ElevenLabs generates it (no buffering)
    - Barge-in aware: cancels in-flight TTS when caller interrupts
    """

    def __init__(self):
        self.stt = DeepgramSTT(DEEPGRAM_API_KEY)
        self.llm = OpenAILLM(OPENAI_API_KEY, OPENAI_MODEL)
        self.tts = ElevenLabsTTS(ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID)
        self._cancel_tts = asyncio.Event()
        self._is_speaking = False

    async def handle_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle a single call from VoxBridge."""
        print("\n" + "=" * 60)
        print("[Bot] New call connected!")
        print("=" * 60)

        # Reset state for this call
        self._cancel_tts.clear()
        self._is_speaking = False

        # Connect to Deepgram STT
        await self.stt.connect()

        # Start the response pipeline
        response_task = asyncio.create_task(self._response_loop(ws))

        try:
            async for message in ws:
                if isinstance(message, bytes):
                    # Raw audio from VoxBridge (mulaw 8kHz)
                    pcm16 = mulaw_to_pcm16(message)
                    await self.stt.send_audio(pcm16)

                elif isinstance(message, str):
                    try:
                        msg = json.loads(message)
                        msg_type = msg.get("type", "")

                        if msg_type == "start":
                            call_id = msg.get("call_id", "unknown")
                            from_num = msg.get("from", "unknown")
                            sip_headers = msg.get("sip_headers", {})
                            print(f"[Bot] Call started: {call_id}")
                            print(f"[Bot] Caller: {from_num}")
                            if sip_headers:
                                print(f"[Bot] SIP Headers: {sip_headers}")

                            # Send a greeting (streamed!)
                            await self._speak(ws, "Hello! How can I help you today?")

                        elif msg_type == "stop":
                            print("[Bot] Call ended")
                            break

                        elif msg_type == "dtmf":
                            digit = msg.get("digit", "")
                            print(f"[Bot] DTMF: {digit}")

                        elif msg_type == "barge_in":
                            print("[Bot] ⚡ Barge-in — cancelling TTS")
                            self._cancel_tts.set()

                        elif msg_type == "mark":
                            mark_name = msg.get("name", "")
                            print(f"[Bot] Playback mark: {mark_name}")

                    except json.JSONDecodeError:
                        pass

        except websockets.exceptions.ConnectionClosed:
            print("[Bot] Connection closed")
        finally:
            response_task.cancel()
            await self.stt.close()
            # Reset conversation for next call
            self.llm.conversation = [self.llm.conversation[0]]
            print("[Bot] Call cleanup complete\n")

    async def _response_loop(self, ws: WebSocketServerProtocol) -> None:
        """Listen for transcripts and generate streaming responses."""
        try:
            while True:
                transcript = await self.stt.transcript_queue.get()
                if not transcript:
                    continue

                t_start = time.monotonic()
                print(f"\n[Bot] 🎤 User said: '{transcript}'")

                # Stream LLM response and TTS it sentence-by-sentence
                await self._stream_and_speak(ws, transcript)

                elapsed = (time.monotonic() - t_start) * 1000
                print(f"[Bot] ✅ Full response in {elapsed:.0f}ms")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Bot] Response loop error: {e}")

    async def _stream_and_speak(self, ws, user_text: str) -> None:
        """Stream LLM tokens, accumulate sentences, TTS each sentence immediately.

        This is the key latency optimization: instead of waiting for the full
        LLM response and then the full TTS audio, we:
        1. Stream tokens from OpenAI
        2. As soon as we have a complete sentence, fire off TTS
        3. Stream TTS audio to the caller while OpenAI keeps generating
        """
        sentence_buffer = ""
        sentence_delimiters = {'.', '!', '?', ':', ';'}
        is_first_sentence = True

        self._cancel_tts.clear()

        async for token in self.llm.stream_response(user_text):
            if self._cancel_tts.is_set():
                print("[Bot] LLM streaming cancelled (barge-in)")
                break

            sentence_buffer += token

            # Check if we have a complete sentence
            has_delimiter = any(d in token for d in sentence_delimiters)

            if has_delimiter and len(sentence_buffer.strip()) > 5:
                # We have a sentence — speak it immediately
                sentence = sentence_buffer.strip()
                sentence_buffer = ""

                if is_first_sentence:
                    is_first_sentence = False
                    print(f"[Bot] 🗣️ Speaking first sentence: '{sentence}'")

                await self._speak(ws, sentence)

                if self._cancel_tts.is_set():
                    break

        # Speak any remaining text
        remaining = sentence_buffer.strip()
        if remaining and not self._cancel_tts.is_set():
            await self._speak(ws, remaining)

    async def _speak(self, ws, text: str) -> None:
        """Stream TTS audio directly to VoxBridge (no buffering)."""
        if not text or self._cancel_tts.is_set():
            return

        self._is_speaking = True
        self._cancel_tts.clear()

        completed = await self.tts.synthesize_streaming(text, ws, self._cancel_tts)

        self._is_speaking = False

        # Send end-of-speech marker
        if completed:
            try:
                await ws.send(json.dumps({"type": "end_of_speech"}))
            except Exception:
                pass

    async def _speak_greeting(self, ws, text: str) -> None:
        """Alias for speaking — used for the initial greeting."""
        await self._speak(ws, text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    # Validate API keys
    missing = []
    if not DEEPGRAM_API_KEY:
        missing.append("DEEPGRAM_API_KEY")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")

    if missing:
        print("Missing API keys! Set these environment variables:")
        for key in missing:
            print(f"  export {key}='your-key-here'")
        sys.exit(1)

    bot = VoiceBot()

    print(f"\n{'='*60}")
    print(f"  AI Voice Bot (Low-Latency Streaming)")
    print(f"{'='*60}")
    print(f"  WebSocket:  ws://{BOT_HOST}:{BOT_PORT}/ws")
    print(f"  STT:        Deepgram (streaming, endpointing=200ms)")
    print(f"  LLM:        OpenAI {OPENAI_MODEL} (streaming)")
    print(f"  TTS:        ElevenLabs (streaming, latency=3)")
    print(f"{'='*60}")
    print(f"\nWaiting for VoxBridge to connect...\n")

    async with websockets.serve(bot.handle_connection, BOT_HOST, BOT_PORT, ping_interval=20):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
