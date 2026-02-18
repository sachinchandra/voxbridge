"""Pipeline Orchestrator — real-time STT -> LLM -> TTS streaming loop.

This is the heart of VoxBridge's built-in AI pipeline. It replaces the
external bot WebSocket with an internal processing chain that:

1. Receives audio from the telephony provider (via the bridge)
2. Streams it to an STT provider for real-time transcription
3. Detects turn boundaries (when the user stops speaking)
4. Sends the transcript to an LLM for response generation
5. Streams LLM output to a TTS provider sentence-by-sentence
6. Sends synthesized audio back through the bridge to the caller

The orchestrator handles barge-in (caller interrupts), escalation to
human agents, function/tool calling, and conversation context management.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from loguru import logger

from voxbridge.providers.base import (
    BaseLLM,
    BaseSTT,
    BaseTTS,
    LLMChunk,
    LLMToolCall,
    Message,
    STTResult,
    TTSChunk,
)
from voxbridge.providers.registry import provider_registry
from voxbridge.pipeline.context import ConversationContext
from voxbridge.pipeline.escalation import EscalationDetector, EscalationResult
from voxbridge.pipeline.turn_detector import TurnDetector


@dataclass
class PipelineConfig:
    """Configuration for the AI pipeline.

    Typically derived from the Agent's configuration in the database.

    Args:
        stt_provider: STT provider name (e.g., "deepgram").
        stt_config: STT provider kwargs (api_key, model, etc.).
        llm_provider: LLM provider name (e.g., "openai", "anthropic").
        llm_config: LLM provider kwargs (api_key, model, etc.).
        tts_provider: TTS provider name (e.g., "elevenlabs").
        tts_config: TTS provider kwargs (api_key, voice_id, etc.).
        system_prompt: The agent's system prompt.
        first_message: Optional greeting message.
        tools: Tool/function definitions.
        escalation_config: Escalation detection settings.
        max_call_duration_seconds: Maximum call duration (default: 1800 = 30min).
        llm_temperature: LLM temperature (default: 0.7).
        llm_max_tokens: LLM max tokens per response (default: 512).
        silence_threshold_ms: Silence for turn detection (default: 700ms).
        interruption_enabled: Whether barge-in is enabled (default: True).
    """

    stt_provider: str = "deepgram"
    stt_config: dict[str, Any] = field(default_factory=dict)
    llm_provider: str = "openai"
    llm_config: dict[str, Any] = field(default_factory=dict)
    tts_provider: str = "elevenlabs"
    tts_config: dict[str, Any] = field(default_factory=dict)

    system_prompt: str = "You are a helpful AI assistant on a phone call. Be concise and conversational."
    first_message: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)

    escalation_enabled: bool = True
    escalation_config: dict[str, Any] = field(default_factory=dict)

    max_call_duration_seconds: int = 1800
    llm_temperature: float = 0.7
    llm_max_tokens: int = 512
    silence_threshold_ms: float = 700.0
    interruption_enabled: bool = True

    end_call_phrases: list[str] = field(default_factory=lambda: [
        "goodbye",
        "bye bye",
        "end the call",
        "hang up",
    ])


# Type for tool execution callback
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]


class PipelineOrchestrator:
    """Real-time STT -> LLM -> TTS pipeline orchestrator.

    Manages the full audio processing pipeline for a single call.
    Each call gets its own PipelineOrchestrator instance.

    The orchestrator:
    - Creates and manages STT, LLM, and TTS provider instances
    - Runs the STT listener and turn detector
    - Processes user turns through the LLM
    - Streams LLM responses through TTS
    - Handles barge-in, escalation, and tool calling
    - Sends audio back through a callback to the bridge

    Usage:
        pipeline = PipelineOrchestrator(config)
        pipeline.set_audio_output_callback(send_audio_to_provider)
        pipeline.set_tool_executor(execute_tool)
        await pipeline.start()
        # Feed audio chunks:
        await pipeline.feed_audio(audio_bytes)
        # On barge-in:
        await pipeline.handle_barge_in()
        # Cleanup:
        await pipeline.stop()
    """

    def __init__(self, config: PipelineConfig):
        self.config = config

        # Provider instances (created on start)
        self._stt: BaseSTT | None = None
        self._llm: BaseLLM | None = None
        self._tts: BaseTTS | None = None

        # Pipeline components
        self._turn_detector = TurnDetector(
            silence_threshold_ms=config.silence_threshold_ms,
        )
        self._context = ConversationContext(
            system_prompt=config.system_prompt,
            first_message=config.first_message,
            tools=config.tools,
        )
        self._escalation = EscalationDetector(
            enabled=config.escalation_enabled,
            **config.escalation_config,
        )

        # Callbacks
        self._audio_output_cb: Callable[[bytes], Awaitable[None]] | None = None
        self._tool_executor: ToolExecutor | None = None
        self._on_escalation: Callable[[EscalationResult], Awaitable[None]] | None = None
        self._on_call_end: Callable[[str], Awaitable[None]] | None = None
        self._on_transcript: Callable[[str, str], Awaitable[None]] | None = None

        # State
        self._running = False
        self._is_speaking = False  # Whether TTS is playing
        self._stt_task: asyncio.Task | None = None
        self._generation_task: asyncio.Task | None = None
        self._start_time: float = 0.0

        # Sentence buffer for TTS
        self._sentence_buffer = ""

    # ------------------------------------------------------------------
    # Configuration callbacks
    # ------------------------------------------------------------------

    def set_audio_output_callback(
        self, callback: Callable[[bytes], Awaitable[None]]
    ) -> None:
        """Set the callback for sending audio back to the provider.

        Args:
            callback: Async function that accepts raw audio bytes (PCM16).
        """
        self._audio_output_cb = callback

    def set_tool_executor(self, executor: ToolExecutor) -> None:
        """Set the function that executes tool calls.

        Args:
            executor: Async function(name, arguments) -> result.
        """
        self._tool_executor = executor

    def set_escalation_callback(
        self, callback: Callable[[EscalationResult], Awaitable[None]]
    ) -> None:
        """Set the callback for escalation events."""
        self._on_escalation = callback

    def set_call_end_callback(
        self, callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Set the callback for call end events."""
        self._on_call_end = callback

    def set_transcript_callback(
        self, callback: Callable[[str, str], Awaitable[None]]
    ) -> None:
        """Set callback for transcript events (role, text)."""
        self._on_transcript = callback

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize providers and start the pipeline.

        Creates STT, LLM, and TTS provider instances, connects them,
        and starts the STT listener task.
        """
        logger.info("Pipeline starting...")
        self._start_time = time.time()

        # Create providers
        self._stt = provider_registry.create_stt(
            self.config.stt_provider, **self.config.stt_config
        )
        self._llm = provider_registry.create_llm(
            self.config.llm_provider, **self.config.llm_config
        )
        self._tts = provider_registry.create_tts(
            self.config.tts_provider, **self.config.tts_config
        )

        # Connect streaming providers
        await self._stt.connect()
        await self._tts.connect()

        # Set up turn detection callback
        self._turn_detector.set_turn_end_callback(self._on_turn_end)

        # Start STT result listener
        self._stt_task = asyncio.create_task(self._stt_listener())
        self._running = True

        # Send first message greeting if configured
        if self.config.first_message:
            await self._synthesize_and_send(self.config.first_message)
            if self._on_transcript:
                await self._on_transcript("assistant", self.config.first_message)

        logger.info(
            f"Pipeline started: STT={self.config.stt_provider}, "
            f"LLM={self.config.llm_provider}, TTS={self.config.tts_provider}"
        )

    async def stop(self) -> None:
        """Stop the pipeline and clean up all providers."""
        logger.info("Pipeline stopping...")
        self._running = False

        # Cancel running tasks
        if self._stt_task and not self._stt_task.done():
            self._stt_task.cancel()
            try:
                await self._stt_task
            except asyncio.CancelledError:
                pass

        if self._generation_task and not self._generation_task.done():
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                pass

        # Close providers
        if self._stt:
            await self._stt.close()
        if self._llm:
            await self._llm.close()
        if self._tts:
            await self._tts.close()

        logger.info(
            f"Pipeline stopped. "
            f"Duration: {time.time() - self._start_time:.1f}s, "
            f"Tokens: {self._context.total_tokens}, "
            f"Turns: {self._escalation.turn_count}"
        )

    # ------------------------------------------------------------------
    # Audio input
    # ------------------------------------------------------------------

    async def feed_audio(self, audio: bytes) -> None:
        """Feed an audio chunk from the provider into the pipeline.

        The audio should be PCM16 at the STT provider's expected sample rate.

        Args:
            audio: Raw PCM16 audio bytes.
        """
        if self._stt and self._running:
            await self._stt.send_audio(audio)

    # ------------------------------------------------------------------
    # Barge-in handling
    # ------------------------------------------------------------------

    async def handle_barge_in(self) -> None:
        """Handle a barge-in event (caller interrupted TTS playback).

        Cancels the current LLM generation and TTS synthesis,
        resets the turn detector, and prepares for new input.
        """
        logger.info("Pipeline: handling barge-in")
        self._is_speaking = False

        # Cancel ongoing generation
        if self._generation_task and not self._generation_task.done():
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                pass
            self._generation_task = None

        # Reset turn detector for new input
        self._turn_detector.reset()
        self._sentence_buffer = ""

    # ------------------------------------------------------------------
    # DTMF handling
    # ------------------------------------------------------------------

    async def handle_dtmf(self, digit: str) -> None:
        """Handle a DTMF digit press.

        Checks for escalation triggers (digit "0") and otherwise
        includes the DTMF info in the conversation.

        Args:
            digit: The DTMF digit pressed ("0"-"9", "*", "#").
        """
        # Check escalation
        result = self._escalation.check_dtmf(digit)
        if result.should_escalate:
            await self._handle_escalation(result)
            return

        # Add DTMF context to conversation
        self._context.add_user_message(f"[DTMF tone pressed: {digit}]")

    # ------------------------------------------------------------------
    # Internal: STT listener
    # ------------------------------------------------------------------

    async def _stt_listener(self) -> None:
        """Background task that processes STT results."""
        try:
            async for result in self._stt.results():
                if not self._running:
                    break

                # Feed to turn detector
                await self._turn_detector.on_stt_result(result)

                # Check call duration limit
                elapsed = time.time() - self._start_time
                if elapsed > self.config.max_call_duration_seconds:
                    logger.warning("Max call duration reached")
                    await self._end_call("max_duration")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"STT listener error: {e}")

    # ------------------------------------------------------------------
    # Internal: Turn processing (LLM + TTS)
    # ------------------------------------------------------------------

    async def _on_turn_end(self, transcript: str) -> None:
        """Called by TurnDetector when the user finishes speaking.

        Triggers the LLM generation and TTS synthesis pipeline.

        Args:
            transcript: The complete user turn transcript.
        """
        if not self._running:
            return

        logger.info(f"Processing turn: '{transcript[:80]}'")

        # Add to conversation context
        self._context.add_user_message(transcript)

        # Notify transcript callback
        if self._on_transcript:
            await self._on_transcript("user", transcript)

        # Check for escalation
        esc_result = self._escalation.check_user_message(transcript)
        if esc_result.should_escalate:
            await self._handle_escalation(esc_result)
            return

        # Check for end-call phrases
        transcript_lower = transcript.lower()
        for phrase in self.config.end_call_phrases:
            if phrase.lower() in transcript_lower:
                # Let the LLM say goodbye first
                goodbye_prompt = (
                    f"The caller said: '{transcript}'. "
                    "Say a brief, polite goodbye and end the conversation."
                )
                self._context._messages[-1] = Message(
                    role="user", content=goodbye_prompt
                )
                await self._generate_and_speak()
                await self._end_call("caller_goodbye")
                return

        # Start LLM generation (cancel any in-progress generation)
        if self._generation_task and not self._generation_task.done():
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                pass

        self._generation_task = asyncio.create_task(self._generate_and_speak())

    async def _generate_and_speak(self) -> None:
        """Generate an LLM response and synthesize it to speech.

        This is the core pipeline loop:
        1. Stream tokens from the LLM
        2. Buffer into sentences
        3. Send each sentence to TTS
        4. Send TTS audio to the provider
        """
        if not self._llm or not self._tts:
            return

        self._is_speaking = True
        full_response = ""
        pending_tool_calls: dict[str, dict[str, str]] = {}

        try:
            messages = self._context.get_messages()
            tools = self._context.get_tools()

            async for chunk in self._llm.generate(
                messages=messages,
                tools=tools,
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            ):
                if not self._running or not self._is_speaking:
                    break

                # Handle text content
                if chunk.text:
                    full_response += chunk.text
                    self._sentence_buffer += chunk.text

                    # Try to extract complete sentences for TTS
                    sentences = self._extract_sentences(self._sentence_buffer)
                    if sentences:
                        for sentence in sentences[:-1]:
                            await self._synthesize_and_send(sentence)
                        self._sentence_buffer = sentences[-1]

                # Handle tool calls
                if chunk.tool_call_id:
                    tc_id = chunk.tool_call_id
                    if tc_id not in pending_tool_calls:
                        pending_tool_calls[tc_id] = {
                            "name": "",
                            "arguments": "",
                        }
                    if chunk.tool_name:
                        pending_tool_calls[tc_id]["name"] = chunk.tool_name
                    if chunk.tool_arguments:
                        pending_tool_calls[tc_id]["arguments"] = chunk.tool_arguments

                # Handle usage tracking
                if chunk.is_final:
                    self._context.update_token_usage(
                        chunk.input_tokens, chunk.output_tokens
                    )

            # Flush remaining sentence buffer
            if self._sentence_buffer.strip() and self._is_speaking:
                await self._synthesize_and_send(self._sentence_buffer.strip())
                self._sentence_buffer = ""

            # Handle tool calls
            if pending_tool_calls:
                await self._handle_tool_calls(full_response, pending_tool_calls)
                return

            # Add assistant response to context
            if full_response.strip():
                self._context.add_assistant_message(full_response)
                if self._on_transcript:
                    await self._on_transcript("assistant", full_response)

        except asyncio.CancelledError:
            # Barge-in or stop — save partial response
            if full_response.strip():
                self._context.add_assistant_message(
                    full_response + " [interrupted]"
                )
            raise
        except Exception as e:
            logger.error(f"Generation error: {e}")
            # Try to say an error message
            await self._synthesize_and_send(
                "I'm sorry, I had a brief issue. Could you repeat that?"
            )
        finally:
            self._is_speaking = False
            self._sentence_buffer = ""

    # ------------------------------------------------------------------
    # Internal: TTS output
    # ------------------------------------------------------------------

    async def _synthesize_and_send(self, text: str) -> None:
        """Synthesize text to speech and send audio chunks to provider.

        Args:
            text: The text to synthesize and play.
        """
        if not self._tts or not self._audio_output_cb or not text.strip():
            return

        try:
            async for chunk in self._tts.synthesize(text):
                if not self._is_speaking and not self.config.first_message:
                    break
                if chunk.audio:
                    await self._audio_output_cb(chunk.audio)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")

    # ------------------------------------------------------------------
    # Internal: Tool calling
    # ------------------------------------------------------------------

    async def _handle_tool_calls(
        self,
        assistant_text: str,
        tool_calls: dict[str, dict[str, str]],
    ) -> None:
        """Execute tool calls and feed results back to the LLM.

        Args:
            assistant_text: Any text the assistant generated before tool calls.
            tool_calls: Map of tool_call_id -> {name, arguments}.
        """
        # Build LLMToolCall objects
        llm_tool_calls = []
        for tc_id, tc_data in tool_calls.items():
            try:
                args = json.loads(tc_data["arguments"])
            except json.JSONDecodeError:
                args = {}
            llm_tool_calls.append(
                LLMToolCall(id=tc_id, name=tc_data["name"], arguments=args)
            )

        # Add assistant message with tool calls to context
        self._context.add_assistant_tool_calls(assistant_text, llm_tool_calls)

        # If we have a filler message, say it while tools execute
        if assistant_text.strip():
            await self._synthesize_and_send(assistant_text)

        # Execute each tool
        for tc in llm_tool_calls:
            logger.info(f"Executing tool: {tc.name}({tc.arguments})")

            if self._tool_executor:
                try:
                    result = await self._tool_executor(tc.name, tc.arguments)
                    self._context.add_tool_result(tc.id, tc.name, result)
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    self._context.add_tool_result(
                        tc.id, tc.name, f"Error: {str(e)}"
                    )
            else:
                self._context.add_tool_result(
                    tc.id, tc.name, "Tool execution not configured"
                )

        # Generate follow-up response with tool results
        if self._running:
            await self._generate_and_speak()

    # ------------------------------------------------------------------
    # Internal: Escalation
    # ------------------------------------------------------------------

    async def _handle_escalation(self, result: EscalationResult) -> None:
        """Handle an escalation event.

        Says the transfer message and notifies the bridge.

        Args:
            result: The escalation detection result.
        """
        logger.info(f"Escalation: {result.reason}")

        # Say transfer message
        transfer_msg = self._escalation.transfer_message
        await self._synthesize_and_send(transfer_msg)

        # Notify callback
        if self._on_escalation:
            await self._on_escalation(result)

    async def _end_call(self, reason: str) -> None:
        """End the call through the callback.

        Args:
            reason: Reason for ending the call.
        """
        logger.info(f"Pipeline ending call: {reason}")
        if self._on_call_end:
            await self._on_call_end(reason)

    # ------------------------------------------------------------------
    # Internal: Sentence splitting
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sentences(text: str) -> list[str]:
        """Split text into sentences for TTS.

        Returns a list where the last element may be an incomplete sentence.
        Complete sentences end with sentence-ending punctuation.
        """
        if not text:
            return []

        # Split on sentence boundaries
        # Match: period, exclamation, question mark, colon, semicolon
        # followed by a space or end of string
        parts = re.split(r'(?<=[.!?;:])\s+', text)

        if not parts:
            return [text]

        return parts

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Whether the pipeline is currently running."""
        return self._running

    @property
    def is_speaking(self) -> bool:
        """Whether TTS is currently playing audio."""
        return self._is_speaking

    @property
    def context(self) -> ConversationContext:
        """Access the conversation context."""
        return self._context

    @property
    def duration_seconds(self) -> float:
        """Pipeline duration in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return 0.0
