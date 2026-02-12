"""AI Voice Bot — Deepgram STT + OpenAI LLM + ElevenLabs TTS.

A complete WebSocket voice bot that:
1. Receives raw audio from VoxBridge (mulaw 8kHz)
2. Streams it to Deepgram for real-time speech-to-text
3. Sends the transcript to OpenAI GPT for a response
4. Streams ElevenLabs TTS audio back through VoxBridge

Usage:
    pip install websockets deepgram-sdk openai elevenlabs aiohttp
    export DEEPGRAM_API_KEY="your-key"
    export OPENAI_API_KEY="your-key"
    export ELEVENLABS_API_KEY="your-key"
    python voice_bot.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import struct
import sys
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
            "&endpointing=300"
            "&vad_events=true"
        )
        headers = {"Authorization": f"Token {self.api_key}"}
        self.ws = await websockets.connect(url, additional_headers=headers)
        self._running = True
        asyncio.create_task(self._recv_loop())
        print("[Deepgram] Connected")

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
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "").strip()
                        if transcript:
                            print(f"[Deepgram] Transcript: {transcript}")
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
                # Send close signal
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# OpenAI LLM
# ---------------------------------------------------------------------------

class OpenAILLM:
    """Chat completion via OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.conversation: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    async def get_response(self, user_text: str) -> str:
        """Get a text response from OpenAI."""
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
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if "error" in data:
                    print(f"[OpenAI] Error: {data['error']}")
                    return "Sorry, I had trouble thinking of a response."

                reply = data["choices"][0]["message"]["content"].strip()
                self.conversation.append({"role": "assistant", "content": reply})
                print(f"[OpenAI] Response: {reply}")
                return reply


# ---------------------------------------------------------------------------
# ElevenLabs TTS (streaming)
# ---------------------------------------------------------------------------

class ElevenLabsTTS:
    """Text-to-speech via ElevenLabs streaming API.

    Returns PCM16 audio at the requested sample rate.
    """

    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech, return raw PCM16 8kHz audio bytes."""
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            f"?output_format=pcm_16000"
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

        audio_chunks = []
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"[ElevenLabs] Error {resp.status}: {error_text}")
                    return b""

                async for chunk in resp.content.iter_chunked(4096):
                    audio_chunks.append(chunk)

        pcm16_16k = b"".join(audio_chunks)

        # Downsample from 16kHz to 8kHz (simple 2:1 decimation)
        pcm16_8k = self._downsample_16k_to_8k(pcm16_16k)
        print(f"[ElevenLabs] Synthesized {len(pcm16_8k)} bytes of audio")
        return pcm16_8k

    @staticmethod
    def _downsample_16k_to_8k(pcm16_data: bytes) -> bytes:
        """Simple 2:1 downsampling from 16kHz to 8kHz PCM16."""
        n_samples = len(pcm16_data) // 2
        samples = struct.unpack(f"<{n_samples}h", pcm16_data)
        # Take every other sample
        downsampled = samples[::2]
        return struct.pack(f"<{len(downsampled)}h", *downsampled)


# ---------------------------------------------------------------------------
# Voice Bot — the WebSocket server that VoxBridge connects to
# ---------------------------------------------------------------------------

class VoiceBot:
    """WebSocket voice bot server.

    VoxBridge connects to this bot as a client. The bot:
    1. Receives audio + JSON control messages from VoxBridge
    2. Pipes audio to Deepgram for transcription
    3. Sends transcripts to OpenAI for responses
    4. Synthesizes responses with ElevenLabs
    5. Sends audio back to VoxBridge → Twilio → caller
    """

    def __init__(self):
        self.stt = DeepgramSTT(DEEPGRAM_API_KEY)
        self.llm = OpenAILLM(OPENAI_API_KEY, OPENAI_MODEL)
        self.tts = ElevenLabsTTS(ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID)

    async def handle_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle a single call from VoxBridge."""
        print("\n" + "=" * 60)
        print("[Bot] New call connected!")
        print("=" * 60)

        # Connect to Deepgram STT
        await self.stt.connect()

        # Start the response pipeline
        response_task = asyncio.create_task(
            self._response_loop(ws)
        )

        try:
            async for message in ws:
                if isinstance(message, bytes):
                    # Raw audio from VoxBridge (mulaw 8kHz)
                    pcm16 = mulaw_to_pcm16(message)
                    await self.stt.send_audio(pcm16)

                elif isinstance(message, str):
                    # JSON control message
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

                            # Send a greeting
                            await self._speak(ws, "Hello! How can I help you today?")

                        elif msg_type == "stop":
                            print("[Bot] Call ended")
                            break

                        elif msg_type == "dtmf":
                            digit = msg.get("digit", "")
                            print(f"[Bot] DTMF: {digit}")

                        elif msg_type == "barge_in":
                            print("[Bot] Barge-in detected — stopping TTS")

                        elif msg_type == "mark":
                            mark_name = msg.get("name", "")
                            print(f"[Bot] Playback mark reached: {mark_name}")

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
        """Listen for transcripts and generate responses."""
        try:
            while True:
                # Wait for a complete transcript from Deepgram
                transcript = await self.stt.transcript_queue.get()

                if not transcript:
                    continue

                print(f"\n[Bot] Processing: '{transcript}'")

                # Get LLM response
                response_text = await self.llm.get_response(transcript)

                # Synthesize and send audio
                await self._speak(ws, response_text)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Bot] Response loop error: {e}")

    async def _speak(self, ws: WebSocketServerProtocol, text: str) -> None:
        """Synthesize text and send audio to VoxBridge."""
        print(f"[Bot] Speaking: '{text}'")

        # Get TTS audio (PCM16 8kHz)
        pcm16_audio = await self.tts.synthesize(text)
        if not pcm16_audio:
            return

        # Convert to mulaw for Twilio via VoxBridge
        mulaw_audio = pcm16_to_mulaw(pcm16_audio)

        # Send in 20ms chunks (160 bytes at 8kHz mulaw)
        chunk_size = 160
        for i in range(0, len(mulaw_audio), chunk_size):
            chunk = mulaw_audio[i : i + chunk_size]
            try:
                await ws.send(chunk)
            except Exception:
                break
            # Pace the audio to ~real-time to avoid buffer overflow
            await asyncio.sleep(0.018)  # ~20ms per chunk

        # Send end-of-speech marker
        try:
            await ws.send(json.dumps({"type": "end_of_speech"}))
        except Exception:
            pass


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

    print(f"\nAI Voice Bot starting on ws://{BOT_HOST}:{BOT_PORT}/ws")
    print(f"  STT:  Deepgram (streaming)")
    print(f"  LLM:  OpenAI ({OPENAI_MODEL})")
    print(f"  TTS:  ElevenLabs (voice: {ELEVENLABS_VOICE_ID})")
    print(f"\nWaiting for VoxBridge to connect...\n")

    async with websockets.serve(bot.handle_connection, BOT_HOST, BOT_PORT, ping_interval=20):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
