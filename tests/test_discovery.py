"""Tests for peer discovery registry."""
from __future__ import annotations

import time

from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    ModelTierEnum,
)
from aeolus.network.discovery import PeerRegistry


def _make_doc(
    peer_id: str, name: str, status: AgentStatus = AgentStatus.AVAILABLE
) -> AgentCapabilityDocument:
    return AgentCapabilityDocument(
        peer_id=peer_id,
        name=name,
        status=status,
        model_tier=ModelTierEnum.T1,
        capabilities=["test"],
        capability_description="test agent",
    )


class TestPeerRegistry:
    def test_add_new_peer(self) -> None:
        reg = PeerRegistry()
        doc = _make_doc("peer-1", "alpha")
        assert reg.update(doc) is True
        assert reg.count == 1
        assert reg.get("peer-1") is not None

    def test_update_existing_peer(self) -> None:
        reg = PeerRegistry()
        doc = _make_doc("peer-1", "alpha")
        reg.update(doc)
        assert reg.update(doc) is False
        assert reg.count == 1

    def test_remove_peer(self) -> None:
        reg = PeerRegistry()
        reg.update(_make_doc("peer-1", "alpha"))
        removed = reg.remove("peer-1")
        assert removed is not None
        assert removed.name == "alpha"
        assert reg.count == 0

    def test_remove_nonexistent(self) -> None:
        reg = PeerRegistry()
        assert reg.remove("nope") is None

    def test_available_peers(self) -> None:
        reg = PeerRegistry()
        reg.update(_make_doc("p1", "a", AgentStatus.AVAILABLE))
        reg.update(_make_doc("p2", "b", AgentStatus.BUSY))
        reg.update(_make_doc("p3", "c", AgentStatus.AVAILABLE))
        assert len(reg.available_peers()) == 2

    def test_all_peers(self) -> None:
        reg = PeerRegistry()
        reg.update(_make_doc("p1", "a"))
        reg.update(_make_doc("p2", "b"))
        assert len(reg.all_peers()) == 2

    def test_peer_ids(self) -> None:
        reg = PeerRegistry()
        reg.update(_make_doc("p1", "a"))
        reg.update(_make_doc("p2", "b"))
        assert sorted(reg.peer_ids()) == ["p1", "p2"]

    def test_prune_stale(self) -> None:
        reg = PeerRegistry(timeout=0.1)
        reg.update(_make_doc("p1", "a"))
        time.sleep(0.2)
        stale = reg.prune_stale()
        assert "p1" in stale
        assert reg.count == 0

    def test_prune_keeps_fresh(self) -> None:
        reg = PeerRegistry(timeout=10.0)
        reg.update(_make_doc("p1", "a"))
        stale = reg.prune_stale()
        assert stale == []
        assert reg.count == 1

    def test_callbacks(self) -> None:
        reg = PeerRegistry()
        joined: list[str] = []
        left: list[str] = []
        reg.on_join(lambda doc: joined.append(doc.peer_id))
        reg.on_leave(lambda pid: left.append(pid))

        reg.update(_make_doc("p1", "a"))
        assert joined == ["p1"]

        reg.remove("p1")
        assert left == ["p1"]

    def test_callback_error_does_not_break_update(self) -> None:
        reg = PeerRegistry()
        reg.on_join(lambda doc: (_ for _ in ()).throw(RuntimeError("boom")))
        # Should not raise
        reg.update(_make_doc("p1", "a"))
        assert reg.count == 1

    def test_get_returns_doc_not_tuple(self) -> None:
        reg = PeerRegistry()
        doc = _make_doc("p1", "a")
        reg.update(doc)
        retrieved = reg.get("p1")
        assert isinstance(retrieved, AgentCapabilityDocument)
        assert retrieved.name == "a"

    def test_get_nonexistent(self) -> None:
        reg = PeerRegistry()
        assert reg.get("nope") is None
