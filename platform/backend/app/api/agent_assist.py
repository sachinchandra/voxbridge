"""Agent Assist API — real-time AI co-pilot for human agents.

Endpoints:
    POST   /agent-assist/sessions              Start assist session
    GET    /agent-assist/sessions              List sessions
    GET    /agent-assist/sessions/{id}         Get session
    POST   /agent-assist/sessions/{id}/end     End session (generates summary)
    DELETE /agent-assist/sessions/{id}         Delete session

    POST   /agent-assist/sessions/{id}/transcript    Add transcript entry + get suggestions
    POST   /agent-assist/sessions/{id}/accept/{sid}  Accept a suggestion
    POST   /agent-assist/sessions/{id}/dismiss/{sid} Dismiss a suggestion

    GET    /agent-assist/summary               Aggregate assist stats
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import AssistSession
from app.services import agent_assist as assist_svc
from app.middleware.auth import get_current_customer_id

router = APIRouter(prefix="/agent-assist", tags=["agent-assist"])


# -- Request schemas ----------------------------------------------------------

class StartSessionRequest(BaseModel):
    call_id: str = ""
    agent_id: str = ""
    human_agent_name: str = ""


class TranscriptEntryRequest(BaseModel):
    role: str = "caller"        # caller | agent
    content: str = ""


# -- Session endpoints --------------------------------------------------------

@router.post("/sessions")
async def start_session(
    req: StartSessionRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Start a new Agent Assist session for a live call."""
    session = AssistSession(
        customer_id=customer_id,
        call_id=req.call_id,
        agent_id=req.agent_id,
        human_agent_name=req.human_agent_name,
    )
    assist_svc.create_session(session)
    return session.model_dump()


@router.get("/sessions")
async def list_sessions(
    active_only: bool = False,
    customer_id: str = Depends(get_current_customer_id),
):
    """List all assist sessions."""
    sessions = assist_svc.list_sessions(customer_id, active_only)
    return [
        {
            "id": s.id,
            "call_id": s.call_id,
            "human_agent_name": s.human_agent_name,
            "status": s.status.value,
            "suggestions_count": len(s.suggestions),
            "suggestions_accepted": s.suggestions_accepted,
            "compliance_warnings": s.compliance_warnings,
            "caller_sentiment": s.caller_sentiment,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Get full session details including transcript and suggestions."""
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")
    return session.model_dump()


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """End a session and generate call summary + next steps."""
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")

    result = assist_svc.end_session(session_id)
    return {
        "session_id": result.id,
        "status": result.status.value,
        "call_summary": result.call_summary,
        "next_steps": result.next_steps,
        "caller_sentiment": result.caller_sentiment,
        "suggestions_accepted": result.suggestions_accepted,
        "suggestions_dismissed": result.suggestions_dismissed,
        "compliance_warnings": result.compliance_warnings,
        "pii_detected": result.pii_detected,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Delete a session."""
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")
    assist_svc.delete_session(session_id)
    return {"deleted": True}


# -- Transcript + suggestions -------------------------------------------------

@router.post("/sessions/{session_id}/transcript")
async def add_transcript(
    session_id: str,
    req: TranscriptEntryRequest,
    customer_id: str = Depends(get_current_customer_id),
):
    """Add a transcript entry and get real-time suggestions back.

    This is the core endpoint — called each time someone speaks
    during the call. Returns any new suggestions generated.
    """
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")

    suggestions = assist_svc.add_transcript_entry(session_id, req.role, req.content)
    return {
        "suggestions": [s.model_dump() for s in suggestions],
        "transcript_length": len(session.transcript),
        "caller_sentiment": session.caller_sentiment,
    }


@router.post("/sessions/{session_id}/accept/{suggestion_id}")
async def accept_suggestion(
    session_id: str,
    suggestion_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Mark a suggestion as accepted (used by the agent)."""
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")

    result = assist_svc.accept_suggestion(session_id, suggestion_id)
    if not result:
        raise HTTPException(404, "Suggestion not found")
    return {"accepted": True, "suggestion_id": suggestion_id}


@router.post("/sessions/{session_id}/dismiss/{suggestion_id}")
async def dismiss_suggestion(
    session_id: str,
    suggestion_id: str,
    customer_id: str = Depends(get_current_customer_id),
):
    """Mark a suggestion as dismissed (not useful)."""
    session = assist_svc.get_session(session_id)
    if not session or session.customer_id != customer_id:
        raise HTTPException(404, "Session not found")

    result = assist_svc.dismiss_suggestion(session_id, suggestion_id)
    if not result:
        raise HTTPException(404, "Suggestion not found")
    return {"dismissed": True, "suggestion_id": suggestion_id}


# -- Summary -----------------------------------------------------------------

@router.get("/summary")
async def get_summary(customer_id: str = Depends(get_current_customer_id)):
    """Get aggregate Agent Assist statistics."""
    summary = assist_svc.get_assist_summary(customer_id)
    return summary.model_dump()
