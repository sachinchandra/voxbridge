"""Agent Assist — AI co-pilot for human agents during live calls.

Listens to live calls in real-time and provides:
1. Suggested responses based on conversation context
2. Knowledge base lookups (relevant articles/answers)
3. Compliance warnings (PII, forbidden phrases, required disclosures)
4. Sentiment alerts (angry caller detection)
5. Auto-generated call summary + next steps after call ends

This is the enterprise "land" strategy — add value before replacing.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.models.database import (
    AssistSession,
    AssistSessionStatus,
    AssistSessionSummary,
    AssistSuggestion,
    SuggestionType,
)


# ──────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────

_sessions: dict[str, AssistSession] = {}
MAX_SESSIONS = 500
MAX_SUGGESTIONS_PER_SESSION = 100

# PII patterns for compliance detection
PII_PATTERNS = {
    "ssn": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "phone": r"\b(?:\+1[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "dob": r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b",
}

# Negative sentiment indicators
NEGATIVE_INDICATORS = [
    "angry", "furious", "frustrated", "unacceptable", "terrible",
    "worst", "horrible", "disgusted", "outraged", "ridiculous",
    "complaint", "sue", "lawyer", "manager", "supervisor",
    "cancel", "refund", "never again", "waste of time",
]

# Common response templates by topic
RESPONSE_TEMPLATES = {
    "greeting": "Thank you for calling. How can I help you today?",
    "hold": "I understand your concern. Let me look into this for you — may I place you on a brief hold?",
    "empathy": "I completely understand how frustrating this must be. Let me see what I can do to resolve this.",
    "escalation": "I want to make sure this is handled properly. Let me connect you with a specialist who can help.",
    "closing": "Is there anything else I can help you with today? We appreciate your patience.",
    "order_status": "I can look up your order right away. Could you provide me with your order number?",
    "refund": "I understand you'd like a refund. Let me review your account and see what options are available.",
    "technical": "I'm sorry you're experiencing technical difficulties. Let me walk you through some troubleshooting steps.",
    "billing": "I can review your billing details. Let me pull up your account information.",
    "appointment": "I'd be happy to help schedule an appointment. What dates and times work best for you?",
}


# ──────────────────────────────────────────────────────────────────
# Session CRUD
# ──────────────────────────────────────────────────────────────────

def create_session(session: AssistSession) -> AssistSession:
    """Start a new Agent Assist session."""
    if len(_sessions) >= MAX_SESSIONS:
        # Remove oldest completed sessions
        completed = sorted(
            [s for s in _sessions.values() if s.status == AssistSessionStatus.COMPLETED],
            key=lambda s: s.created_at,
        )
        for old in completed[:50]:
            _sessions.pop(old.id, None)

    _sessions[session.id] = session
    logger.info(f"Assist session started: {session.id} for call {session.call_id}")
    return session


def get_session(session_id: str) -> AssistSession | None:
    return _sessions.get(session_id)


def list_sessions(customer_id: str, active_only: bool = False) -> list[AssistSession]:
    sessions = [s for s in _sessions.values() if s.customer_id == customer_id]
    if active_only:
        sessions = [s for s in sessions if s.status == AssistSessionStatus.ACTIVE]
    return sorted(sessions, key=lambda s: s.created_at, reverse=True)


def end_session(session_id: str) -> AssistSession | None:
    """End a session and generate call summary."""
    session = _sessions.get(session_id)
    if not session:
        return None

    session.status = AssistSessionStatus.COMPLETED
    session.ended_at = datetime.now(timezone.utc)

    # Generate call summary from transcript
    session.call_summary = generate_call_summary(session)
    session.next_steps = generate_next_steps(session)

    logger.info(f"Assist session ended: {session_id}")
    return session


def delete_session(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None


# ──────────────────────────────────────────────────────────────────
# Transcript processing
# ──────────────────────────────────────────────────────────────────

def add_transcript_entry(
    session_id: str,
    role: str,
    content: str,
) -> list[AssistSuggestion]:
    """Add a transcript entry and generate suggestions.

    Args:
        session_id: The assist session ID.
        role: Who spoke — "caller" or "agent".
        content: What was said.

    Returns:
        List of new suggestions generated from this utterance.
    """
    session = _sessions.get(session_id)
    if not session or session.status != AssistSessionStatus.ACTIVE:
        return []

    session.transcript.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    new_suggestions: list[AssistSuggestion] = []

    # 1. Check for PII
    pii_suggestions = detect_pii(session, content, role)
    new_suggestions.extend(pii_suggestions)

    # 2. Detect sentiment (only for caller)
    if role == "caller":
        sentiment_suggestions = detect_sentiment(session, content)
        new_suggestions.extend(sentiment_suggestions)

    # 3. Generate response suggestions (only when caller speaks)
    if role == "caller":
        response_suggestions = generate_response_suggestions(session, content)
        new_suggestions.extend(response_suggestions)

    # Add suggestions to session
    for s in new_suggestions:
        if len(session.suggestions) < MAX_SUGGESTIONS_PER_SESSION:
            session.suggestions.append(s)

    return new_suggestions


# ──────────────────────────────────────────────────────────────────
# PII detection
# ──────────────────────────────────────────────────────────────────

def detect_pii(
    session: AssistSession,
    text: str,
    role: str,
) -> list[AssistSuggestion]:
    """Detect PII in transcript and generate compliance warnings."""
    suggestions = []

    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            session.pii_detected = True
            session.compliance_warnings += 1

            suggestions.append(AssistSuggestion(
                session_id=session.id,
                type=SuggestionType.COMPLIANCE,
                content=f"PII detected ({pii_type}) in {role} speech. "
                        f"Ensure this data is handled according to policy. "
                        f"Do not read back or confirm sensitive information verbally.",
                confidence=0.95,
                source=f"pii_detector:{pii_type}",
            ))

    return suggestions


# ──────────────────────────────────────────────────────────────────
# Sentiment detection
# ──────────────────────────────────────────────────────────────────

def detect_sentiment(
    session: AssistSession,
    caller_text: str,
) -> list[AssistSuggestion]:
    """Detect caller sentiment and alert agent if negative."""
    text_lower = caller_text.lower()
    negative_count = sum(1 for indicator in NEGATIVE_INDICATORS if indicator in text_lower)

    suggestions = []

    if negative_count >= 3:
        session.caller_sentiment = "negative"
        suggestions.append(AssistSuggestion(
            session_id=session.id,
            type=SuggestionType.SENTIMENT,
            content="Caller appears very frustrated. Use empathetic language, "
                    "acknowledge their frustration, and focus on resolution. "
                    "Consider offering escalation to a supervisor if needed.",
            confidence=min(1.0, negative_count * 0.2),
            source="sentiment_detector",
        ))
    elif negative_count >= 1:
        session.caller_sentiment = "negative"
        suggestions.append(AssistSuggestion(
            session_id=session.id,
            type=SuggestionType.SENTIMENT,
            content="Caller may be frustrated. Use empathetic language and "
                    "acknowledge their concern before proceeding.",
            confidence=0.6,
            source="sentiment_detector",
        ))

    return suggestions


# ──────────────────────────────────────────────────────────────────
# Response suggestions
# ──────────────────────────────────────────────────────────────────

def generate_response_suggestions(
    session: AssistSession,
    caller_text: str,
) -> list[AssistSuggestion]:
    """Generate suggested responses based on caller input.

    In production, this would call an LLM with the full conversation
    context. For now, uses keyword-based template matching.
    """
    text_lower = caller_text.lower()
    suggestions = []

    # Topic detection
    topic_matches = {
        "order_status": ["order", "tracking", "shipment", "delivery", "package", "where is my"],
        "refund": ["refund", "money back", "return", "credit", "charge"],
        "billing": ["bill", "invoice", "payment", "charge", "price", "cost"],
        "technical": ["not working", "error", "broken", "crash", "bug", "issue", "problem"],
        "appointment": ["appointment", "schedule", "booking", "reserve", "available"],
        "escalation": ["manager", "supervisor", "speak to someone", "transfer", "escalate"],
        "greeting": ["hello", "hi ", "hey", "good morning", "good afternoon"],
        "closing": ["thank you", "thanks", "goodbye", "that's all", "nothing else"],
    }

    for topic, keywords in topic_matches.items():
        match_count = sum(1 for kw in keywords if kw in text_lower)
        if match_count > 0:
            template = RESPONSE_TEMPLATES.get(topic, "")
            if template:
                confidence = min(0.9, match_count * 0.3)
                suggestions.append(AssistSuggestion(
                    session_id=session.id,
                    type=SuggestionType.RESPONSE,
                    content=template,
                    confidence=confidence,
                    source=f"template:{topic}",
                ))

    # If caller seems to need empathy and no other match
    if not suggestions and session.caller_sentiment == "negative":
        suggestions.append(AssistSuggestion(
            session_id=session.id,
            type=SuggestionType.RESPONSE,
            content=RESPONSE_TEMPLATES["empathy"],
            confidence=0.7,
            source="template:empathy",
        ))

    # Knowledge suggestion (simulated)
    if any(kw in text_lower for kw in ["how do i", "how to", "where can i", "what is"]):
        suggestions.append(AssistSuggestion(
            session_id=session.id,
            type=SuggestionType.KNOWLEDGE,
            content=f"Search knowledge base for: \"{caller_text[:80]}\"",
            confidence=0.75,
            source="knowledge_lookup",
        ))

    # Action suggestion
    if any(kw in text_lower for kw in ["cancel", "close account", "delete"]):
        suggestions.append(AssistSuggestion(
            session_id=session.id,
            type=SuggestionType.ACTION,
            content="Caller may want to cancel. Check retention offers before proceeding. "
                    "Document reason for cancellation.",
            confidence=0.8,
            source="action_detector",
        ))

    return suggestions


# ──────────────────────────────────────────────────────────────────
# Accept / dismiss suggestions
# ──────────────────────────────────────────────────────────────────

def accept_suggestion(session_id: str, suggestion_id: str) -> AssistSuggestion | None:
    """Mark a suggestion as accepted (used by the agent)."""
    session = _sessions.get(session_id)
    if not session:
        return None
    for s in session.suggestions:
        if s.id == suggestion_id:
            s.accepted = True
            session.suggestions_accepted += 1
            return s
    return None


def dismiss_suggestion(session_id: str, suggestion_id: str) -> AssistSuggestion | None:
    """Mark a suggestion as dismissed (not useful)."""
    session = _sessions.get(session_id)
    if not session:
        return None
    for s in session.suggestions:
        if s.id == suggestion_id:
            s.accepted = False
            session.suggestions_dismissed += 1
            return s
    return None


# ──────────────────────────────────────────────────────────────────
# Call summary generation
# ──────────────────────────────────────────────────────────────────

def generate_call_summary(session: AssistSession) -> str:
    """Generate a summary of the call from the transcript.

    In production, this would use an LLM. For now, builds a structured
    summary from the transcript metadata.
    """
    if not session.transcript:
        return "No transcript available."

    caller_msgs = [t for t in session.transcript if t["role"] == "caller"]
    agent_msgs = [t for t in session.transcript if t["role"] == "agent"]

    parts = []
    parts.append(f"Call with {len(session.transcript)} exchanges "
                 f"({len(caller_msgs)} caller, {len(agent_msgs)} agent).")

    if session.caller_sentiment != "neutral":
        parts.append(f"Caller sentiment: {session.caller_sentiment}.")

    if session.pii_detected:
        parts.append("PII was detected during the call.")

    if session.compliance_warnings > 0:
        parts.append(f"{session.compliance_warnings} compliance warning(s) raised.")

    if session.suggestions_accepted > 0:
        total = session.suggestions_accepted + session.suggestions_dismissed
        parts.append(
            f"Agent used {session.suggestions_accepted}/{total} suggestions "
            f"({session.suggestions_accepted / max(total, 1) * 100:.0f}% acceptance rate)."
        )

    # Extract topic from first caller message
    if caller_msgs:
        first_msg = caller_msgs[0]["content"][:100]
        parts.append(f"Initial topic: \"{first_msg}\"")

    return " ".join(parts)


def generate_next_steps(session: AssistSession) -> list[str]:
    """Generate recommended next steps after call ends."""
    steps = []

    if session.pii_detected:
        steps.append("Review call for PII compliance — ensure sensitive data was handled properly")

    if session.caller_sentiment == "negative":
        steps.append("Follow up with caller within 24 hours to ensure resolution")
        steps.append("Review call for potential service improvement opportunities")

    if session.compliance_warnings > 0:
        steps.append("Review compliance warnings and take corrective action if needed")

    # Check if escalation was mentioned
    for entry in session.transcript:
        if any(kw in entry["content"].lower() for kw in ["escalate", "supervisor", "manager"]):
            steps.append("Ensure escalation was completed and documented")
            break

    if not steps:
        steps.append("No follow-up actions required")

    return steps


# ──────────────────────────────────────────────────────────────────
# Summary statistics
# ──────────────────────────────────────────────────────────────────

def get_assist_summary(customer_id: str) -> AssistSessionSummary:
    """Get aggregate stats for Agent Assist usage."""
    sessions = [s for s in _sessions.values() if s.customer_id == customer_id]
    active = [s for s in sessions if s.status == AssistSessionStatus.ACTIVE]

    total_suggestions = sum(len(s.suggestions) for s in sessions)
    total_accepted = sum(s.suggestions_accepted for s in sessions)
    total_dismissed = sum(s.suggestions_dismissed for s in sessions)
    total_reviewed = total_accepted + total_dismissed

    return AssistSessionSummary(
        total_sessions=len(sessions),
        active_sessions=len(active),
        total_suggestions=total_suggestions,
        acceptance_rate=round(total_accepted / max(total_reviewed, 1), 2),
        compliance_warnings=sum(s.compliance_warnings for s in sessions),
        avg_suggestions_per_session=round(total_suggestions / max(len(sessions), 1), 1),
    )
