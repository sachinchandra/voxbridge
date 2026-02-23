"""Playground API — test AI agents via text chat in the browser.

Endpoints:
    POST /playground/start         Start a new test session
    POST /playground/message       Send a message in a session
    POST /playground/end           End a session
    GET  /playground/session/{id}  Get session details
    POST /playground/quick-test    One-shot test (no session needed)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.database import PlaygroundResponse
from app.services import database as db
from app.services import playground as pg
from app.middleware.auth import get_current_customer

router = APIRouter(prefix="/playground", tags=["playground"])


# ── Request schemas ──────────────────────────────────────────────

class StartRequest(BaseModel):
    agent_id: str


class MessageRequest(BaseModel):
    session_id: str
    message: str


class QuickTestRequest(BaseModel):
    agent_id: str
    message: str


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/start")
async def start_session(
    req: StartRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Start a new playground test session with an agent."""
    agent = db.get_agent(req.agent_id, customer_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    session = pg.create_session(
        customer_id=customer_id,
        agent_id=req.agent_id,
        agent_name=agent.name,
    )

    # If agent has a first message, include it
    first_message = agent.first_message or ""
    if first_message:
        from app.models.database import PlaygroundMessage
        import time
        session.messages.append(PlaygroundMessage(
            role="assistant",
            content=first_message,
            timestamp=time.time(),
        ))

    return {
        "session_id": session.id,
        "agent_name": agent.name,
        "first_message": first_message,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
    }


@router.post("/message", response_model=PlaygroundResponse)
async def send_message(
    req: MessageRequest,
    customer_id: str = Depends(get_current_customer),
):
    """Send a message in an active playground session."""
    session = pg.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found or expired")
    if session.customer_id != customer_id:
        raise HTTPException(403, "Not your session")
    if session.status != "active":
        raise HTTPException(400, "Session is no longer active")

    # Load agent config
    agent = db.get_agent(session.agent_id, customer_id)
    if not agent:
        raise HTTPException(404, "Agent no longer exists")

    agent_config = {
        "system_prompt": agent.system_prompt,
        "first_message": agent.first_message,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "llm_config": agent.llm_config,
        "tools": agent.tools,
        "end_call_phrases": agent.end_call_phrases,
    }

    result = await pg.process_turn(
        session=session,
        user_message=req.message,
        agent_config=agent_config,
    )

    if result.get("done"):
        pg.end_session(req.session_id)

    return PlaygroundResponse(
        session_id=req.session_id,
        reply=result["reply"],
        tool_calls=result.get("tool_calls", []),
        done=result.get("done", False),
        latency_ms=result.get("latency_ms", 0),
        tokens_used=result.get("tokens_used", 0),
    )


@router.post("/end/{session_id}")
async def end_session(
    session_id: str,
    customer_id: str = Depends(get_current_customer),
):
    """End a playground session."""
    session = pg.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.customer_id != customer_id:
        raise HTTPException(403, "Not your session")

    pg.end_session(session_id)
    return {
        "session_id": session_id,
        "status": "completed",
        "total_turns": session.total_turns,
        "total_tokens": session.total_tokens,
        "estimated_cost_cents": session.estimated_cost_cents,
    }


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    customer_id: str = Depends(get_current_customer),
):
    """Get playground session details."""
    session = pg.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.customer_id != customer_id:
        raise HTTPException(403, "Not your session")

    return {
        "session_id": session.id,
        "agent_id": session.agent_id,
        "agent_name": session.agent_name,
        "status": session.status,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
                "latency_ms": m.latency_ms,
                "tool_call": m.tool_call,
            }
            for m in session.messages
        ],
        "total_turns": session.total_turns,
        "total_tokens": session.total_tokens,
        "estimated_cost_cents": session.estimated_cost_cents,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }


@router.post("/quick-test", response_model=PlaygroundResponse)
async def quick_test(
    req: QuickTestRequest,
    customer_id: str = Depends(get_current_customer),
):
    """One-shot test — send a single message to an agent without creating a persistent session."""
    agent = db.get_agent(req.agent_id, customer_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Create ephemeral session
    session = pg.create_session(
        customer_id=customer_id,
        agent_id=req.agent_id,
        agent_name=agent.name,
    )

    agent_config = {
        "system_prompt": agent.system_prompt,
        "first_message": agent.first_message,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "llm_config": agent.llm_config,
        "tools": agent.tools,
        "end_call_phrases": agent.end_call_phrases,
    }

    result = await pg.process_turn(
        session=session,
        user_message=req.message,
        agent_config=agent_config,
    )

    # Clean up ephemeral session
    pg.delete_session(session.id)

    return PlaygroundResponse(
        session_id=session.id,
        reply=result["reply"],
        tool_calls=result.get("tool_calls", []),
        done=True,
        latency_ms=result.get("latency_ms", 0),
        tokens_used=result.get("tokens_used", 0),
    )
