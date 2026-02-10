"""Built-in HTTP/WebSocket server for VoxBridge.

Provides a FastAPI-based server that accepts inbound WebSocket connections
from telephony providers and routes them to the bridge orchestrator.
Also exposes health check and status endpoints.

Requires: pip install voxbridge[server]
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from voxbridge.bridge import VoxBridge
from voxbridge.config import BridgeConfig, load_config


def _fastapi_available() -> bool:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        return True
    except ImportError:
        return False


def create_app(config: BridgeConfig | dict | str) -> Any:
    """Create a FastAPI application with VoxBridge WebSocket endpoint.

    Args:
        config: Bridge configuration (YAML path, dict, or BridgeConfig).

    Returns:
        A FastAPI application instance.

    Requires: pip install voxbridge[server]
    """
    if not _fastapi_available():
        raise ImportError(
            "FastAPI server requires fastapi and uvicorn. "
            "Install with: pip install voxbridge[server]"
        )

    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse

    bridge_config = load_config(config)
    bridge = VoxBridge(bridge_config)

    app = FastAPI(
        title="VoxBridge",
        description="Universal telephony adapter for voice bots",
        version="0.1.0",
    )

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "active_calls": bridge.sessions.active_count})

    @app.get("/status")
    async def status():
        sessions = []
        for s in bridge.sessions.all_sessions:
            sessions.append({
                "session_id": s.session_id,
                "call_id": s.call_id,
                "provider": s.provider,
                "from_number": s.from_number,
                "to_number": s.to_number,
                "is_active": s.is_active,
                "duration_ms": s.duration_ms,
            })
        return JSONResponse({
            "provider": bridge_config.provider.type,
            "bot_url": bridge_config.bot.url,
            "active_calls": bridge.sessions.active_count,
            "sessions": sessions,
        })

    @app.get("/providers")
    async def providers():
        from voxbridge.serializers.registry import serializer_registry
        return JSONResponse({"providers": serializer_registry.available})

    @app.websocket(bridge_config.provider.listen_path)
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        logger.info(f"Provider WebSocket connected: {websocket.client}")

        from voxbridge.transports.websocket import WebSocketServerTransport

        # Wrap the FastAPI WebSocket in our transport adapter
        transport = _FastAPIWebSocketAdapter(websocket)
        try:
            await bridge._handle_provider_connection(transport)
        except WebSocketDisconnect:
            logger.info(f"Provider WebSocket disconnected: {websocket.client}")
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")

    return app


class _FastAPIWebSocketAdapter:
    """Adapter to make FastAPI's WebSocket work with VoxBridge's transport interface."""

    def __init__(self, ws):
        self._ws = ws
        self._connected = True

    async def connect(self, **kwargs):
        pass  # Already connected by FastAPI

    async def send(self, data: bytes | str):
        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        else:
            await self._ws.send_text(data)

    async def recv(self) -> bytes | str:
        msg = await self._ws.receive()
        if "text" in msg:
            return msg["text"]
        if "bytes" in msg:
            return msg["bytes"]
        raise RuntimeError("Unexpected WebSocket message type")

    async def disconnect(self):
        self._connected = False
        try:
            await self._ws.close()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._connected


def run_server(config: BridgeConfig | dict | str, host: str = None, port: int = None):
    """Run the VoxBridge server with uvicorn.

    Args:
        config: Bridge configuration.
        host: Override the listen host.
        port: Override the listen port.
    """
    if not _fastapi_available():
        raise ImportError(
            "FastAPI server requires fastapi and uvicorn. "
            "Install with: pip install voxbridge[server]"
        )

    import uvicorn

    bridge_config = load_config(config)
    app = create_app(bridge_config)

    uvicorn.run(
        app,
        host=host or bridge_config.provider.listen_host,
        port=port or bridge_config.provider.listen_port,
    )
