"""NATS-based messaging transport (primary for hackathon; fallback for py-libp2p).

Provides GossipSub-like pub/sub semantics over NATS. Each agent subscribes
to the capability broadcast topic and a direct-message inbox topic.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# Type for message handler callbacks
MessageHandler = Callable[[str, bytes], Coroutine[Any, Any, None]]


class NatsTransport:
    """
    Thin wrapper around NATS pub/sub for Aeolus messaging.

    Topics:
      - GOSSIP_TOPIC       — capability document broadcasts (all agents subscribe)
      - NEGOTIATE_TOPIC     — negotiation messages (broadcast, agents filter by to_peer)
      - TASK_TOPIC_PREFIX.{peer_id} — direct messages to a specific peer
    """

    def __init__(self, nats_url: str | None = None):
        self._url = nats_url or settings.nats_url
        self._nc: Any = None  # nats.aio.client.Client
        self._subscriptions: list[Any] = []
        self._handlers: dict[str, list[MessageHandler]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the NATS server."""
        try:
            import nats  # type: ignore
            self._nc = await nats.connect(self._url)
            logger.info(f"Connected to NATS at {self._url}")
        except ImportError:
            logger.error(
                "nats-py not installed. Run: pip install nats-py"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to connect to NATS at {self._url}: {e}")
            raise

    async def disconnect(self) -> None:
        """Drain subscriptions and disconnect."""
        if self._nc:
            try:
                await self._nc.drain()
            except Exception:
                pass
            logger.info("Disconnected from NATS")

    @property
    def is_connected(self) -> bool:
        return self._nc is not None and self._nc.is_connected

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to a topic with a callback handler."""
        if not self._nc:
            raise RuntimeError("Not connected to NATS")

        async def _cb(msg: Any) -> None:
            await handler(msg.subject, msg.data)

        sub = await self._nc.subscribe(topic, cb=_cb)
        self._subscriptions.append(sub)
        self._handlers.setdefault(topic, []).append(handler)
        logger.debug(f"Subscribed to {topic}")

    async def subscribe_direct(self, peer_id: str, handler: MessageHandler) -> None:
        """Subscribe to the direct-message inbox for a specific peer."""
        topic = f"{settings.negotiation_topic_prefix}.direct.{peer_id}"
        await self.subscribe(topic, handler)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, topic: str, data: bytes | str) -> None:
        """Publish a message to a topic."""
        if not self._nc:
            raise RuntimeError("Not connected to NATS")
        if isinstance(data, str):
            data = data.encode()
        await self._nc.publish(topic, data)
        logger.debug(f"Published {len(data)} bytes to {topic}")

    async def publish_capability(self, doc_json: str) -> None:
        """Broadcast an Agent Capability Document."""
        await self.publish(settings.capability_topic, doc_json)

    async def publish_negotiation(self, msg_json: str) -> None:
        """Broadcast a negotiation message."""
        await self.publish(settings.negotiation_topic_prefix, msg_json)

    async def publish_direct(self, peer_id: str, data: str) -> None:
        """Send a direct message to a specific peer."""
        topic = f"{settings.negotiation_topic_prefix}.direct.{peer_id}"
        await self.publish(topic, data)
