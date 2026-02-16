"""WebSocket transport for VoxBridge.

Provides both client (outbound) and server (inbound) WebSocket transports
using the ``websockets`` library with asyncio.

When an ``http_handler`` is provided, the server uses ``aiohttp`` instead
of plain ``websockets`` so that HTTP POST requests (e.g. Twilio TwiML
webhooks) can be served on the **same** port as the WebSocket endpoint.
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

    When ``http_handler`` is provided, the server uses ``aiohttp`` instead
    of the plain ``websockets`` library so that both HTTP and WebSocket
    traffic can be served on the **same** port.  This is useful for
    serving Twilio TwiML webhooks alongside the Media Stream WebSocket
    with a single ngrok tunnel.

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
        http_handler=None,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self._handler = handler
        self._http_handler = http_handler
        self._server: Any = None
        self._runner: Any = None  # aiohttp runner (hybrid mode only)

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

    # ------------------------------------------------------------------
    # aiohttp hybrid mode — HTTP + WebSocket on one port
    # ------------------------------------------------------------------

    async def _aiohttp_ws_handler(self, request):
        """Handle WebSocket upgrade requests via aiohttp."""
        import aiohttp.web as aioweb

        ws = aioweb.WebSocketResponse()
        await ws.prepare(request)

        # Wrap aiohttp WS in a shim so VoxBridge can use it
        shim = _AiohttpWebSocketShim(ws)
        transport = WebSocketServerTransport(websocket=shim)
        if self._handler:
            try:
                await self._handler(transport)
            except Exception as e:
                logger.error(f"Handler error: {e}")
        return ws

    async def _aiohttp_http_handler(self, request):
        """Handle plain HTTP requests via the user-supplied http_handler."""
        import aiohttp.web as aioweb

        if self._http_handler:
            try:
                status, content_type, body = await self._http_handler(request)
                return aioweb.Response(
                    status=status,
                    body=body,
                    content_type=content_type,
                )
            except Exception as e:
                logger.error(f"HTTP handler error: {e}")
                return aioweb.Response(status=500, text="Internal Server Error")
        return aioweb.Response(status=404, text="Not Found")

    async def _start_hybrid(self) -> None:
        """Start an aiohttp server that handles both HTTP and WebSocket."""
        import aiohttp.web as aioweb

        app = aioweb.Application()

        # Register all HTTP routes via a catch-all that checks for WS upgrade
        app.router.add_route("*", "/{path_info:.*}", self._aiohttp_route_handler)

        self._runner = aioweb.AppRunner(app)
        await self._runner.setup()
        site = aioweb.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(
            f"Hybrid HTTP+WebSocket server listening on "
            f"http://{self.host}:{self.port}"
        )

    async def _aiohttp_route_handler(self, request):
        """Route handler: upgrade to WS if requested, else serve HTTP."""
        import aiohttp.web as aioweb

        # Check if it's a WebSocket upgrade
        if (
            request.headers.get("Upgrade", "").lower() == "websocket"
            or request.headers.get("Connection", "").lower() == "upgrade"
        ):
            return await self._aiohttp_ws_handler(request)

        # Plain HTTP — delegate to http_handler
        return await self._aiohttp_http_handler(request)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server."""
        if self._http_handler:
            logger.info(
                f"Starting hybrid HTTP+WS server on "
                f"{self.host}:{self.port}{self.path}"
            )
            await self._start_hybrid()
        else:
            logger.info(
                f"Starting WebSocket server on "
                f"{self.host}:{self.port}{self.path}"
            )
            self._server = await websockets.asyncio.server.serve(
                self._ws_handler,
                self.host,
                self.port,
            )
            logger.info(
                f"WebSocket server listening on "
                f"ws://{self.host}:{self.port}{self.path}"
            )

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Hybrid server stopped")
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("WebSocket server stopped")

    async def serve_forever(self) -> None:
        """Start and run the server until cancelled."""
        await self.start()
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            await self.stop()


class _AiohttpWebSocketShim:
    """Thin shim that makes an ``aiohttp.WebSocketResponse`` look like a
    ``websockets`` server connection so that :class:`WebSocketServerTransport`
    can use it unchanged.
    """

    def __init__(self, ws) -> None:
        self._ws = ws
        self.open = True

    async def send(self, data: bytes | str) -> None:
        if isinstance(data, bytes):
            await self._ws.send_bytes(data)
        else:
            await self._ws.send_str(data)

    async def recv(self) -> bytes | str:
        import aiohttp

        msg = await self._ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data
        elif msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data
        elif msg.type in (
            aiohttp.WSMsgType.CLOSE,
            aiohttp.WSMsgType.CLOSING,
            aiohttp.WSMsgType.CLOSED,
        ):
            self.open = False
            raise websockets.exceptions.ConnectionClosed(None, None)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            self.open = False
            raise websockets.exceptions.ConnectionClosed(None, None)
        return msg.data

    async def close(self) -> None:
        self.open = False
        await self._ws.close()
