"""Twilio webhook handlers for inbound/outbound call routing.

These endpoints receive webhooks from Twilio when:
- An inbound call arrives on a provisioned phone number
- A call status changes (ringing, in-progress, completed, failed)

The inbound handler routes the call to the correct AI agent based on
which phone number was called, then returns TwiML to connect to
a WebSocket stream for the VoxBridge pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from loguru import logger

from app.config import settings
from app.services.database import (
    create_call,
    get_agent,
    get_call,
    get_phone_number_by_number,
)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ──────────────────────────────────────────────────────────────────
# Inbound Call Webhook
# ──────────────────────────────────────────────────────────────────

@router.post("/twilio/inbound")
async def handle_inbound_call(
    request: Request,
    CallSid: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
    CallStatus: str = Form(""),
    Direction: str = Form("inbound"),
    AccountSid: str = Form(""),
):
    """Handle an inbound call from Twilio.

    Flow:
    1. Look up which phone number was called (To)
    2. Find the agent assigned to that number
    3. Create a call record
    4. Return TwiML that connects to a WebSocket stream
       where the VoxBridge pipeline handles the AI conversation

    Returns TwiML XML response.
    """
    logger.info(f"Inbound call: {CallSid} from {From} to {To}")

    # 1. Look up the phone number record
    phone = get_phone_number_by_number(To)
    if not phone:
        logger.warning(f"No phone number record for {To}")
        return _twiml_reject("This number is not configured.")

    # 2. Find the assigned agent
    if not phone.agent_id:
        logger.warning(f"Phone {To} has no agent assigned")
        return _twiml_reject("This number is not assigned to an agent.")

    agent = get_agent(phone.agent_id, phone.customer_id)
    if not agent:
        logger.error(f"Agent {phone.agent_id} not found for phone {To}")
        return _twiml_reject("Agent configuration error.")

    if agent.status != "active":
        logger.warning(f"Agent {agent.id} ({agent.name}) is not active (status: {agent.status})")
        return _twiml_reject("This agent is currently unavailable.")

    # 3. Create a call record in the database
    call = create_call({
        "customer_id": phone.customer_id,
        "agent_id": agent.id,
        "phone_number_id": phone.id,
        "direction": "inbound",
        "from_number": From,
        "to_number": To,
        "status": "ringing",
        "metadata": {
            "twilio_call_sid": CallSid,
            "twilio_account_sid": AccountSid,
        },
    })

    logger.info(
        f"Call record created: {call.id} | Agent: {agent.name} | From: {From}"
    )

    # 4. Return TwiML to connect to WebSocket stream
    # The WebSocket URL includes the call_id and agent_id for the pipeline
    ws_base = settings.twilio_webhook_base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_base}/api/v1/ws/call/{call.id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="call_id" value="{call.id}" />
            <Parameter name="agent_id" value="{agent.id}" />
            <Parameter name="customer_id" value="{phone.customer_id}" />
            <Parameter name="from_number" value="{From}" />
            <Parameter name="to_number" value="{To}" />
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# ──────────────────────────────────────────────────────────────────
# Call Status Webhook
# ──────────────────────────────────────────────────────────────────

@router.post("/twilio/status")
async def handle_call_status(
    request: Request,
    CallSid: str = Form(""),
    CallStatus: str = Form(""),
    CallDuration: str = Form("0"),
    From: str = Form(""),
    To: str = Form(""),
):
    """Handle call status updates from Twilio.

    Twilio sends status callbacks when a call transitions:
    initiated → ringing → in-progress → completed/failed/busy/no-answer

    We update the call record in the database with final status and duration.
    """
    logger.info(f"Call status update: {CallSid} → {CallStatus} (duration: {CallDuration}s)")

    # Map Twilio status to our CallStatus enum
    status_map = {
        "initiated": "initiated",
        "ringing": "ringing",
        "in-progress": "in_progress",
        "completed": "completed",
        "failed": "failed",
        "busy": "busy",
        "no-answer": "no_answer",
        "canceled": "failed",
    }

    mapped_status = status_map.get(CallStatus, CallStatus)
    duration = int(CallDuration) if CallDuration else 0

    # Find the call by Twilio SID in metadata
    # For now, log the update — the WebSocket handler will manage the
    # call record lifecycle in real-time
    logger.info(
        f"Status callback: SID={CallSid}, status={mapped_status}, "
        f"duration={duration}s, from={From}, to={To}"
    )

    # Return 200 OK to acknowledge the webhook
    return {"status": "received"}


# ──────────────────────────────────────────────────────────────────
# Helper: TwiML rejection response
# ──────────────────────────────────────────────────────────────────

def _twiml_reject(message: str) -> Response:
    """Return a TwiML response that says a message and hangs up."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">{message}</Say>
    <Hangup />
</Response>"""
    return Response(content=twiml, media_type="application/xml")
