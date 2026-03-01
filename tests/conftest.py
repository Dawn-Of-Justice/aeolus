"""Shared test fixtures for the Aeolus test suite."""
from __future__ import annotations

import pytest

from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    MessageType,
    ModelTierEnum,
    NegotiationMessage,
    NegotiationTerms,
    TaskRequirements,
)


@pytest.fixture
def make_agent():
    """Factory fixture for creating AgentCapabilityDocuments."""
    def _make(
        peer_id: str = "test-peer",
        name: str = "test-agent",
        tier: ModelTierEnum = ModelTierEnum.T1,
        capabilities: list[str] | None = None,
        description: str = "A test agent",
        status: AgentStatus = AgentStatus.AVAILABLE,
        current_load: int = 0,
        max_concurrent: int = 2,
    ) -> AgentCapabilityDocument:
        return AgentCapabilityDocument(
            peer_id=peer_id,
            name=name,
            model_tier=tier,
            capabilities=capabilities or ["test"],
            capability_description=description,
            status=status,
            current_load=current_load,
            max_concurrent_tasks=max_concurrent,
        )
    return _make


@pytest.fixture
def make_request():
    """Factory for creating REQUEST messages."""
    def _make(
        from_agent: str = "requester-1",
        task_id: str = "task-1",
        description: str = "summarise this text",
        requirements: TaskRequirements | None = None,
    ) -> NegotiationMessage:
        return NegotiationMessage(
            type=MessageType.REQUEST,
            task_id=task_id,
            from_agent=from_agent,
            task_description=description,
            requirements=requirements or TaskRequirements(),
        )
    return _make


@pytest.fixture
def sample_requirements():
    """Default TaskRequirements for tests."""
    return TaskRequirements(max_latency_ms=5000, min_quality=0.7, priority=5)
