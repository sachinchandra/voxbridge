"""WebSocket endpoint for live voice playground calls.

Provides a real-time conversational experience:
  Browser mic → WebSocket → Deepgram Streaming STT → LLM → TTS → audio back to browser

The browser streams mic audio continuously. Deepgram detects end-of-speech
automatically (endpointing). When an utterance is complete, the backend
processes it through the LLM and returns synthesized audio.

Client connects to:
    ws://host/api/v1/playground/ws/call?token=<jwt>&session_id=<sid>

Protocol:
    Browser → Server:  binary audio frames (webm/opus chunks from MediaRecorder)
    Server → Browser:  JSON messages:
        { type: "transcript", text: "...", is_final: bool }
        { type: "agent_reply", text: "...", audio_base64: "...", audio_content_type: "...", stt_ms, llm_ms, tts_ms }
        { type: "status", status: "listening" | "processing" | "speaking" }
        { type: "error", message: "..." }
        { type: "call_ended" }
"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from app.config import settings
from app.services.auth import decode_token
from app.services import database as db, playground as pg, tts

router = APIRouter()

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


async def _authenticate(token: str) -> str | None:
    """Validate JWT and return customer_id."""
    try:
        payload = decode_token(token)
        if not payload or "sub" not in payload:
            return None
        return payload["sub"]
    except Exception:
        return None


@router.websocket("/playground/ws/call")
async def playground_live_call(
    ws: WebSocket,
    token: str = Query(...),
    session_id: str = Query(...),
):
    """Live voice call WebSocket for playground testing."""

    # 1. Auth
    customer_id = await _authenticate(token)
    if not customer_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    # 2. Validate session
    session = pg.get_session(session_id)
    if not session or session.customer_id != customer_id or session.status != "active":
        await ws.close(code=4002, reason="Invalid session")
        return

    # 3. Load agent
    agent = db.get_agent(session.agent_id, customer_id)
    if not agent:
        await ws.close(code=4003, reason="Agent not found")
        return

    agent_config = {
        "system_prompt": agent.system_prompt,
        "first_message": agent.first_message,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "llm_config": agent.llm_config,
        "tools": agent.tools,
        "end_call_phrases": agent.end_call_phrases,
    }

    await ws.accept()
    logger.info(f"Live call started: session={session_id}, customer={customer_id}")

    # Send initial status
    await _send_json(ws, {"type": "status", "status": "listening"})

    # If agent has a first message, speak it
    if agent.first_message:
        await _send_json(ws, {"type": "status", "status": "speaking"})
        tts_result = await tts.synthesize_speech(
            text=agent.first_message,
            provider=agent.tts_provider or "openai",
            voice_id=agent.tts_voice_id or "",
            config=agent.tts_config or {},
        )
        audio_b64 = ""
        if tts_result.get("audio_data") and not tts_result.get("error"):
            audio_b64 = base64.b64encode(tts_result["audio_data"]).decode("utf-8")
        await _send_json(ws, {
            "type": "agent_reply",
            "text": agent.first_message,
            "audio_base64": audio_b64,
            "audio_content_type": tts_result.get("content_type", "audio/mpeg"),
            "stt_ms": 0, "llm_ms": 0, "tts_ms": tts_result.get("duration_ms", 0),
        })
        await _send_json(ws, {"type": "status", "status": "listening"})

    # 4. Check if we have Deepgram key for streaming STT
    if settings.deepgram_api_key:
        await _run_with_deepgram_streaming(ws, session, agent, agent_config)
    elif settings.openai_api_key:
        await _run_with_chunked_whisper(ws, session, agent, agent_config)
    else:
        await _send_json(ws, {
            "type": "error",
            "message": "No STT provider configured. Set DEEPGRAM_API_KEY or OPENAI_API_KEY.",
        })
        await ws.close(code=4004, reason="No STT provider")
        return

    logger.info(f"Live call ended: session={session_id}")


# ── Deepgram Streaming Mode ──────────────────────────────────────

async def _run_with_deepgram_streaming(ws: WebSocket, session, agent, agent_config: dict):
    """Full-duplex: browser audio → Deepgram streaming → LLM → TTS → browser."""
    import websockets

    # NOTE: Do NOT specify encoding/sample_rate — browser sends audio/webm;codecs=opus
    # Deepgram auto-detects the format from the container headers
    dg_url = (
        f"{DEEPGRAM_WS_URL}"
        f"?model=nova-2&language=en&smart_format=true&punctuate=true"
        f"&endpointing=300&utterance_end_ms=1000&interim_results=true"
    )

    dg_key = settings.deepgram_api_key.strip()
    logger.info(f"Deepgram key: {dg_key[:8]}...{dg_key[-4:]} (len={len(dg_key)})")
    headers = {"Authorization": f"Token {dg_key}"}
    processing_lock = asyncio.Lock()
    utterance_buffer = ""

    try:
        # websockets v12+ uses `additional_headers`, older versions use `extra_headers`
        try:
            dg_ws = await websockets.connect(dg_url, additional_headers=headers)
        except TypeError:
            dg_ws = await websockets.connect(dg_url, extra_headers=headers)

        async with dg_ws:
            logger.info("Deepgram streaming connected")

            async def _forward_audio():
                """Forward browser audio to Deepgram."""
                chunk_count = 0
                try:
                    while True:
                        data = await ws.receive()
                        if data.get("type") == "websocket.disconnect":
                            logger.info("Browser WS disconnected")
                            break
                        if "bytes" in data:
                            chunk_count += 1
                            if chunk_count <= 3 or chunk_count % 50 == 0:
                                logger.info(f"Forwarding audio chunk #{chunk_count}: {len(data['bytes'])} bytes")
                            await dg_ws.send(data["bytes"])
                        elif "text" in data:
                            msg = json.loads(data["text"])
                            logger.info(f"Browser text msg: {msg}")
                            if msg.get("action") == "end_call":
                                break
                except WebSocketDisconnect:
                    logger.info("Browser WS disconnected (exception)")
                except Exception as e:
                    logger.error(f"Audio forward error: {type(e).__name__}: {e}")
                finally:
                    logger.info(f"Audio forward ended after {chunk_count} chunks")
                    try:
                        await dg_ws.send(json.dumps({"type": "CloseStream"}))
                    except Exception:
                        pass

            async def _read_deepgram():
                """Read Deepgram transcripts and process utterances."""
                nonlocal utterance_buffer
                msg_count = 0
                try:
                    async for msg in dg_ws:
                        msg_count += 1
                        data = json.loads(msg)
                        if msg_count <= 5:
                            logger.info(f"Deepgram msg #{msg_count}: type={data.get('type')}")

                        if data.get("type") == "Results":
                            alt = data.get("channel", {}).get("alternatives", [{}])[0]
                            transcript = alt.get("transcript", "")
                            is_final = data.get("is_final", False)
                            speech_final = data.get("speech_final", False)

                            if transcript:
                                # Send interim/final transcript to browser
                                await _send_json(ws, {
                                    "type": "transcript",
                                    "text": transcript,
                                    "is_final": is_final,
                                })

                                if is_final:
                                    utterance_buffer += " " + transcript

                            # speech_final = Deepgram detected end of utterance
                            if speech_final and utterance_buffer.strip():
                                full_text = utterance_buffer.strip()
                                utterance_buffer = ""

                                # Process through LLM + TTS
                                async with processing_lock:
                                    await _process_and_respond(
                                        ws, session, agent, agent_config, full_text
                                    )

                        elif data.get("type") == "UtteranceEnd":
                            # Fallback: if we have buffered text, process it
                            if utterance_buffer.strip():
                                full_text = utterance_buffer.strip()
                                utterance_buffer = ""
                                async with processing_lock:
                                    await _process_and_respond(
                                        ws, session, agent, agent_config, full_text
                                    )

                except websockets.exceptions.ConnectionClosed as e:
                    logger.info(f"Deepgram WS closed: code={e.code} reason={e.reason}")
                except Exception as e:
                    logger.error(f"Deepgram read error: {type(e).__name__}: {e}")
                finally:
                    logger.info(f"Deepgram read ended after {msg_count} messages")

            # Run both loops concurrently
            forward_task = asyncio.create_task(_forward_audio())
            read_task = asyncio.create_task(_read_deepgram())

            done, pending = await asyncio.wait(
                [forward_task, read_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            done_names = []
            for t in done:
                name = "forward" if t is forward_task else "deepgram_read"
                exc = t.exception() if not t.cancelled() else None
                done_names.append(f"{name}(exc={exc})")
            pending_names = ["forward" if t is forward_task else "deepgram_read" for t in pending]
            logger.info(f"Call loop ended — done={done_names}, pending={pending_names}")

            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    except Exception as e:
        logger.error(f"Deepgram streaming error: {e}")
        await _send_json(ws, {"type": "error", "message": f"STT connection failed: {e}"})

    try:
        await _send_json(ws, {"type": "call_ended"})
        await ws.close()
    except Exception:
        pass


# ── Whisper Chunked Mode (fallback) ─────────────────────────────

async def _run_with_chunked_whisper(ws: WebSocket, session, agent, agent_config: dict):
    """Fallback: collect audio chunks, use silence detection, send to Whisper."""
    from app.services import stt

    audio_chunks: list[bytes] = []
    silence_start: float | None = None
    SILENCE_THRESHOLD = 1.5  # seconds of no audio = end of utterance

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive(), timeout=SILENCE_THRESHOLD)
            except asyncio.TimeoutError:
                # Silence detected — process accumulated audio
                if audio_chunks:
                    combined = b"".join(audio_chunks)
                    audio_chunks.clear()
                    if len(combined) > 500:  # minimum audio size
                        await _send_json(ws, {"type": "status", "status": "processing"})
                        stt_result = await stt.transcribe_audio(
                            audio_data=combined,
                            content_type="audio/webm",
                            provider="openai",
                        )
                        transcript = stt_result.get("transcript", "").strip()
                        if transcript:
                            await _send_json(ws, {
                                "type": "transcript",
                                "text": transcript,
                                "is_final": True,
                            })
                            await _process_and_respond(
                                ws, session, agent, agent_config, transcript,
                                stt_ms=stt_result.get("duration_ms", 0),
                            )
                        else:
                            await _send_json(ws, {"type": "status", "status": "listening"})
                continue

            if data.get("type") == "websocket.disconnect":
                break
            if "bytes" in data:
                audio_chunks.append(data["bytes"])
            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("action") == "end_call":
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Whisper chunked error: {e}")

    try:
        await _send_json(ws, {"type": "call_ended"})
        await ws.close()
    except Exception:
        pass


# ── Shared: Process utterance → LLM → TTS ───────────────────────

async def _process_and_respond(
    ws: WebSocket,
    session,
    agent,
    agent_config: dict,
    user_text: str,
    stt_ms: int = 0,
):
    """Run LLM on transcript → TTS on reply → send audio to browser."""
    await _send_json(ws, {"type": "status", "status": "processing"})

    # LLM
    llm_start = time.time()
    llm_result = await pg.process_turn(session, user_text, agent_config)
    llm_ms = int((time.time() - llm_start) * 1000)

    reply_text = llm_result.get("reply", "")
    done = llm_result.get("done", False)

    if not reply_text:
        await _send_json(ws, {"type": "status", "status": "listening"})
        return

    # TTS
    await _send_json(ws, {"type": "status", "status": "speaking"})
    tts_provider = agent.tts_provider or "openai"
    tts_voice = agent.tts_voice_id or ""
    logger.info(f"TTS request: provider={tts_provider}, voice={tts_voice}, text_len={len(reply_text)}")

    tts_result = await tts.synthesize_speech(
        text=reply_text,
        provider=tts_provider,
        voice_id=tts_voice,
        config=agent.tts_config or {},
    )

    audio_b64 = ""
    tts_error = tts_result.get("error")
    audio_data = tts_result.get("audio_data", b"")
    logger.info(f"TTS result: audio_bytes={len(audio_data) if audio_data else 0}, error={tts_error}")

    if audio_data and not tts_error:
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        logger.info(f"TTS base64 length: {len(audio_b64)}")

    await _send_json(ws, {
        "type": "agent_reply",
        "text": reply_text,
        "audio_base64": audio_b64,
        "audio_content_type": tts_result.get("content_type", "audio/mpeg"),
        "stt_ms": stt_ms,
        "llm_ms": llm_ms,
        "tts_ms": tts_result.get("duration_ms", 0),
        "tool_calls": llm_result.get("tool_calls", []),
        "tokens_used": llm_result.get("tokens_used", 0),
    })

    if done:
        pg.end_session(session.id)
        await _send_json(ws, {"type": "call_ended"})
    else:
        await _send_json(ws, {"type": "status", "status": "listening"})


async def _send_json(ws: WebSocket, data: dict):
    """Send JSON message to browser WebSocket."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception:
        pass
