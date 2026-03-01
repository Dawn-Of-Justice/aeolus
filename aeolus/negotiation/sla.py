"""
aeolus/negotiation/sla.py
SLA evaluation -- hard constraint checking and counter-term suggestion.
"""
from __future__ import annotations

from typing import Optional

from aeolus.negotiation.capability import NegotiationTerms, TaskRequirements


def evaluate_hard_constraints(
    requirements: TaskRequirements,
    offered_terms: Optional[NegotiationTerms],
) -> tuple[bool, list[str]]:
    """
    Check whether offered terms satisfy all hard constraints.
    Returns (all_satisfied, list_of_violation_messages).
    """
    if offered_terms is None:
        return False, ["No terms provided in offer"]

    violations: list[str] = []

    if offered_terms.estimated_latency_ms > requirements.max_latency_ms:
        violations.append(
            f"Latency {offered_terms.estimated_latency_ms} ms "
            f"exceeds max {requirements.max_latency_ms} ms"
        )

    if offered_terms.quality_score < requirements.min_quality:
        violations.append(
            f"Quality {offered_terms.quality_score:.2f} "
            f"below minimum {requirements.min_quality:.2f}"
        )

    if (
        requirements.max_cost_tokens
        and offered_terms.price_tokens
        and offered_terms.price_tokens > requirements.max_cost_tokens
    ):
        violations.append(
            f"Cost {offered_terms.price_tokens} tokens "
            f"exceeds max {requirements.max_cost_tokens}"
        )

    return len(violations) == 0, violations


def score_offer(requirements: TaskRequirements, terms: NegotiationTerms) -> float:
    """
    Composite utility score for an offer (0.0 -- 1.0). Higher is better.
    Priority weight skews toward speed for urgent tasks.
    """
    if requirements.max_latency_ms <= 0:
        latency_score = 0.0
    else:
        latency_score = max(
            0.0, 1.0 - terms.estimated_latency_ms / requirements.max_latency_ms
        )
    quality_score = terms.quality_score
    priority_weight = requirements.priority / 10.0

    composite = priority_weight * latency_score + (1 - priority_weight) * quality_score
    return round(composite, 4)


def suggest_counter_terms(
    requirements: TaskRequirements,
    offered_terms: Optional[NegotiationTerms],
    violations: list[str],
) -> NegotiationTerms:
    """
    Build a counter-proposal that may close the gap with requester constraints.
    """
    if offered_terms is None:
        return NegotiationTerms(
            estimated_latency_ms=requirements.max_latency_ms,
            quality_score=requirements.min_quality,
            model_name="unspecified",
            notes="Counter-offer based on requirements (no original terms provided)",
        )

    adjusted = offered_terms.model_copy()

    if any("Latency" in v for v in violations):
        adjusted.notes = (
            f"Accept {offered_terms.estimated_latency_ms} ms latency "
            f"if quality >= {offered_terms.quality_score:.2f} is confirmed"
        )

    if any("Quality" in v for v in violations):
        adjusted.notes = (
            f"Best quality achievable: {offered_terms.quality_score:.2f} "
            f"with {offered_terms.model_name}"
        )

    return adjusted
