"""Playground API — test AI agents via text chat and voice in the browser.

Endpoints:
    POST /playground/start         Start a new test session
    POST /playground/message       Send a message in a session
    POST /playground/audio-turn    Send audio, get audio + text back (STT → LLM → TTS)
    POST /playground/end           End a session
    GET  /playground/session/{id}  Get session details
    POST /playground/quick-test    One-shot test (no session needed)
    GET  /playground/audio-config  Check which audio providers are available
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.models.database import PlaygroundResponse
from app.services import database as db
from app.services import playground as pg
from app.services import stt, tts
from app.config import settings
from app.middleware.auth import get_current_customer_id

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
    customer_id: str = Depends(get_current_customer_id),
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
    customer_id: str = Depends(get_current_customer_id),
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
    customer_id: str = Depends(get_current_customer_id),
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
    customer_id: str = Depends(get_current_customer_id),
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
    customer_id: str = Depends(get_current_customer_id),
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


# ── Audio endpoints ─────────────────────────────────────────────

@router.get("/audio-config")
async def audio_config(customer_id: str = Depends(get_current_customer_id)):
    """Check which audio providers are configured and available."""
    return {
        "stt_available": bool(settings.deepgram_api_key or settings.openai_api_key),
        "tts_available": bool(settings.openai_api_key or settings.elevenlabs_api_key),
        "stt_provider": "deepgram" if settings.deepgram_api_key else ("openai" if settings.openai_api_key else "none"),
        "tts_provider": "openai" if settings.openai_api_key else ("elevenlabs" if settings.elevenlabs_api_key else "none"),
    }


@router.post("/audio-turn")
async def audio_turn(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    customer_id: str = Depends(get_current_customer_id),
):
    """Complete audio conversation turn: STT → LLM → TTS.

    Accepts audio file from browser mic, transcribes it, feeds text to LLM
    via the existing playground session, synthesizes the reply to speech,
    and returns both the text and audio response.

    Request: multipart/form-data with `audio` file and `session_id` field.
    Response: JSON with transcript, reply text, and base64-encoded audio.
    """
    # Validate session
    session = pg.get_session(session_id)
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

    # 1. Read audio
    audio_data = await audio.read()
    if not audio_data or len(audio_data) < 100:
        raise HTTPException(400, "Audio data too small or empty")

    content_type = audio.content_type or "audio/webm"

    # 2. STT — transcribe audio to text
    stt_provider = agent.stt_provider or "deepgram"
    stt_result = await stt.transcribe_audio(
        audio_data=audio_data,
        content_type=content_type,
        provider=stt_provider,
        config=agent.stt_config or {},
    )

    if stt_result.get("error"):
        return JSONResponse(status_code=422, content={
            "error": "stt_failed",
            "detail": stt_result["error"],
            "stt_provider": stt_result.get("provider", "unknown"),
        })

    transcript = stt_result.get("transcript", "").strip()
    if not transcript:
        return JSONResponse(content={
            "transcript": "",
            "reply": "",
            "audio_base64": "",
            "done": False,
            "stt_ms": stt_result["duration_ms"],
            "llm_ms": 0,
            "tts_ms": 0,
            "message": "No speech detected in audio",
        })

    # 3. LLM — process turn (reuse existing text pipeline)
    agent_config = {
        "system_prompt": agent.system_prompt,
        "first_message": agent.first_message,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "llm_config": agent.llm_config,
        "tools": agent.tools,
        "end_call_phrases": agent.end_call_phrases,
    }

    llm_result = await pg.process_turn(
        session=session,
        user_message=transcript,
        agent_config=agent_config,
    )

    reply_text = llm_result.get("reply", "")
    done = llm_result.get("done", False)

    if done:
        pg.end_session(session_id)

    # 4. TTS — synthesize reply to audio
    tts_provider = agent.tts_provider or "openai"
    tts_result = await tts.synthesize_speech(
        text=reply_text,
        provider=tts_provider,
        voice_id=agent.tts_voice_id or "",
        config=agent.tts_config or {},
    )

    # Encode audio as base64 for JSON transport
    audio_b64 = ""
    if tts_result.get("audio_data") and not tts_result.get("error"):
        audio_b64 = base64.b64encode(tts_result["audio_data"]).decode("utf-8")

    return {
        "transcript": transcript,
        "reply": reply_text,
        "audio_base64": audio_b64,
        "audio_content_type": tts_result.get("content_type", "audio/mpeg"),
        "done": done,
        "tool_calls": llm_result.get("tool_calls", []),
        "tokens_used": llm_result.get("tokens_used", 0),
        "stt_ms": stt_result.get("duration_ms", 0),
        "llm_ms": llm_result.get("latency_ms", 0),
        "tts_ms": tts_result.get("duration_ms", 0),
        "stt_provider": stt_result.get("provider", "unknown"),
        "tts_provider": tts_result.get("provider", "unknown"),
        "tts_error": tts_result.get("error"),
    }
