"""WebSocket transport for VoxBridge.

Provides both client (outbound) and server (inbound) WebSocket transports
using the ``websockets`` library with asyncio.
"""

from __future__ import annotations

import asyncio
from typing import Any

import websockets
import websockets.asyncio.client
import websockets.asyncio.server
from loguru import logger

from voxbridge.transports.base import BaseTransport


class WebSocketClientTransport(BaseTransport):
    """WebSocket client transport for connecting to a remote endpoint.

    Used for the bot-side connection: VoxBridge connects as a client
    to the voice bot's WebSocket server.
    """

    def __init__(self, url: str | None = None, **ws_kwargs: Any) -> None:
        self._url = url
        self._ws: Any | None = None
        self._ws_kwargs = ws_kwargs

    async def connect(self, **kwargs) -> None:
        url = kwargs.get("url", self._url)
        if not url:
            raise ValueError("WebSocket URL is required")
        self._url = url
        logger.info(f"Connecting to WebSocket: {url}")
        self._ws = await websockets.asyncio.client.connect(
            url,
            **self._ws_kwargs,
        )
        logger.info(f"Connected to {url}")

    async def send(self, data: bytes | str) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(data)

    async def recv(self) -> bytes | str:
        if not self._ws:
            raise RuntimeError("Not connected")
        return await self._ws.recv()

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("WebSocket client disconnected")

    def is_connected(self) -> bool:
        return self._ws is not None and self._ws.open


class WebSocketServerTransport(BaseTransport):
    """WebSocket server transport that wraps an already-accepted connection.

    Used for the provider-side connection: the telephony provider connects
    to VoxBridge's server, and this transport wraps that accepted WebSocket.
    """

    def __init__(self, websocket: Any = None) -> None:
        self._ws = websocket

    async def connect(self, **kwargs) -> None:
        ws = kwargs.get("websocket")
        if ws:
            self._ws = ws
        if not self._ws:
            raise ValueError("An accepted WebSocket connection is required")
        logger.info("Provider WebSocket connection accepted")

    async def send(self, data: bytes | str) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(data)

    async def recv(self) -> bytes | str:
        if not self._ws:
            raise RuntimeError("Not connected")
        return await self._ws.recv()

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            logger.info("Provider WebSocket disconnected")

    def is_connected(self) -> bool:
        return self._ws is not None and self._ws.open


class WebSocketServer:
    """Standalone WebSocket server that accepts provider connections.

    Runs a ``websockets`` server and dispatches each new connection
    to a handler callback. The callback receives a ``WebSocketServerTransport``
    wrapping the accepted connection.

    Usage:
        async def on_connection(transport: WebSocketServerTransport):
            # handle the connection
            ...

        server = WebSocketServer(host="0.0.0.0", port=8765, handler=on_connection)
        await server.start()
        # ... later
        await server.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        path: str = "/",
        handler=None,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self._handler = handler
        self._server: Any = None

    async def _ws_handler(self, websocket) -> None:
        """Internal handler for each accepted WebSocket connection."""
        # Check path if specified
        if self.path and self.path != "/":
            request_path = getattr(websocket, "path", "/") or "/"
            if not request_path.startswith(self.path):
                logger.warning(f"Rejected connection to {request_path} (expected {self.path})")
                return

        transport = WebSocketServerTransport(websocket=websocket)
        if self._handler:
            try:
                await self._handler(transport)
            except Exception as e:
                logger.error(f"Handler error: {e}")
        else:
            logger.warning("No handler registered for incoming connections")

    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}{self.path}")
        self._server = await websockets.asyncio.server.serve(
            self._ws_handler,
            self.host,
            self.port,
        )
        logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}{self.path}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("WebSocket server stopped")

    async def serve_forever(self) -> None:
        """Start and run the server until cancelled."""
        await self.start()
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            await self.stop()
