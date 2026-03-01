"""
aeolus/negotiation/matcher.py
Semantic capability matching using embeddings + cosine similarity.
Falls back to keyword overlap if embedding is unavailable.
"""
from __future__ import annotations

import logging

import numpy as np

from aeolus.negotiation.capability import AgentCapabilityDocument

logger = logging.getLogger(__name__)


# ── Similarity helpers ────────────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    norm_a, norm_b = np.linalg.norm(va), np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def keyword_match_score(task_description: str, agent: AgentCapabilityDocument) -> float:
    """Simple keyword overlap fallback (no external calls)."""
    task_lower = task_description.lower()
    matched = sum(
        1 for cap in agent.capabilities
        if any(word in task_lower for word in cap.lower().split())
    )
    return min(1.0, matched / max(1, len(agent.capabilities)))


# ── Semantic match ────────────────────────────────────────────────────────────

async def semantic_match_score(
    task_description: str,
    agent: AgentCapabilityDocument,
) -> float:
    """
    Compute semantic similarity between the task and the agent's capability
    description. Falls back to keyword matching if embeddings fail.
    """
    try:
        from aeolus.negotiation.llm import embed
        task_emb = await embed(task_description)
        agent_emb = await embed(agent.capability_description)
        score = cosine_similarity(task_emb, agent_emb)
        logger.debug(f"Semantic match [{agent.name}]: {score:.3f}")
        return score
    except Exception as exc:
        logger.warning(f"Embedding failed for {agent.name}, using keyword match: {exc}")
        return keyword_match_score(task_description, agent)


# ── Agent ranking ─────────────────────────────────────────────────────────────

async def rank_agents(
    task_description: str,
    agents: list[AgentCapabilityDocument],
    min_score: float = 0.3,
) -> list[tuple[AgentCapabilityDocument, float]]:
    """
    Rank available agents by semantic match. Returns (agent, score) sorted best-first.
    Only agents above min_score are included.
    """
    import asyncio

    available = [a for a in agents if a.is_available]
    if not available:
        return []

    scores = await asyncio.gather(
        *[semantic_match_score(task_description, agent) for agent in available]
    )

    ranked = [
        (agent, score)
        for agent, score in zip(available, scores)
        if score >= min_score
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
