"""Call session management for VoxBridge.

Each active call gets a CallSession that tracks its state, connections,
codec pipeline, and metadata. The SessionStore manages all active sessions.
"""

from __future__ import annotations

import asyncio
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from voxbridge.audio.codecs import CodecRegistry, codec_registry
from voxbridge.audio.resampler import Resampler
from voxbridge.core.events import Codec
from voxbridge.serializers.base import BaseSerializer
from voxbridge.transports.base import BaseTransport


# ---------------------------------------------------------------------------
# Audio energy helpers for barge-in VAD
# ---------------------------------------------------------------------------

# mu-law decode table (for fast RMS without full codec decode)
_MULAW_DECODE_TABLE: list[int] = []
for _i in range(256):
    _v = ~_i & 0xFF
    _sign = _v & 0x80
    _exp = (_v >> 4) & 0x07
    _mant = _v & 0x0F
    _t = (_mant << 3) + 0x84
    _t <<= _exp
    _sample = _t - 0x84
    if _sign:
        _sample = -_sample
    _MULAW_DECODE_TABLE.append(_sample)


def compute_audio_energy(data: bytes, codec: str = "mulaw") -> float:
    """Compute RMS energy of an audio frame.

    Args:
        data: Raw audio bytes.
        codec: "mulaw", "alaw", or "pcm16".

    Returns:
        RMS energy as a float (0.0 = silence, ~32768.0 = max).
    """
    if not data:
        return 0.0

    if codec == "mulaw":
        # Fast path: use lookup table directly
        total = 0
        for b in data:
            s = _MULAW_DECODE_TABLE[b]
            total += s * s
        rms = (total / len(data)) ** 0.5
        return rms
    elif codec == "pcm16":
        n_samples = len(data) // 2
        if n_samples == 0:
            return 0.0
        samples = struct.unpack(f"<{n_samples}h", data)
        total = sum(s * s for s in samples)
        return (total / n_samples) ** 0.5
    else:
        # For alaw or unknown, fall back to treating as pcm16
        n_samples = len(data) // 2
        if n_samples == 0:
            return 0.0
        samples = struct.unpack(f"<{n_samples}h", data)
        total = sum(s * s for s in samples)
        return (total / n_samples) ** 0.5


@dataclass
class BargeInDetector:
    """Energy-based Voice Activity Detector for barge-in detection.

    Prevents false barge-in triggers from silence/background noise by
    requiring the caller's audio energy to exceed a threshold for a
    minimum number of consecutive frames before signalling barge-in.

    Attributes:
        energy_threshold: RMS energy threshold to consider "speech" (0-32768).
            Default 200 works well for typical telephony. Lower = more sensitive.
        min_speech_frames: Number of consecutive above-threshold frames
            required before triggering barge-in. Default 3 (~60ms at 20ms/frame).
            Higher = less sensitive / fewer false positives.
        codec: Audio codec of incoming frames ("mulaw", "pcm16", "alaw").
    """

    energy_threshold: float = 200.0
    min_speech_frames: int = 3
    codec: str = "mulaw"
    _consecutive_speech_frames: int = 0
    _triggered: bool = False

    def check(self, audio_data: bytes) -> bool:
        """Check an audio frame for speech. Returns True if barge-in detected.

        The detector requires `min_speech_frames` consecutive frames above
        the energy threshold before returning True. After triggering, it
        returns False until reset() is called.
        """
        if self._triggered:
            return False

        energy = compute_audio_energy(audio_data, self.codec)

        if energy >= self.energy_threshold:
            self._consecutive_speech_frames += 1
            if self._consecutive_speech_frames >= self.min_speech_frames:
                self._triggered = True
                logger.debug(
                    f"Barge-in VAD triggered: energy={energy:.0f} "
                    f"(threshold={self.energy_threshold}), "
                    f"frames={self._consecutive_speech_frames}"
                )
                return True
        else:
            # Reset counter on silence frame
            self._consecutive_speech_frames = 0

        return False

    def reset(self) -> None:
        """Reset the detector for a new speaking turn."""
        self._consecutive_speech_frames = 0
        self._triggered = False


@dataclass
class CallSession:
    """Represents a single active call flowing through the bridge.

    Each call has:
    - A provider-side transport + serializer
    - A bot-side transport
    - A codec pipeline for audio conversion
    - Metadata from the telephony provider
    """

    # Unique session identifier
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Call identifier from the provider
    call_id: str = ""

    # Transports
    provider_transport: BaseTransport | None = None
    bot_transport: BaseTransport | None = None

    # Serializer for the provider's protocol
    provider_serializer: BaseSerializer | None = None

    # Codec conversion
    codec_registry: CodecRegistry = field(default_factory=lambda: codec_registry)

    # Resamplers (created lazily)
    _inbound_resampler: Resampler | None = None
    _outbound_resampler: Resampler | None = None

    # Call metadata
    from_number: str = ""
    to_number: str = ""
    provider: str = ""
    direction: str = "inbound"
    metadata: dict[str, Any] = field(default_factory=dict)

    # State
    is_active: bool = True
    is_on_hold: bool = False
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None

    # Barge-in / interruption state
    is_bot_speaking: bool = False
    barge_in_enabled: bool = True
    _outbound_audio_queue: asyncio.Queue | None = None
    _pending_marks: list[str] = field(default_factory=list)

    # Barge-in VAD
    barge_in_detector: BargeInDetector = field(default_factory=BargeInDetector)

    # Custom SIP headers (passed from provider → bot)
    sip_headers: dict[str, str] = field(default_factory=dict)

    # SaaS tracking
    api_key_id: str = ""
    audio_bytes_in: int = 0
    audio_bytes_out: int = 0

    # Asyncio tasks for the bidirectional loops
    _tasks: list[asyncio.Task] = field(default_factory=list)

    @property
    def outbound_audio_queue(self) -> asyncio.Queue:
        """Lazy-init the outbound audio queue."""
        if self._outbound_audio_queue is None:
            self._outbound_audio_queue = asyncio.Queue(maxsize=500)
        return self._outbound_audio_queue

    def clear_outbound_audio(self) -> int:
        """Flush all queued outbound audio. Returns number of chunks cleared."""
        cleared = 0
        if self._outbound_audio_queue:
            while not self._outbound_audio_queue.empty():
                try:
                    self._outbound_audio_queue.get_nowait()
                    cleared += 1
                except asyncio.QueueEmpty:
                    break
        self.is_bot_speaking = False
        return cleared

    def setup_resamplers(
        self,
        provider_rate: int,
        bot_rate: int,
    ) -> None:
        """Configure resamplers for the audio pipeline.

        Args:
            provider_rate: Sample rate from the provider (e.g., 8000).
            bot_rate: Sample rate expected by the bot (e.g., 16000).
        """
        if provider_rate != bot_rate:
            self._inbound_resampler = Resampler(provider_rate, bot_rate)
            self._outbound_resampler = Resampler(bot_rate, provider_rate)

    def convert_inbound_audio(self, data: bytes, from_codec: Codec, to_codec: Codec) -> bytes:
        """Convert audio from provider codec/rate to bot codec/rate."""
        # Codec conversion
        converted = self.codec_registry.convert(data, from_codec, to_codec)
        # Resample if needed
        if self._inbound_resampler:
            converted = self._inbound_resampler.process(converted)
        return converted

    def convert_outbound_audio(self, data: bytes, from_codec: Codec, to_codec: Codec) -> bytes:
        """Convert audio from bot codec/rate to provider codec/rate."""
        # Resample first (before encoding to the provider's codec)
        if self._outbound_resampler:
            data = self._outbound_resampler.process(data)
        # Codec conversion
        return self.codec_registry.convert(data, from_codec, to_codec)

    def end(self) -> None:
        """Mark the session as ended and cancel tasks."""
        self.is_active = False
        self.ended_at = time.time()
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()

    @property
    def duration_ms(self) -> int:
        """Call duration in milliseconds."""
        end = self.ended_at or time.time()
        return int((end - self.started_at) * 1000)


class SessionStore:
    """Thread-safe store for active call sessions.

    Provides lookup by session_id or call_id, and automatic cleanup
    of ended sessions.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, CallSession] = {}
        self._call_id_map: dict[str, str] = {}  # call_id -> session_id

    def create(self, **kwargs) -> CallSession:
        """Create and store a new session."""
        session = CallSession(**kwargs)
        self._sessions[session.session_id] = session
        if session.call_id:
            self._call_id_map[session.call_id] = session.session_id
        logger.info(f"Session created: {session.session_id} (call: {session.call_id})")
        return session

    def get(self, session_id: str) -> CallSession | None:
        """Get a session by session_id."""
        return self._sessions.get(session_id)

    def get_by_call_id(self, call_id: str) -> CallSession | None:
        """Get a session by call_id."""
        session_id = self._call_id_map.get(call_id)
        if session_id:
            return self._sessions.get(session_id)
        return None

    def remove(self, session_id: str) -> None:
        """Remove a session from the store."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.end()
            self._call_id_map.pop(session.call_id, None)
            logger.info(
                f"Session removed: {session.session_id} "
                f"(duration: {session.duration_ms}ms)"
            )

    @property
    def active_count(self) -> int:
        """Number of active sessions."""
        return sum(1 for s in self._sessions.values() if s.is_active)

    @property
    def all_sessions(self) -> list[CallSession]:
        """All sessions (active and ended)."""
        return list(self._sessions.values())

    def cleanup(self) -> int:
        """Remove all ended sessions. Returns count removed."""
        ended = [sid for sid, s in self._sessions.items() if not s.is_active]
        for sid in ended:
            self.remove(sid)
        return len(ended)
