"""Call session management for VoxBridge.

Each active call gets a CallSession that tracks its state, connections,
codec pipeline, and metadata. The SessionStore manages all active sessions.
"""

from __future__ import annotations

import asyncio
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

    # Asyncio tasks for the bidirectional loops
    _tasks: list[asyncio.Task] = field(default_factory=list)

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
