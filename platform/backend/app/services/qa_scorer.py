"""Automated QA scoring service for call quality analysis.

Scores every call on:
- Accuracy: Did the AI provide correct information?
- Tone: Was the tone professional, friendly, appropriate?
- Resolution: Was the caller's issue resolved?
- Compliance: Did the AI follow the system prompt and rules?

Also detects:
- PII exposure in transcripts
- Angry/frustrated callers
- Calls that need human review
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger


# PII patterns
PII_PATTERNS = [
    (r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b', 'SSN'),  # Social Security
    (r'\b\d{16}\b', 'Credit Card'),  # Credit card number (16 digits)
    (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 'Credit Card'),  # Credit card formatted
    (r'\b[A-Z]{1,2}\d{6,9}\b', 'ID Number'),  # Passport/ID
]

# Anger indicators
ANGER_KEYWORDS = [
    'angry', 'furious', 'ridiculous', 'unacceptable', 'terrible',
    'worst', 'lawsuit', 'sue you', 'speak to manager', 'supervisor',
    'complaint', 'incompetent', 'useless', 'waste of time', 'frustrated',
    'fed up', 'disgusted', 'outrageous', 'scam', 'rip off',
]

# Positive resolution indicators
RESOLUTION_POSITIVE = [
    'thank you', 'thanks', 'that helps', 'great', 'perfect',
    'awesome', 'appreciate', 'resolved', 'sorted', 'fixed',
    'understood', 'helpful', 'wonderful', 'excellent',
]

# Negative resolution indicators
RESOLUTION_NEGATIVE = [
    "didn't help", "not helpful", "still confused", "doesn't answer",
    "useless", "waste", "hanging up", "forget it", "never mind",
]


def score_call(
    transcript: list[dict],
    resolution: str,
    escalated: bool,
    sentiment_score: float | None,
    system_prompt: str = "",
) -> dict[str, Any]:
    """Score a call based on its transcript and metadata.

    Args:
        transcript: List of {role, content, timestamp} messages.
        resolution: "resolved", "escalated", or "abandoned".
        escalated: Whether the call was escalated to a human.
        sentiment_score: Pre-computed sentiment (-1 to 1).
        system_prompt: The agent's system prompt for compliance checking.

    Returns:
        Dict with all QA fields ready for CallQAScore creation.
    """
    if not transcript:
        return _empty_score()

    # Extract all text
    caller_text = " ".join(
        m.get("content", "") for m in transcript if m.get("role") in ("user", "caller")
    ).lower()
    agent_text = " ".join(
        m.get("content", "") for m in transcript if m.get("role") in ("assistant", "agent")
    ).lower()
    full_text = caller_text + " " + agent_text

    # 1. Accuracy score (based on response coherence and resolution)
    accuracy_score = _score_accuracy(transcript, resolution, escalated)

    # 2. Tone score
    tone_score = _score_tone(agent_text, sentiment_score)

    # 3. Resolution score
    resolution_score = _score_resolution(caller_text, resolution, escalated)

    # 4. Compliance score
    compliance_score = _score_compliance(agent_text, system_prompt)

    # 5. Overall (weighted average)
    overall_score = int(
        accuracy_score * 0.30
        + tone_score * 0.20
        + resolution_score * 0.30
        + compliance_score * 0.20
    )

    # 6. Detect PII
    pii_detected, pii_types = _detect_pii(full_text)

    # 7. Detect angry caller
    angry_caller = _detect_anger(caller_text)

    # 8. Flag determination
    flag_reasons = []
    if pii_detected:
        flag_reasons.append(f"PII detected: {', '.join(pii_types)}")
    if angry_caller:
        flag_reasons.append("Angry/frustrated caller")
    if overall_score < 50:
        flag_reasons.append("Low overall score")
    if escalated:
        flag_reasons.append("Call was escalated")
    if resolution == "abandoned":
        flag_reasons.append("Caller abandoned")

    flagged = len(flag_reasons) > 0

    # 9. Generate summary
    summary = _generate_summary(
        transcript, resolution, escalated, overall_score, flag_reasons
    )

    # 10. Improvement suggestions
    suggestions = _generate_suggestions(
        accuracy_score, tone_score, resolution_score, compliance_score,
        pii_detected, angry_caller,
    )

    return {
        "accuracy_score": accuracy_score,
        "tone_score": tone_score,
        "resolution_score": resolution_score,
        "compliance_score": compliance_score,
        "overall_score": overall_score,
        "pii_detected": pii_detected,
        "angry_caller": angry_caller,
        "flagged": flagged,
        "flag_reasons": flag_reasons,
        "summary": summary,
        "improvement_suggestions": suggestions,
    }


def _empty_score() -> dict:
    """Return an empty score for calls with no transcript."""
    return {
        "accuracy_score": 0,
        "tone_score": 0,
        "resolution_score": 0,
        "compliance_score": 0,
        "overall_score": 0,
        "pii_detected": False,
        "angry_caller": False,
        "flagged": True,
        "flag_reasons": ["No transcript available"],
        "summary": "Call had no transcript data to analyze.",
        "improvement_suggestions": [],
    }


def _score_accuracy(transcript: list[dict], resolution: str, escalated: bool) -> int:
    """Score accuracy based on conversation quality signals."""
    score = 70  # Base score

    # Resolution boosts/penalties
    if resolution == "resolved":
        score += 20
    elif resolution == "abandoned":
        score -= 25
    elif resolution == "escalated":
        score -= 10

    # Multi-turn conversation (AI engaged meaningfully)
    agent_turns = sum(1 for m in transcript if m.get("role") in ("assistant", "agent"))
    if agent_turns >= 3:
        score += 5
    if agent_turns >= 6:
        score += 5

    # Penalty for very short calls (likely unhelpful)
    if len(transcript) < 3:
        score -= 15

    return max(0, min(100, score))


def _score_tone(agent_text: str, sentiment_score: float | None) -> int:
    """Score tone based on agent language and sentiment."""
    score = 75  # Base score

    # Positive tone indicators
    polite_words = ['please', 'thank you', 'happy to help', 'certainly', 'of course', 'glad to']
    for word in polite_words:
        if word in agent_text:
            score += 3

    # Negative tone indicators
    negative_words = ['unfortunately', 'cannot', "can't", 'impossible', 'unable', 'no way']
    negative_count = sum(1 for w in negative_words if w in agent_text)
    score -= negative_count * 3

    # Sentiment adjustment
    if sentiment_score is not None:
        if sentiment_score > 0.5:
            score += 10
        elif sentiment_score > 0:
            score += 5
        elif sentiment_score < -0.5:
            score -= 15
        elif sentiment_score < 0:
            score -= 5

    return max(0, min(100, score))


def _score_resolution(caller_text: str, resolution: str, escalated: bool) -> int:
    """Score resolution based on outcome and caller satisfaction signals."""
    score = 50  # Neutral baseline

    if resolution == "resolved":
        score = 85
    elif resolution == "escalated":
        score = 40
    elif resolution == "abandoned":
        score = 20

    # Positive signals from caller
    for phrase in RESOLUTION_POSITIVE:
        if phrase in caller_text:
            score += 3

    # Negative signals from caller
    for phrase in RESOLUTION_NEGATIVE:
        if phrase in caller_text:
            score -= 5

    return max(0, min(100, score))


def _score_compliance(agent_text: str, system_prompt: str) -> int:
    """Score compliance with the system prompt rules."""
    score = 80  # Assume compliance by default

    if not system_prompt:
        return score  # No rules to check

    prompt_lower = system_prompt.lower()

    # Check for key behavioral directives
    # If prompt says "be concise" and AI gave long responses
    if "concise" in prompt_lower or "brief" in prompt_lower:
        if len(agent_text) > 2000:
            score -= 10

    # If prompt mentions specific forbidden topics
    forbidden_patterns = [
        (r'never\s+(?:mention|discuss|talk about)\s+(\w+)', "forbidden topic"),
        (r'do\s+not\s+(?:mention|discuss|talk about)\s+(\w+)', "forbidden topic"),
    ]
    for pattern, _ in forbidden_patterns:
        matches = re.findall(pattern, prompt_lower)
        for topic in matches:
            if topic in agent_text:
                score -= 20

    return max(0, min(100, score))


def _detect_pii(text: str) -> tuple[bool, list[str]]:
    """Detect PII patterns in the transcript."""
    found_types = []
    for pattern, pii_type in PII_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if pii_type not in found_types:
                found_types.append(pii_type)
    return len(found_types) > 0, found_types


def _detect_anger(caller_text: str) -> bool:
    """Detect if the caller was angry or frustrated."""
    anger_count = sum(1 for kw in ANGER_KEYWORDS if kw in caller_text)
    # Consider angry if 2+ indicators found
    return anger_count >= 2


def _generate_summary(
    transcript: list[dict],
    resolution: str,
    escalated: bool,
    overall_score: int,
    flag_reasons: list[str],
) -> str:
    """Generate a brief call summary."""
    turn_count = len(transcript)
    caller_msgs = sum(1 for m in transcript if m.get("role") in ("user", "caller"))

    parts = []

    # Quality assessment
    if overall_score >= 80:
        parts.append("High quality call.")
    elif overall_score >= 60:
        parts.append("Acceptable call quality.")
    elif overall_score >= 40:
        parts.append("Below average call quality.")
    else:
        parts.append("Poor call quality — review recommended.")

    # Resolution
    if resolution == "resolved":
        parts.append("Issue resolved successfully.")
    elif resolution == "escalated":
        parts.append("Escalated to human agent.")
    elif resolution == "abandoned":
        parts.append("Caller abandoned the call.")

    # Stats
    parts.append(f"{turn_count} total messages, {caller_msgs} from caller.")

    # Flags
    if flag_reasons:
        parts.append(f"Flagged: {'; '.join(flag_reasons)}")

    return " ".join(parts)


def _generate_suggestions(
    accuracy: int, tone: int, resolution: int, compliance: int,
    pii_detected: bool, angry_caller: bool,
) -> list[str]:
    """Generate improvement suggestions based on scores."""
    suggestions = []

    if accuracy < 60:
        suggestions.append("Improve response accuracy — consider updating the knowledge base or system prompt with more detailed information.")
    if tone < 60:
        suggestions.append("Improve conversational tone — add more empathetic and polite language patterns to the system prompt.")
    if resolution < 60:
        suggestions.append("Improve issue resolution — ensure the agent has tools to look up information and take actions for callers.")
    if compliance < 60:
        suggestions.append("Review compliance — the agent may be deviating from the system prompt guidelines.")
    if pii_detected:
        suggestions.append("PII was detected in the conversation — add guardrails to prevent the agent from soliciting or repeating sensitive information.")
    if angry_caller:
        suggestions.append("Caller was frustrated — consider adding earlier escalation triggers for negative sentiment.")

    return suggestions
