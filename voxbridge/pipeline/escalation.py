"""Escalation detection for the AI pipeline.

Detects when a call should be escalated to a human agent based on:
- Caller sentiment / anger detection
- Keyword triggers (e.g., "speak to a human", "transfer me")
- Conversation complexity (too many turns without resolution)
- Explicit DTMF escalation (e.g., press 0 for agent)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class EscalationResult:
    """Result of an escalation check."""

    should_escalate: bool = False
    reason: str = ""
    confidence: float = 0.0
    trigger: str = ""  # "keyword", "sentiment", "turns", "dtmf", "explicit"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationDetector:
    """Detects when a call should be escalated to a human agent.

    Configurable detection strategies:
    1. Keyword matching: Detect phrases like "speak to an agent"
    2. Turn count: Escalate after too many turns without resolution
    3. Repeated questions: Detect when the caller repeats themselves
    4. Sentiment: Detect frustration/anger patterns

    Args:
        enabled: Whether escalation detection is active (default: True).
        keyword_triggers: List of phrases that trigger escalation.
        max_turns_before_escalation: Max conversation turns (default: 15).
        repeated_question_threshold: Number of similar questions to trigger (default: 3).
        transfer_number: Phone number to transfer to on escalation.
        transfer_message: Message to say before transferring.
    """

    enabled: bool = True
    keyword_triggers: list[str] = field(default_factory=lambda: [
        "speak to a human",
        "speak to an agent",
        "talk to a person",
        "talk to a human",
        "talk to an agent",
        "transfer me",
        "connect me to a person",
        "real person",
        "human agent",
        "representative",
        "operator",
        "supervisor",
        "manager",
        "let me speak to someone",
        "I want a human",
    ])
    max_turns_before_escalation: int = 15
    repeated_question_threshold: int = 3
    transfer_number: str = ""
    transfer_message: str = "I'm transferring you to a human agent now. Please hold."

    # Anger/frustration patterns
    _anger_patterns: list[str] = field(default_factory=lambda: [
        r"this is (?:so |really )?(?:frustrating|ridiculous|unacceptable|terrible|awful)",
        r"(?:I'm|I am) (?:so |really |very )?(?:angry|frustrated|upset|furious|mad)",
        r"(?:you're|you are) (?:useless|terrible|awful|incompetent|stupid|dumb)",
        r"this (?:doesn't|does not|isn't|is not) (?:help|work|make sense)",
        r"(?:wtf|omg|seriously|come on|for god'?s? sake)\b",
        r"I (?:already|just) (?:told|said|explained) (?:you|that)",
        r"what the (?:hell|heck|fuck)\b",
    ])

    # Internal tracking
    _turn_count: int = 0
    _user_messages: list[str] = field(default_factory=list)
    _escalation_triggered: bool = False

    def check_user_message(self, text: str) -> EscalationResult:
        """Check a user message for escalation triggers.

        Should be called on each user turn. Returns an EscalationResult
        indicating whether to escalate and why.

        Args:
            text: The user's transcribed speech.

        Returns:
            EscalationResult with escalation decision.
        """
        if not self.enabled or self._escalation_triggered:
            return EscalationResult()

        self._turn_count += 1
        self._user_messages.append(text.lower().strip())
        text_lower = text.lower().strip()

        # 1. Check keyword triggers
        for keyword in self.keyword_triggers:
            if keyword.lower() in text_lower:
                self._escalation_triggered = True
                logger.info(f"Escalation triggered by keyword: '{keyword}'")
                return EscalationResult(
                    should_escalate=True,
                    reason=f"Caller requested human: '{keyword}'",
                    confidence=0.95,
                    trigger="keyword",
                    metadata={"keyword": keyword},
                )

        # 2. Check anger patterns
        for pattern in self._anger_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                logger.info(f"Anger pattern detected: {pattern}")
                return EscalationResult(
                    should_escalate=True,
                    reason="Caller frustration detected",
                    confidence=0.7,
                    trigger="sentiment",
                    metadata={"pattern": pattern},
                )

        # 3. Check turn count
        if self._turn_count >= self.max_turns_before_escalation:
            logger.info(
                f"Max turns ({self.max_turns_before_escalation}) reached"
            )
            return EscalationResult(
                should_escalate=True,
                reason=f"Conversation exceeded {self.max_turns_before_escalation} turns",
                confidence=0.6,
                trigger="turns",
                metadata={"turn_count": self._turn_count},
            )

        # 4. Check repeated questions
        if len(self._user_messages) >= self.repeated_question_threshold:
            recent = self._user_messages[-self.repeated_question_threshold:]
            if self._are_similar(recent):
                logger.info("Repeated question pattern detected")
                return EscalationResult(
                    should_escalate=True,
                    reason="Caller is repeating the same question",
                    confidence=0.65,
                    trigger="repeated",
                    metadata={"repeated_messages": recent},
                )

        return EscalationResult()

    def check_dtmf(self, digit: str) -> EscalationResult:
        """Check if a DTMF digit triggers escalation.

        Convention: pressing "0" during a call requests a human agent.

        Args:
            digit: The DTMF digit pressed.

        Returns:
            EscalationResult with escalation decision.
        """
        if not self.enabled:
            return EscalationResult()

        if digit == "0":
            self._escalation_triggered = True
            logger.info("Escalation triggered by DTMF 0")
            return EscalationResult(
                should_escalate=True,
                reason="Caller pressed 0 to speak with a human agent",
                confidence=1.0,
                trigger="dtmf",
                metadata={"digit": digit},
            )

        return EscalationResult()

    def reset(self) -> None:
        """Reset escalation state for a new call."""
        self._turn_count = 0
        self._user_messages.clear()
        self._escalation_triggered = False

    @property
    def turn_count(self) -> int:
        """Number of user turns in the conversation."""
        return self._turn_count

    @staticmethod
    def _are_similar(messages: list[str], threshold: float = 0.6) -> bool:
        """Check if a list of messages are similar to each other.

        Uses a simple word overlap metric (Jaccard similarity).
        """
        if len(messages) < 2:
            return False

        word_sets = [set(msg.split()) for msg in messages]

        # Compare each pair
        similar_count = 0
        total_pairs = 0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                total_pairs += 1
                if not word_sets[i] or not word_sets[j]:
                    continue
                intersection = word_sets[i] & word_sets[j]
                union = word_sets[i] | word_sets[j]
                similarity = len(intersection) / len(union) if union else 0
                if similarity >= threshold:
                    similar_count += 1

        return similar_count >= total_pairs * 0.5 if total_pairs > 0 else False
