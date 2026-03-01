"""
aeolus/network/transport_base.py
Abstract base class for Aeolus transport layer.
Allows swapping NATS for other transports (libp2p, WebSocket, mock for tests).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine


# Callback type: receives (topic, data_bytes)
MessageHandler = Callable[[str, bytes], Coroutine[Any, Any, None]]


class Transport(ABC):
    """Abstract transport interface for Aeolus agent communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the transport backend."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect, draining any pending messages."""

    @abstractmethod
    async def subscribe(self, topic: str, callback: MessageHandler) -> None:
        """Subscribe to a topic with an async callback handler."""

    @abstractmethod
    async def publish(self, topic: str, data: bytes) -> None:
        """Publish data to a topic."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport is currently connected."""
