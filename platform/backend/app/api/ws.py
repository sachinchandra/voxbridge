"""WebSocket endpoint for real-time event streaming.

Client connects to:
    ws://host/api/v1/ws/events?token=<jwt>

On connect the server sends the last 10 events for catch-up,
then streams new events as they arrive from the event bus.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from app.services.auth import decode_token
from app.services import event_bus, ws_manager

router = APIRouter()


async def _authenticate_ws(token: str) -> str | None:
    """Validate JWT and return customer_id, or None."""
    try:
        payload = decode_token(token)
        if not payload:
            logger.warning("WS auth: token decode returned None")
            return None
        if "sub" not in payload:
            logger.warning(f"WS auth: no 'sub' in payload, keys={list(payload.keys())}")
            return None
        customer_id = payload["sub"]
        logger.info(f"WS auth: token valid for customer={customer_id}")
        return customer_id
    except Exception as e:
        logger.error(f"WS auth error: {type(e).__name__}: {e}")
        return None


@router.websocket("/ws/events")
async def websocket_events(ws: WebSocket, token: str = Query(...)):
    """Main event stream WebSocket.

    Protocol:
    - Auth via ?token=<jwt> query param
    - Server sends JSON events: { type, customer_id, payload, timestamp }
    - Client can send { "action": "ping" } for keepalive
    - Server sends { "type": "pong" } in response
    """
    # Authenticate
    customer_id = await _authenticate_ws(token)
    if not customer_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    # Accept and register
    await ws_manager.connect(ws, customer_id)
    queue = event_bus.subscribe(customer_id)

    logger.info(f"WS connected: customer={customer_id}, connections={ws_manager.connection_count(customer_id)}")

    try:
        # Send catch-up events
        recent = event_bus.get_recent_events(customer_id, limit=10)
        if recent:
            await ws_manager.send_personal(ws, {
                "type": "catchup",
                "events": recent,
            })

        # Send connected confirmation
        await ws_manager.send_personal(ws, {
            "type": "connected",
            "customer_id": customer_id,
            "connections": ws_manager.connection_count(customer_id),
        })

        # Dual loop: read from event bus + handle client messages
        async def _event_sender():
            """Forward events from bus to WebSocket."""
            try:
                while True:
                    event = await queue.get()
                    ok = await ws_manager.send_personal(ws, event)
                    if not ok:
                        break
            except asyncio.CancelledError:
                pass

        async def _client_receiver():
            """Handle incoming messages from client."""
            try:
                while True:
                    raw = await ws.receive_text()
                    try:
                        msg = json.loads(raw)
                        action = msg.get("action", "")
                        if action == "ping":
                            await ws_manager.send_personal(ws, {"type": "pong"})
                    except json.JSONDecodeError:
                        pass
            except WebSocketDisconnect:
                pass
            except Exception:
                pass

        # Run both concurrently
        sender_task = asyncio.create_task(_event_sender())
        receiver_task = asyncio.create_task(_client_receiver())

        # Wait for either to finish (usually receiver on disconnect)
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel the remaining task
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        event_bus.unsubscribe(customer_id, queue)
        ws_manager.disconnect(ws, customer_id)
        logger.info(f"WS disconnected: customer={customer_id}, remaining={ws_manager.connection_count(customer_id)}")
