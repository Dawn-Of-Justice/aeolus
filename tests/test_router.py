"""Tests for task router (escalation and tier mapping)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    ModelTierEnum,
    TaskRequirements,
)
from aeolus.tasks.router import should_escalate, tier_model


def _make_agent(
    tier: ModelTierEnum = ModelTierEnum.T1,
    capabilities: list[str] | None = None,
) -> AgentCapabilityDocument:
    return AgentCapabilityDocument(
        peer_id="test-peer",
        name="test",
        model_tier=tier,
        capabilities=capabilities or ["test"],
        capability_description="test agent",
    )


class TestTierModel:
    def test_3b_tier(self) -> None:
        model = tier_model("3B")
        assert model is not None
        assert len(model) > 0

    def test_8b_tier(self) -> None:
        model = tier_model("8B")
        assert model is not None
        assert len(model) > 0

    def test_large_tier(self) -> None:
        model = tier_model("LARGE")
        assert model is not None
        assert len(model) > 0

    def test_unknown_tier_falls_back_to_tier1(self) -> None:
        model = tier_model("UNKNOWN")
        assert model == tier_model("3B")

    def test_each_tier_maps_to_different_model(self) -> None:
        models = {tier_model("3B"), tier_model("8B"), tier_model("LARGE")}
        # At least 2 distinct models (3B and LARGE should differ)
        assert len(models) >= 2


class TestShouldEscalate:
    @pytest.mark.asyncio
    async def test_no_escalation(self) -> None:
        agent = _make_agent(ModelTierEnum.T1, ["summarisation"])
        reqs = TaskRequirements()

        with patch("aeolus.tasks.router.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_escalate": False,
                "escalate_to_tier": None,
                "reason": "Task is simple",
            }
            escalate, target = await should_escalate("summarise this", agent, reqs)

        assert escalate is False
        assert target is None

    @pytest.mark.asyncio
    async def test_escalation_needed(self) -> None:
        agent = _make_agent(ModelTierEnum.T1, ["summarisation"])
        reqs = TaskRequirements()

        with patch("aeolus.tasks.router.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_escalate": True,
                "escalate_to_tier": "LARGE",
                "reason": "Complex analysis needed",
            }
            escalate, target = await should_escalate(
                "deep security audit with multi-layer analysis", agent, reqs
            )

        assert escalate is True
        assert target == "LARGE"

    @pytest.mark.asyncio
    async def test_escalation_to_8b(self) -> None:
        agent = _make_agent(ModelTierEnum.T1, ["translation"])
        reqs = TaskRequirements()

        with patch("aeolus.tasks.router.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_escalate": True,
                "escalate_to_tier": "8B",
                "reason": "Moderately complex",
            }
            escalate, target = await should_escalate("translate long document", agent, reqs)

        assert escalate is True
        assert target == "8B"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_no_escalation(self) -> None:
        agent = _make_agent(ModelTierEnum.T1)
        reqs = TaskRequirements()

        with patch("aeolus.tasks.router.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM down")
            escalate, target = await should_escalate("anything", agent, reqs)

        assert escalate is False
        assert target is None

    @pytest.mark.asyncio
    async def test_passes_agent_context_to_llm(self) -> None:
        agent = _make_agent(ModelTierEnum.T2, ["code", "security"])
        reqs = TaskRequirements(max_latency_ms=3000)

        with patch("aeolus.tasks.router.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_escalate": False,
                "escalate_to_tier": None,
            }
            await should_escalate("review this code", agent, reqs)

        mock_llm.assert_called_once()
        call_args = mock_llm.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        user_msg = messages[1]["content"]
        assert "8B" in user_msg  # model tier value
        assert "code" in user_msg  # capability
