"""
aeolus/negotiation/engine.py
NegotiationEngine -- orchestrates the full REQUEST->OFFER->COUNTER->ACCEPT->BIND->RESULT flow.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aeolus.exceptions import NegotiationError, TaskExecutionError
from aeolus.negotiation import llm, prompts, sla
from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    MessageType,
    NegotiationMessage,
    NegotiationTerms,
    TaskRequirements,
)

logger = logging.getLogger(__name__)


class NegotiationEngine:
    """
    Manages negotiation state from the perspective of a single agent node.
    An agent can simultaneously act as:
      - A PROVIDER (receives REQUESTs, sends OFFERs, executes tasks)
      - A REQUESTER (sends REQUESTs, evaluates OFFERs, issues ACCEPTs)
    """

    def __init__(self, agent: AgentCapabilityDocument):
        self.agent = agent
        # task_id -> negotiation state dict
        self._active: dict[str, dict] = {}
        self._active_lock = asyncio.Lock()

    # -- Provider side -------------------------------------------------------

    async def evaluate_request(
        self, request: NegotiationMessage
    ) -> Optional[NegotiationMessage]:
        """
        Evaluate an incoming REQUEST. Returns an OFFER message or None to decline.
        """
        if not self.agent.is_available:
            logger.info(f"[{self.agent.name}] Declining {request.task_id}: overloaded")
            return None

        try:
            assessment = await self._assess_task(request)
        except Exception as exc:
            logger.error(
                f"[{self.agent.name}] Task assessment failed for "
                f"{request.task_id}: {exc}"
            )
            return None

        if not assessment.get("should_offer", False):
            logger.info(
                f"[{self.agent.name}] Declining {request.task_id}: "
                f"match={assessment.get('match_score', 0):.2f}"
            )
            return None

        terms = NegotiationTerms(
            estimated_latency_ms=assessment.get("estimated_latency_ms", 5000),
            quality_score=assessment.get("quality_score", 0.7),
            model_name=self.agent.model_name,
        )

        offer = NegotiationMessage(
            type=MessageType.OFFER,
            task_id=request.task_id,
            from_agent=self.agent.peer_id,
            to_agent=request.from_agent,
            match_score=round(assessment.get("match_score", 0.5), 3),
            terms=terms,
        )

        async with self._active_lock:
            self._active[request.task_id] = {
                "role": "provider",
                "state": "offered",
                "request": request,
                "offer": offer,
            }

        logger.info(
            f"[{self.agent.name}] Offering task {request.task_id}: "
            f"score={offer.match_score}, latency={terms.estimated_latency_ms}ms"
        )
        return offer

    async def handle_bind(self, bind: NegotiationMessage) -> NegotiationMessage:
        """
        Execute the task after receiving a BIND. Returns a RESULT message.
        """
        async with self._active_lock:
            state = self._active.get(bind.task_id)
        if not state:
            raise NegotiationError(f"Unknown task_id in BIND: {bind.task_id}")

        logger.info(f"[{self.agent.name}] Executing task {bind.task_id}")
        request: NegotiationMessage = state["request"]

        try:
            from aeolus.tasks.executor import execute_task
            output = await execute_task(request.task_description or "", self.agent)
        except Exception as exc:
            raise TaskExecutionError(
                f"Task {bind.task_id} execution failed: {exc}"
            ) from exc

        result = NegotiationMessage(
            type=MessageType.RESULT,
            task_id=bind.task_id,
            from_agent=self.agent.peer_id,
            to_agent=bind.from_agent,
            output=output,
            success=True,
            metrics={"executor": self.agent.name, "model": self.agent.model_name},
        )

        async with self._active_lock:
            self._active.pop(bind.task_id, None)
        return result

    # -- Requester side ------------------------------------------------------

    async def evaluate_offer(
        self,
        offer: NegotiationMessage,
        original_requirements: TaskRequirements,
    ) -> NegotiationMessage:
        """
        Evaluate a received OFFER. Returns ACCEPT or COUNTER.
        """
        satisfied, violations = sla.evaluate_hard_constraints(
            original_requirements, offer.terms
        )

        if satisfied:
            accept = NegotiationMessage(
                type=MessageType.ACCEPT,
                task_id=offer.task_id,
                from_agent=self.agent.peer_id,
                to_agent=offer.from_agent,
                binding_terms=offer.terms,
            )
            logger.info(
                f"[{self.agent.name}] Accepting offer from {offer.from_agent} "
                f"for task {offer.task_id}"
            )
            return accept

        # Build counter-offer
        suggested = sla.suggest_counter_terms(
            original_requirements, offer.terms, violations
        )
        counter = NegotiationMessage(
            type=MessageType.COUNTER,
            task_id=offer.task_id,
            from_agent=self.agent.peer_id,
            to_agent=offer.from_agent,
            adjusted_terms=suggested,
            reason="; ".join(violations),
        )
        logger.info(
            f"[{self.agent.name}] Countering offer from {offer.from_agent}: {violations}"
        )
        return counter

    # -- Internal ------------------------------------------------------------

    async def _assess_task(self, request: NegotiationMessage) -> dict:
        """Ask the LLM whether we should accept and at what terms."""
        def _to_float(value, default: float) -> float:
            try:
                if value is None:
                    return default
                return float(value)
            except (TypeError, ValueError):
                return default

        def _to_int(value, default: int) -> int:
            try:
                if value is None:
                    return default
                return int(float(value))
            except (TypeError, ValueError):
                return default

        def _to_bool(value, default: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes", "y"}:
                    return True
                if lowered in {"false", "0", "no", "n"}:
                    return False
            return default

        reqs = request.requirements or TaskRequirements()
        model_tier = (
            self.agent.model_tier.value
            if hasattr(self.agent.model_tier, "value")
            else str(self.agent.model_tier)
        )
        raw = await llm.complete_json(
            messages=[
                {"role": "system", "content": prompts.NEGOTIATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": prompts.CAPABILITY_ASSESSMENT_PROMPT.format(
                        capabilities=", ".join(self.agent.capabilities),
                        capability_description=self.agent.capability_description,
                        current_load=self.agent.current_load,
                        max_concurrent_tasks=self.agent.max_concurrent_tasks,
                        model_tier=model_tier,
                        task_description=request.task_description,
                        requirements=reqs.model_dump_json(),
                    ),
                },
            ],
            model=self.agent.model_name,
            temperature=0.2,
        )

        # Validate and provide defaults for LLM response
        match_score = min(max(_to_float(raw.get("match_score"), 0.0), 0.0), 1.0)
        estimated_latency_ms = min(
            max(_to_int(raw.get("estimated_latency_ms"), 5000), 500),
            120_000,
        )
        quality_score = min(max(_to_float(raw.get("quality_score"), 0.5), 0.0), 1.0)

        return {
            "should_offer": _to_bool(raw.get("should_offer"), False),
            "match_score": match_score,
            "estimated_latency_ms": estimated_latency_ms,
            "quality_score": quality_score,
            "reasoning": str(raw.get("reasoning", "")),
        }
