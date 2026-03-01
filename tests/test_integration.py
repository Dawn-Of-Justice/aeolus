"""Integration tests for the full negotiation flow.

Tests the REQUEST -> OFFER -> ACCEPT -> BIND -> RESULT pipeline
using two NegotiationEngine instances with mocked LLM.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    MessageType,
    ModelTierEnum,
    NegotiationMessage,
    NegotiationTerms,
    TaskRequirements,
)
from aeolus.negotiation.engine import NegotiationEngine
from aeolus.negotiation.sla import evaluate_hard_constraints, score_offer


def _make_agent(
    peer_id: str,
    name: str,
    capabilities: list[str],
    description: str = "",
) -> AgentCapabilityDocument:
    return AgentCapabilityDocument(
        peer_id=peer_id,
        name=name,
        model_tier=ModelTierEnum.T1,
        capabilities=capabilities,
        capability_description=description or f"Agent {name}",
    )


class TestFullNegotiationFlow:
    """End-to-end negotiation between a requester and a provider."""

    @pytest.mark.asyncio
    async def test_happy_path_request_to_result(self) -> None:
        """Full flow: REQUEST -> OFFER -> ACCEPT -> BIND -> RESULT."""
        # Set up two agents
        requester_agent = _make_agent("requester-1", "alice", ["orchestration"])
        provider_agent = _make_agent("provider-1", "bob", ["summarisation", "text"])

        requester_engine = NegotiationEngine(requester_agent)
        provider_engine = NegotiationEngine(provider_agent)

        # Step 1: Requester creates a REQUEST
        request = NegotiationMessage(
            type=MessageType.REQUEST,
            task_id="integration-task-1",
            from_agent="requester-1",
            task_description="summarise this article about AI safety",
            requirements=TaskRequirements(max_latency_ms=5000, min_quality=0.7),
        )

        # Step 2: Provider evaluates REQUEST and produces OFFER
        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.9,
                "estimated_latency_ms": 2000,
                "quality_score": 0.85,
                "reasoning": "Strong match for text summarisation",
            }
            offer = await provider_engine.evaluate_request(request)

        assert offer is not None
        assert offer.type == MessageType.OFFER
        assert offer.from_agent == "provider-1"
        assert offer.to_agent == "requester-1"

        # Step 3: Requester evaluates OFFER and produces ACCEPT
        response = await requester_engine.evaluate_offer(
            offer, request.requirements
        )
        assert response.type == MessageType.ACCEPT
        assert response.binding_terms is not None

        # Step 4: Provider receives BIND (simulated from ACCEPT)
        bind = NegotiationMessage(
            type=MessageType.BIND,
            task_id="integration-task-1",
            from_agent="requester-1",
            to_agent="provider-1",
            binding_terms=response.binding_terms,
            confirmation=True,
        )

        with patch("aeolus.tasks.executor.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "AI safety is a field focused on ensuring advanced AI systems remain beneficial and aligned with human values."
            result = await provider_engine.handle_bind(bind)

        # Step 5: Verify RESULT
        assert result.type == MessageType.RESULT
        assert result.success is True
        assert result.output is not None
        assert len(result.output) > 0
        assert result.from_agent == "provider-1"
        assert result.to_agent == "requester-1"

    @pytest.mark.asyncio
    async def test_counter_offer_flow(self) -> None:
        """Flow where the offer doesn't meet requirements and gets countered."""
        requester_agent = _make_agent("requester-1", "alice", ["orchestration"])
        provider_agent = _make_agent("provider-1", "bob", ["summarisation"])

        requester_engine = NegotiationEngine(requester_agent)
        provider_engine = NegotiationEngine(provider_agent)

        # Strict requirements
        requirements = TaskRequirements(max_latency_ms=1000, min_quality=0.9)

        request = NegotiationMessage(
            type=MessageType.REQUEST,
            task_id="counter-task-1",
            from_agent="requester-1",
            task_description="summarise this text quickly",
            requirements=requirements,
        )

        # Provider offers terms that don't meet strict requirements
        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.8,
                "estimated_latency_ms": 3000,  # Too slow
                "quality_score": 0.75,  # Too low
                "reasoning": "Can handle but not at required SLA",
            }
            offer = await provider_engine.evaluate_request(request)

        assert offer is not None

        # Requester evaluates and issues COUNTER
        response = await requester_engine.evaluate_offer(offer, requirements)
        assert response.type == MessageType.COUNTER
        assert response.reason is not None
        assert response.adjusted_terms is not None

    @pytest.mark.asyncio
    async def test_provider_declines_when_overloaded(self) -> None:
        """Provider at capacity should decline the request."""
        provider_agent = _make_agent("provider-1", "bob", ["summarisation"])
        provider_agent.current_load = provider_agent.max_concurrent_tasks

        provider_engine = NegotiationEngine(provider_agent)

        request = NegotiationMessage(
            type=MessageType.REQUEST,
            task_id="decline-task-1",
            from_agent="requester-1",
            task_description="summarise this text",
            requirements=TaskRequirements(),
        )

        offer = await provider_engine.evaluate_request(request)
        assert offer is None

    @pytest.mark.asyncio
    async def test_multiple_providers_best_offer_wins(self) -> None:
        """When multiple providers offer, the requester should accept the best one."""
        requester_agent = _make_agent("requester-1", "alice", ["orchestration"])
        provider_a = _make_agent("provider-a", "bob", ["summarisation"])
        provider_b = _make_agent("provider-b", "carol", ["summarisation", "analysis"])

        requester_engine = NegotiationEngine(requester_agent)
        engine_a = NegotiationEngine(provider_a)
        engine_b = NegotiationEngine(provider_b)

        request = NegotiationMessage(
            type=MessageType.REQUEST,
            task_id="multi-task-1",
            from_agent="requester-1",
            task_description="summarise this research paper on LLMs",
            requirements=TaskRequirements(max_latency_ms=5000, min_quality=0.7),
        )

        # Provider A: mediocre offer
        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.6,
                "estimated_latency_ms": 4000,
                "quality_score": 0.75,
            }
            offer_a = await engine_a.evaluate_request(request)

        # Provider B: better offer
        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.95,
                "estimated_latency_ms": 1500,
                "quality_score": 0.92,
            }
            offer_b = await engine_b.evaluate_request(request)

        assert offer_a is not None
        assert offer_b is not None

        # Score both offers using SLA
        requirements = request.requirements
        score_a = score_offer(requirements, offer_a.terms)
        score_b = score_offer(requirements, offer_b.terms)
        assert score_b > score_a  # B should score higher

        # Requester should accept both (they both meet constraints)
        response_a = await requester_engine.evaluate_offer(offer_a, requirements)
        response_b = await requester_engine.evaluate_offer(offer_b, requirements)
        assert response_a.type == MessageType.ACCEPT
        assert response_b.type == MessageType.ACCEPT


class TestSLAIntegration:
    """Tests that SLA evaluation integrates correctly with negotiation messages."""

    def test_hard_constraints_with_negotiation_terms(self) -> None:
        req = TaskRequirements(max_latency_ms=3000, min_quality=0.8, priority=7)
        terms = NegotiationTerms(
            estimated_latency_ms=2500,
            quality_score=0.85,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is True
        score = score_offer(req, terms)
        assert 0.0 < score < 1.0

    def test_violated_constraints_produce_useful_messages(self) -> None:
        req = TaskRequirements(max_latency_ms=1000, min_quality=0.9)
        terms = NegotiationTerms(
            estimated_latency_ms=5000,
            quality_score=0.5,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is False
        assert len(violations) == 2
        # Violations should be human-readable
        for v in violations:
            assert isinstance(v, str)
            assert len(v) > 10
