"""Tests for the semantic matcher."""
from __future__ import annotations

import pytest

from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    ModelTierEnum,
)
from aeolus.negotiation.matcher import (
    cosine_similarity,
    keyword_match_score,
    rank_agents,
)


def _make_agent(
    peer_id: str,
    name: str,
    capabilities: list[str],
    description: str = "test agent",
    status: AgentStatus = AgentStatus.AVAILABLE,
    current_load: int = 0,
) -> AgentCapabilityDocument:
    return AgentCapabilityDocument(
        peer_id=peer_id,
        name=name,
        model_tier=ModelTierEnum.T1,
        capabilities=capabilities,
        capability_description=description,
        status=status,
        current_load=current_load,
    )


# -- cosine_similarity --------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_single_element(self) -> None:
        assert abs(cosine_similarity([3.0], [3.0]) - 1.0) < 1e-6


# -- keyword_match_score ------------------------------------------------------

class TestKeywordMatchScore:
    def test_full_match(self) -> None:
        agent = _make_agent("p1", "a", ["text", "summarise"])
        score = keyword_match_score("please summarise this text", agent)
        assert score == 1.0

    def test_partial_match(self) -> None:
        agent = _make_agent("p1", "a", ["text", "translation", "code"])
        score = keyword_match_score("translate this text", agent)
        assert 0.0 < score < 1.0

    def test_no_match(self) -> None:
        agent = _make_agent("p1", "a", ["translation"])
        score = keyword_match_score("review code for security bugs", agent)
        assert score == 0.0

    def test_case_insensitive(self) -> None:
        agent = _make_agent("p1", "a", ["Text", "Summarisation"])
        score = keyword_match_score("TEXT SUMMARISATION", agent)
        assert score == 1.0

    def test_empty_capabilities(self) -> None:
        agent = _make_agent("p1", "a", [])
        score = keyword_match_score("anything", agent)
        assert score == 0.0

    def test_score_bounded(self) -> None:
        agent = _make_agent("p1", "a", ["a"])
        score = keyword_match_score("a a a a a a", agent)
        assert 0.0 <= score <= 1.0


# -- rank_agents (async) ------------------------------------------------------

class TestRankAgents:
    @pytest.mark.asyncio
    async def test_filters_unavailable(self) -> None:
        agents = [
            _make_agent("p1", "a", ["summarisation"], status=AgentStatus.AVAILABLE),
            _make_agent("p2", "b", ["summarisation"], status=AgentStatus.BUSY),
        ]
        import aeolus.negotiation.matcher as matcher_mod
        original = matcher_mod.semantic_match_score

        async def mock_match(desc, agent):
            return keyword_match_score(desc, agent)

        matcher_mod.semantic_match_score = mock_match
        try:
            ranked = await rank_agents("summarise text", agents, min_score=0.0)
            peer_ids = [a.peer_id for a, _ in ranked]
            assert "p2" not in peer_ids
        finally:
            matcher_mod.semantic_match_score = original

    @pytest.mark.asyncio
    async def test_filters_by_min_score(self) -> None:
        agents = [
            _make_agent("p1", "a", ["summarisation"]),
            _make_agent("p2", "b", ["translation"]),
        ]
        import aeolus.negotiation.matcher as matcher_mod
        original = matcher_mod.semantic_match_score

        async def mock_match(desc, agent):
            return keyword_match_score(desc, agent)

        matcher_mod.semantic_match_score = mock_match
        try:
            ranked = await rank_agents("summarise text", agents, min_score=0.5)
            assert all(score >= 0.5 for _, score in ranked)
        finally:
            matcher_mod.semantic_match_score = original

    @pytest.mark.asyncio
    async def test_empty_agents(self) -> None:
        ranked = await rank_agents("anything", [], min_score=0.0)
        assert ranked == []

    @pytest.mark.asyncio
    async def test_sorted_best_first(self) -> None:
        agents = [
            _make_agent("p1", "a", ["code"]),
            _make_agent("p2", "b", ["summarisation", "text"]),
        ]
        import aeolus.negotiation.matcher as matcher_mod
        original = matcher_mod.semantic_match_score

        async def mock_match(desc, agent):
            return keyword_match_score(desc, agent)

        matcher_mod.semantic_match_score = mock_match
        try:
            ranked = await rank_agents("summarise this text", agents, min_score=0.0)
            if len(ranked) >= 2:
                assert ranked[0][1] >= ranked[1][1]
        finally:
            matcher_mod.semantic_match_score = original

    @pytest.mark.asyncio
    async def test_all_agents_at_capacity_returns_empty(self) -> None:
        agents = [
            _make_agent("p1", "a", ["summarisation"], current_load=2),
        ]
        import aeolus.negotiation.matcher as matcher_mod
        original = matcher_mod.semantic_match_score

        async def mock_match(desc, agent):
            return keyword_match_score(desc, agent)

        matcher_mod.semantic_match_score = mock_match
        try:
            ranked = await rank_agents("summarise text", agents, min_score=0.0)
            assert ranked == []
        finally:
            matcher_mod.semantic_match_score = original
