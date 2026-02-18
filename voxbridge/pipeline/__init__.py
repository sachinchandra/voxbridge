"""VoxBridge AI Pipeline - Real-time STT -> LLM -> TTS processing.

The pipeline replaces the external bot WebSocket with a built-in AI processing
chain. Audio flows in from the telephony provider, gets transcribed, processed
by an LLM, and the response is synthesized back to speech.

Usage:
    from voxbridge.pipeline import PipelineOrchestrator, PipelineConfig

    pipeline = PipelineOrchestrator(config)
    await pipeline.run(session, agent_config)
"""

from voxbridge.pipeline.orchestrator import PipelineOrchestrator, PipelineConfig
from voxbridge.pipeline.context import ConversationContext
from voxbridge.pipeline.turn_detector import TurnDetector
from voxbridge.pipeline.escalation import EscalationDetector, EscalationResult

__all__ = [
    "PipelineOrchestrator",
    "PipelineConfig",
    "ConversationContext",
    "TurnDetector",
    "EscalationDetector",
    "EscalationResult",
]
