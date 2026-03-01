"""Peer discovery -- tracks known peers, manages heartbeats and timeouts."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Callable, Dict, Optional, Any

from ..config import settings
from ..negotiation.capability import AgentCapabilityDocument

logger = logging.getLogger(__name__)


class PeerRegistry:
    """
    In-memory registry of discovered peers. Updated by GossipSub heartbeats.
    Peers that miss heartbeats beyond the timeout are marked stale and removed.
    """

    def __init__(self, timeout: float | None = None):
        self._timeout = timeout if timeout is not None else settings.peer_timeout
        # peer_id -> (capability_doc, last_seen_timestamp)
        self._peers: Dict[str, tuple[AgentCapabilityDocument, float]] = {}
        # Callbacks fired when peers join/leave
        self._on_join: list[Callable[[AgentCapabilityDocument], Any]] = []
        self._on_leave: list[Callable[[str], Any]] = []
        self._lock = threading.Lock()

    # -- Peer lifecycle ------------------------------------------------------

    def update(self, doc: AgentCapabilityDocument) -> bool:
        """
        Add or update a peer. Returns True if this is a newly discovered peer.
        """
        with self._lock:
            is_new = doc.peer_id not in self._peers
            self._peers[doc.peer_id] = (doc, time.monotonic())

        if is_new:
            logger.info(f"Discovered new peer: {doc.name} ({doc.peer_id[:12]}...)")
            for cb in self._on_join:
                try:
                    cb(doc)
                except Exception as exc:
                    logger.warning(f"Join callback failed: {exc}")
        return is_new

    def remove(self, peer_id: str) -> Optional[AgentCapabilityDocument]:
        """Explicitly remove a peer. Returns its doc if it existed."""
        with self._lock:
            entry = self._peers.pop(peer_id, None)

        if entry:
            doc, _ = entry
            logger.info(f"Peer left: {doc.name} ({peer_id[:12]}...)")
            for cb in self._on_leave:
                try:
                    cb(peer_id)
                except Exception as exc:
                    logger.warning(f"Leave callback failed: {exc}")
            return doc
        return None

    def prune_stale(self) -> list[str]:
        """Remove peers that haven't sent a heartbeat within the timeout."""
        now = time.monotonic()
        with self._lock:
            stale = [
                pid
                for pid, (_, last_seen) in self._peers.items()
                if (now - last_seen) > self._timeout
            ]
        for pid in stale:
            self.remove(pid)
        return stale

    # -- Queries -------------------------------------------------------------

    def get(self, peer_id: str) -> Optional[AgentCapabilityDocument]:
        with self._lock:
            entry = self._peers.get(peer_id)
        return entry[0] if entry else None

    def all_peers(self) -> list[AgentCapabilityDocument]:
        with self._lock:
            return [doc for doc, _ in self._peers.values()]

    def available_peers(self) -> list[AgentCapabilityDocument]:
        with self._lock:
            return [doc for doc, _ in self._peers.values() if doc.is_available]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._peers)

    def peer_ids(self) -> list[str]:
        with self._lock:
            return list(self._peers.keys())

    # -- Callbacks -----------------------------------------------------------

    def on_join(self, callback: Callable[[AgentCapabilityDocument], Any]) -> None:
        self._on_join.append(callback)

    def on_leave(self, callback: Callable[[str], Any]) -> None:
        self._on_leave.append(callback)

    # -- Background pruning --------------------------------------------------

    async def run_pruner(self, interval: float = 5.0) -> None:
        """Background task that periodically prunes stale peers."""
        while True:
            try:
                stale = self.prune_stale()
                if stale:
                    logger.info(f"Pruned {len(stale)} stale peer(s)")
            except Exception as exc:
                logger.error(f"Pruner error: {exc}")
            await asyncio.sleep(interval)
