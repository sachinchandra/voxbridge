"""Turn detection for the AI pipeline.

Determines when the user has finished speaking and the LLM should respond.
Uses a combination of STT endpointing (final results) and silence-based
timing to decide turn boundaries.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from loguru import logger

from voxbridge.providers.base import STTResult


@dataclass
class TurnDetector:
    """Detects when the user has finished a conversational turn.

    Combines STT final results with silence timing to determine when
    the user is done speaking. This triggers the LLM to generate a response.

    The detector tracks:
    - STT final results (endpointed by the STT provider)
    - Silence duration after the last speech
    - Accumulated transcript text for the current turn

    Args:
        silence_threshold_ms: Silence after last speech to trigger turn end (default: 700ms).
        min_turn_length: Minimum characters of speech before allowing turn end (default: 2).
        max_turn_duration_ms: Maximum duration of a single turn (default: 30000ms).
        endpointing_mode: "stt" (rely on STT) or "silence" (use silence timer) (default: "stt").
    """

    silence_threshold_ms: float = 700.0
    min_turn_length: int = 2
    max_turn_duration_ms: float = 30000.0
    endpointing_mode: str = "stt"  # "stt" or "silence"

    # Internal state
    _current_transcript: str = ""
    _interim_transcript: str = ""
    _last_speech_time: float = 0.0
    _turn_start_time: float = 0.0
    _is_speaking: bool = False
    _turn_ended: bool = False
    _silence_task: asyncio.Task | None = field(default=None, repr=False)
    _on_turn_end: Callable[[str], Awaitable[None]] | None = field(
        default=None, repr=False
    )

    def set_turn_end_callback(
        self, callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Set the callback that fires when a turn ends.

        Args:
            callback: Async function receiving the complete turn transcript.
        """
        self._on_turn_end = callback

    async def on_stt_result(self, result: STTResult) -> None:
        """Process an STT result and check for turn end.

        Args:
            result: An STTResult from the STT provider.
        """
        now = time.time()

        if not result.text and result.is_final:
            # Empty final result = utterance end from STT (Deepgram UtteranceEnd)
            if self._current_transcript.strip():
                await self._end_turn()
            return

        if result.text:
            self._last_speech_time = now

            if not self._is_speaking:
                self._is_speaking = True
                self._turn_start_time = now
                self._turn_ended = False
                logger.debug("Turn started")

            if result.is_final:
                # Append final text to transcript
                if self._current_transcript:
                    self._current_transcript += " " + result.text
                else:
                    self._current_transcript = result.text
                self._interim_transcript = ""

                if self.endpointing_mode == "stt":
                    # STT provider says this is final — start silence timer
                    self._start_silence_timer()

            else:
                # Interim result — update but don't commit
                self._interim_transcript = result.text

        # Check max turn duration
        if (
            self._is_speaking
            and (now - self._turn_start_time) * 1000 > self.max_turn_duration_ms
        ):
            logger.warning("Max turn duration reached, forcing turn end")
            await self._end_turn()

    def _start_silence_timer(self) -> None:
        """Start (or restart) the silence timer."""
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()
        self._silence_task = asyncio.create_task(self._silence_watcher())

    async def _silence_watcher(self) -> None:
        """Wait for silence threshold, then end the turn."""
        try:
            await asyncio.sleep(self.silence_threshold_ms / 1000.0)

            # Check if we actually had enough silence
            elapsed_ms = (time.time() - self._last_speech_time) * 1000
            if elapsed_ms >= self.silence_threshold_ms * 0.8:
                await self._end_turn()
        except asyncio.CancelledError:
            pass

    async def _end_turn(self) -> None:
        """End the current turn and fire the callback."""
        if self._turn_ended:
            return

        self._turn_ended = True
        self._is_speaking = False

        # Include any pending interim text
        transcript = self._current_transcript
        if self._interim_transcript:
            if transcript:
                transcript += " " + self._interim_transcript
            else:
                transcript = self._interim_transcript

        transcript = transcript.strip()

        if len(transcript) < self.min_turn_length:
            logger.debug(f"Turn too short ({len(transcript)} chars), ignoring")
            self.reset()
            return

        logger.info(f"Turn ended: '{transcript[:80]}{'...' if len(transcript) > 80 else ''}'")

        # Reset state before callback (callback may take time)
        self.reset()

        if self._on_turn_end:
            await self._on_turn_end(transcript)

    def reset(self) -> None:
        """Reset state for a new turn."""
        self._current_transcript = ""
        self._interim_transcript = ""
        self._is_speaking = False
        self._turn_ended = False
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()
            self._silence_task = None

    def cancel(self) -> None:
        """Cancel any pending turn detection (e.g., on barge-in)."""
        self.reset()
        logger.debug("Turn detection cancelled")

    @property
    def current_text(self) -> str:
        """Get the current accumulated transcript text."""
        text = self._current_transcript
        if self._interim_transcript:
            if text:
                text += " " + self._interim_transcript
            else:
                text = self._interim_transcript
        return text.strip()

    @property
    def is_speaking(self) -> bool:
        """Whether the user is currently speaking."""
        return self._is_speaking
