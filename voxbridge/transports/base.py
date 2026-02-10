"""Base transport interface for VoxBridge.

Transports handle the raw I/O connection lifecycle (WebSocket or SIP).
They are responsible for connecting, sending, receiving, and disconnecting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseTransport(ABC):
    """Abstract base class for transport connections.

    Transports manage the network connection to either the telephony provider
    or the voice bot. They handle connection lifecycle and raw message I/O.
    """

    @abstractmethod
    async def connect(self, **kwargs) -> None:
        """Establish the transport connection.

        Args:
            **kwargs: Transport-specific connection parameters.
        """
        ...

    @abstractmethod
    async def send(self, data: bytes | str) -> None:
        """Send data over the transport.

        Args:
            data: Raw bytes or string to send.
        """
        ...

    @abstractmethod
    async def recv(self) -> bytes | str:
        """Receive the next message from the transport.

        Returns:
            Raw bytes or string received.

        Raises:
            ConnectionClosed: If the connection is closed.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the transport connection gracefully."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the transport is currently connected."""
        ...

    async def __aiter__(self) -> AsyncIterator[bytes | str]:
        """Iterate over incoming messages."""
        while self.is_connected():
            try:
                msg = await self.recv()
                yield msg
            except Exception:
                break
