"""Tests for the negotiation engine."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aeolus.exceptions import NegotiationError, TaskExecutionError
from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    MessageType,
    ModelTierEnum,
    NegotiationMessage,
    NegotiationTerms,
    TaskRequirements,
)
from aeolus.negotiation.engine import NegotiationEngine


def _make_agent(
    peer_id: str = "provider-1",
    name: str = "alpha",
    capabilities: list[str] | None = None,
    description: str = "text summarisation agent",
    current_load: int = 0,
    max_concurrent: int = 2,
) -> AgentCapabilityDocument:
    return AgentCapabilityDocument(
        peer_id=peer_id,
        name=name,
        model_tier=ModelTierEnum.T1,
        capabilities=capabilities or ["text", "summarisation"],
        capability_description=description,
        current_load=current_load,
        max_concurrent_tasks=max_concurrent,
    )


def _make_request(
    from_agent: str = "requester-1",
    task_id: str = "task-1",
    description: str = "summarise this text",
) -> NegotiationMessage:
    return NegotiationMessage(
        type=MessageType.REQUEST,
        task_id=task_id,
        from_agent=from_agent,
        task_description=description,
        requirements=TaskRequirements(),
    )


# -- evaluate_request ---------------------------------------------------------

class TestEvaluateRequest:
    @pytest.mark.asyncio
    async def test_returns_offer_when_llm_says_yes(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)
        request = _make_request()

        mock_response = {
            "should_offer": True,
            "match_score": 0.85,
            "estimated_latency_ms": 3000,
            "quality_score": 0.9,
            "reasoning": "Good match",
        }

        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            offer = await engine.evaluate_request(request)

        assert offer is not None
        assert offer.type == MessageType.OFFER
        assert offer.from_agent == "provider-1"
        assert offer.to_agent == "requester-1"
        assert offer.task_id == "task-1"
        assert offer.match_score == 0.85
        assert offer.terms is not None
        assert offer.terms.estimated_latency_ms == 3000
        assert offer.terms.quality_score == 0.9

    @pytest.mark.asyncio
    async def test_returns_none_when_llm_declines(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)
        request = _make_request()

        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"should_offer": False, "match_score": 0.2}
            offer = await engine.evaluate_request(request)

        assert offer is None

    @pytest.mark.asyncio
    async def test_returns_none_when_overloaded(self) -> None:
        agent = _make_agent(current_load=2, max_concurrent=2)
        engine = NegotiationEngine(agent)
        request = _make_request()

        offer = await engine.evaluate_request(request)
        assert offer is None

    @pytest.mark.asyncio
    async def test_returns_none_on_llm_error(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)
        request = _make_request()

        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM down")
            offer = await engine.evaluate_request(request)

        assert offer is None

    @pytest.mark.asyncio
    async def test_stores_active_negotiation(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)
        request = _make_request()

        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.8,
                "estimated_latency_ms": 2000,
                "quality_score": 0.8,
            }
            await engine.evaluate_request(request)

        assert "task-1" in engine._active
        assert engine._active["task-1"]["role"] == "provider"

    @pytest.mark.asyncio
    async def test_offer_contains_model_name(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)
        request = _make_request()

        with patch("aeolus.negotiation.engine.llm.complete_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "should_offer": True,
                "match_score": 0.9,
                "estimated_latency_ms": 1000,
                "quality_score": 0.95,
            }
            offer = await engine.evaluate_request(request)

        assert offer is not None
        assert offer.terms.model_name == agent.model_name


# -- evaluate_offer -----------------------------------------------------------

class TestEvaluateOffer:
    @pytest.mark.asyncio
    async def test_accepts_when_constraints_met(self) -> None:
        agent = _make_agent(peer_id="requester-1")
        engine = NegotiationEngine(agent)
        requirements = TaskRequirements(max_latency_ms=5000, min_quality=0.7)

        offer = NegotiationMessage(
            type=MessageType.OFFER,
            task_id="task-1",
            from_agent="provider-1",
            to_agent="requester-1",
            match_score=0.9,
            terms=NegotiationTerms(
                estimated_latency_ms=2000,
                quality_score=0.85,
                model_name="ministral-3b-latest",
            ),
        )

        response = await engine.evaluate_offer(offer, requirements)
        assert response.type == MessageType.ACCEPT
        assert response.to_agent == "provider-1"
        assert response.binding_terms is not None

    @pytest.mark.asyncio
    async def test_counters_when_latency_exceeds(self) -> None:
        agent = _make_agent(peer_id="requester-1")
        engine = NegotiationEngine(agent)
        requirements = TaskRequirements(max_latency_ms=1000, min_quality=0.7)

        offer = NegotiationMessage(
            type=MessageType.OFFER,
            task_id="task-1",
            from_agent="provider-1",
            to_agent="requester-1",
            terms=NegotiationTerms(
                estimated_latency_ms=3000,
                quality_score=0.85,
                model_name="ministral-3b-latest",
            ),
        )

        response = await engine.evaluate_offer(offer, requirements)
        assert response.type == MessageType.COUNTER
        assert "Latency" in response.reason

    @pytest.mark.asyncio
    async def test_counters_when_quality_too_low(self) -> None:
        agent = _make_agent(peer_id="requester-1")
        engine = NegotiationEngine(agent)
        requirements = TaskRequirements(max_latency_ms=5000, min_quality=0.9)

        offer = NegotiationMessage(
            type=MessageType.OFFER,
            task_id="task-1",
            from_agent="provider-1",
            to_agent="requester-1",
            terms=NegotiationTerms(
                estimated_latency_ms=2000,
                quality_score=0.5,
                model_name="ministral-3b-latest",
            ),
        )

        response = await engine.evaluate_offer(offer, requirements)
        assert response.type == MessageType.COUNTER
        assert "Quality" in response.reason

    @pytest.mark.asyncio
    async def test_accepts_exact_boundary(self) -> None:
        agent = _make_agent(peer_id="requester-1")
        engine = NegotiationEngine(agent)
        requirements = TaskRequirements(max_latency_ms=2000, min_quality=0.7)

        offer = NegotiationMessage(
            type=MessageType.OFFER,
            task_id="task-1",
            from_agent="provider-1",
            to_agent="requester-1",
            terms=NegotiationTerms(
                estimated_latency_ms=2000,
                quality_score=0.7,
                model_name="ministral-3b-latest",
            ),
        )

        response = await engine.evaluate_offer(offer, requirements)
        assert response.type == MessageType.ACCEPT


# -- handle_bind --------------------------------------------------------------

class TestHandleBind:
    @pytest.mark.asyncio
    async def test_raises_on_unknown_task(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)

        bind = NegotiationMessage(
            type=MessageType.BIND,
            task_id="unknown-task",
            from_agent="requester-1",
            to_agent="provider-1",
        )

        with pytest.raises(NegotiationError, match="Unknown task_id"):
            await engine.handle_bind(bind)

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)

        request = _make_request()
        engine._active["task-1"] = {
            "role": "provider",
            "state": "offered",
            "request": request,
        }

        bind = NegotiationMessage(
            type=MessageType.BIND,
            task_id="task-1",
            from_agent="requester-1",
            to_agent="provider-1",
        )

        with patch("aeolus.tasks.executor.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Task completed successfully"
            result = await engine.handle_bind(bind)

        assert result.type == MessageType.RESULT
        assert result.success is True
        assert result.output == "Task completed successfully"
        assert "task-1" not in engine._active

    @pytest.mark.asyncio
    async def test_raises_execution_error(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)

        request = _make_request()
        engine._active["task-1"] = {
            "role": "provider",
            "state": "offered",
            "request": request,
        }

        bind = NegotiationMessage(
            type=MessageType.BIND,
            task_id="task-1",
            from_agent="requester-1",
            to_agent="provider-1",
        )

        with patch("aeolus.tasks.executor.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("Execution crashed")
            with pytest.raises(TaskExecutionError, match="execution failed"):
                await engine.handle_bind(bind)

    @pytest.mark.asyncio
    async def test_result_includes_metrics(self) -> None:
        agent = _make_agent()
        engine = NegotiationEngine(agent)

        request = _make_request()
        engine._active["task-1"] = {
            "role": "provider",
            "state": "offered",
            "request": request,
        }

        bind = NegotiationMessage(
            type=MessageType.BIND,
            task_id="task-1",
            from_agent="requester-1",
            to_agent="provider-1",
        )

        with patch("aeolus.tasks.executor.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Done"
            result = await engine.handle_bind(bind)

        assert result.metrics is not None
        assert "executor" in result.metrics
        assert "model" in result.metrics
