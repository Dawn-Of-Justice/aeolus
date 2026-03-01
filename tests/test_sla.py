"""Tests for SLA evaluation and counter-offer logic."""
from __future__ import annotations

from aeolus.negotiation.capability import NegotiationTerms, TaskRequirements
from aeolus.negotiation.sla import (
    evaluate_hard_constraints,
    score_offer,
    suggest_counter_terms,
)


# -- evaluate_hard_constraints ------------------------------------------------

class TestEvaluateHardConstraints:
    def test_acceptable_offer(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.85,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is True
        assert violations == []

    def test_latency_too_high(self) -> None:
        req = TaskRequirements(max_latency_ms=1000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.85,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is False
        assert any("Latency" in v for v in violations)

    def test_quality_too_low(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.9)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.7,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is False
        assert any("Quality" in v for v in violations)

    def test_both_fail(self) -> None:
        req = TaskRequirements(max_latency_ms=500, min_quality=0.95)
        terms = NegotiationTerms(
            estimated_latency_ms=3000,
            quality_score=0.5,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is False
        assert len(violations) == 2

    def test_exact_boundary_passes(self) -> None:
        req = TaskRequirements(max_latency_ms=2000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.7,
            model_name="ministral-3b-latest",
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is True

    def test_none_terms_fails(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7)
        ok, violations = evaluate_hard_constraints(req, None)
        assert ok is False
        assert len(violations) == 1

    def test_cost_violation(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7, max_cost_tokens=100)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.8,
            model_name="ministral-3b-latest",
            price_tokens=200,
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is False
        assert any("Cost" in v for v in violations)

    def test_cost_within_limit(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7, max_cost_tokens=500)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.8,
            model_name="ministral-3b-latest",
            price_tokens=200,
        )
        ok, violations = evaluate_hard_constraints(req, terms)
        assert ok is True


# -- score_offer --------------------------------------------------------------

class TestScoreOffer:
    def test_perfect_offer(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7, priority=5)
        terms = NegotiationTerms(
            estimated_latency_ms=0,
            quality_score=1.0,
            model_name="ministral-3b-latest",
        )
        score = score_offer(req, terms)
        assert score == 1.0

    def test_worst_offer(self) -> None:
        req = TaskRequirements(max_latency_ms=1000, min_quality=0.7, priority=5)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.0,
            model_name="ministral-3b-latest",
        )
        score = score_offer(req, terms)
        assert score == 0.0

    def test_priority_weights_speed(self) -> None:
        req_urgent = TaskRequirements(max_latency_ms=5000, min_quality=0.7, priority=9)
        req_normal = TaskRequirements(max_latency_ms=5000, min_quality=0.7, priority=2)
        terms = NegotiationTerms(
            estimated_latency_ms=1000,
            quality_score=0.6,
            model_name="ministral-3b-latest",
        )
        score_urgent = score_offer(req_urgent, terms)
        score_normal = score_offer(req_normal, terms)
        assert score_urgent != score_normal

    def test_zero_max_latency(self) -> None:
        req = TaskRequirements(max_latency_ms=0, min_quality=0.7, priority=5)
        terms = NegotiationTerms(
            estimated_latency_ms=1000,
            quality_score=0.8,
            model_name="ministral-3b-latest",
        )
        score = score_offer(req, terms)
        assert 0.0 <= score <= 1.0

    def test_score_bounded(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7, priority=5)
        terms = NegotiationTerms(
            estimated_latency_ms=2500,
            quality_score=0.75,
            model_name="ministral-3b-latest",
        )
        score = score_offer(req, terms)
        assert 0.0 <= score <= 1.0


# -- suggest_counter_terms ----------------------------------------------------

class TestSuggestCounterTerms:
    def test_counter_for_latency_violation(self) -> None:
        req = TaskRequirements(max_latency_ms=2000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=3000,
            quality_score=0.85,
            model_name="ministral-3b-latest",
        )
        counter = suggest_counter_terms(req, terms, ["Latency 3000 ms exceeds max 2000 ms"])
        assert counter is not None
        assert counter.notes is not None

    def test_counter_for_quality_violation(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.8)
        terms = NegotiationTerms(
            estimated_latency_ms=2000,
            quality_score=0.6,
            model_name="ministral-3b-latest",
        )
        counter = suggest_counter_terms(req, terms, ["Quality 0.60 below minimum 0.80"])
        assert counter is not None
        assert counter.notes is not None

    def test_counter_with_none_terms(self) -> None:
        req = TaskRequirements(max_latency_ms=5000, min_quality=0.7)
        counter = suggest_counter_terms(req, None, ["No terms provided"])
        assert counter is not None
        assert counter.estimated_latency_ms == 5000
        assert counter.quality_score == req.min_quality

    def test_counter_preserves_model_name(self) -> None:
        req = TaskRequirements(max_latency_ms=2000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=3000,
            quality_score=0.85,
            model_name="custom-model",
        )
        counter = suggest_counter_terms(req, terms, ["Latency violation"])
        assert counter.model_name == "custom-model"

    def test_counter_preserves_latency(self) -> None:
        req = TaskRequirements(max_latency_ms=2000, min_quality=0.7)
        terms = NegotiationTerms(
            estimated_latency_ms=3000,
            quality_score=0.85,
            model_name="ministral-3b-latest",
        )
        counter = suggest_counter_terms(req, terms, ["Latency 3000 ms exceeds max 2000 ms"])
        # Counter should preserve original latency (it's the provider's best estimate)
        assert counter.estimated_latency_ms == 3000
