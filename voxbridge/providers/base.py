"""Base interfaces for AI providers (STT, LLM, TTS).

All provider implementations inherit from these abstract base classes,
ensuring a consistent interface that the pipeline orchestrator can use
regardless of the underlying service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


# ---------------------------------------------------------------------------
# Data classes for provider communication
# ---------------------------------------------------------------------------

@dataclass
class STTResult:
    """A speech-to-text transcription result."""

    text: str
    is_final: bool = False
    confidence: float = 0.0
    language: str = ""
    # Word-level timestamps (optional)
    words: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LLMChunk:
    """A streaming chunk from an LLM response."""

    text: str = ""
    # Function/tool call data
    tool_call_id: str = ""
    tool_name: str = ""
    tool_arguments: str = ""  # Accumulated JSON string
    # End of response flag
    is_final: bool = False
    # Usage info (only on final chunk)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMToolCall:
    """A completed function/tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TTSChunk:
    """A chunk of synthesized audio from a TTS provider."""

    audio: bytes  # Raw audio bytes (PCM16 or provider-specific)
    sample_rate: int = 24000
    is_final: bool = False


@dataclass
class Message:
    """A conversation message for the LLM."""

    role: str  # "system", "user", "assistant", "tool"
    content: str = ""
    tool_call_id: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    name: str = ""  # For tool results


# ---------------------------------------------------------------------------
# Abstract Base Classes
# ---------------------------------------------------------------------------

class BaseSTT(ABC):
    """Abstract base class for Speech-to-Text providers.

    STT providers convert audio streams to text transcriptions.
    They support streaming input (audio chunks) and streaming output
    (partial/final transcription results).

    Lifecycle:
        1. __init__(api_key, **config) — configure the provider
        2. connect() — open a streaming connection
        3. send_audio(chunk) — feed audio chunks
        4. results() — async iterator of STTResult objects
        5. close() — tear down the connection
    """

    @abstractmethod
    async def connect(self) -> None:
        """Open a streaming connection to the STT service."""
        ...

    @abstractmethod
    async def send_audio(self, audio: bytes) -> None:
        """Send an audio chunk to the STT stream.

        Args:
            audio: Raw audio bytes (PCM16 at the configured sample rate).
        """
        ...

    @abstractmethod
    async def results(self) -> AsyncIterator[STTResult]:
        """Yield transcription results as they arrive.

        Yields partial (is_final=False) and final (is_final=True) results.
        The iterator ends when the connection is closed.
        """
        ...
        yield  # pragma: no cover

    @abstractmethod
    async def close(self) -> None:
        """Close the STT connection and release resources."""
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Expected input audio sample rate (e.g., 16000)."""
        ...

    @property
    @abstractmethod
    def codec(self) -> str:
        """Expected input audio codec (e.g., 'pcm16', 'mulaw')."""
        ...

    @property
    def name(self) -> str:
        """Provider name for logging."""
        return self.__class__.__name__


class BaseLLM(ABC):
    """Abstract base class for Large Language Model providers.

    LLM providers process conversation messages and generate streaming
    text responses, optionally with function/tool calls.

    Lifecycle:
        1. __init__(api_key, model, **config) — configure the provider
        2. generate(messages, tools?) — async iterator of LLMChunk objects
        3. close() — clean up any persistent connections
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMChunk]:
        """Generate a streaming response from the LLM.

        Args:
            messages: Conversation history as Message objects.
            tools: Optional list of tool/function definitions in
                   OpenAI-compatible format.
            temperature: Sampling temperature (0.0 - 2.0).
            max_tokens: Maximum tokens to generate.

        Yields:
            LLMChunk objects with streaming text and/or tool call data.
            The final chunk has is_final=True with usage info.
        """
        ...
        yield  # pragma: no cover

    async def close(self) -> None:
        """Clean up any persistent connections. Override if needed."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """The model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')."""
        ...

    @property
    def name(self) -> str:
        """Provider name for logging."""
        return self.__class__.__name__

    @property
    def supports_tools(self) -> bool:
        """Whether this LLM supports function/tool calling."""
        return True


class BaseTTS(ABC):
    """Abstract base class for Text-to-Speech providers.

    TTS providers convert text to audio streams. They support streaming
    input (text chunks/sentences) and streaming output (audio chunks).

    Lifecycle:
        1. __init__(api_key, voice_id, **config) — configure the provider
        2. connect() — open a streaming connection (if applicable)
        3. synthesize(text) — async iterator of TTSChunk objects
        4. close() — tear down the connection
    """

    @abstractmethod
    async def connect(self) -> None:
        """Open a connection to the TTS service. Called once per session."""
        ...

    @abstractmethod
    async def synthesize(self, text: str) -> AsyncIterator[TTSChunk]:
        """Synthesize text to audio, streaming chunks as they're ready.

        Args:
            text: The text to synthesize. Best results with complete sentences.

        Yields:
            TTSChunk objects containing audio bytes and metadata.
        """
        ...
        yield  # pragma: no cover

    @abstractmethod
    async def close(self) -> None:
        """Close the TTS connection and release resources."""
        ...

    @abstractmethod
    async def flush(self) -> AsyncIterator[TTSChunk]:
        """Flush any buffered audio. Called at end of an utterance.

        Yields:
            Any remaining TTSChunk objects.
        """
        ...
        yield  # pragma: no cover

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output audio sample rate (e.g., 24000, 22050)."""
        ...

    @property
    @abstractmethod
    def codec(self) -> str:
        """Output audio codec (e.g., 'pcm16')."""
        ...

    @property
    def name(self) -> str:
        """Provider name for logging."""
        return self.__class__.__name__
