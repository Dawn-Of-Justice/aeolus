"""
aeolus/tasks/router.py
Multi-tier routing — decides which model tier should handle a task,
and escalates automatically when a 3B agent assesses low confidence.
"""
from __future__ import annotations

import logging

from aeolus.config import ModelTier, settings
from aeolus.negotiation import llm, prompts
from aeolus.negotiation.capability import AgentCapabilityDocument, TaskRequirements

logger = logging.getLogger(__name__)


async def should_escalate(
    task_description: str,
    agent: AgentCapabilityDocument,
    requirements: TaskRequirements,
) -> tuple[bool, str | None]:
    """
    Ask the LLM whether this task exceeds the agent's capability tier.
    Returns (escalate, target_tier_or_None).
    """
    try:
        result = await llm.complete_json(
            messages=[
                {"role": "system", "content": prompts.NEGOTIATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": prompts.ESCALATION_ASSESSMENT_PROMPT.format(
                        model_tier=agent.model_tier,
                        model_name=agent.model_name,
                        capabilities=", ".join(agent.capabilities),
                        task_description=task_description,
                        requirements=requirements.model_dump_json(),
                    ),
                },
            ],
            temperature=0.1,
        )
        return result.get("should_escalate", False), result.get("escalate_to_tier")
    except Exception as exc:
        logger.warning(f"Escalation check failed: {exc}")
        return False, None


def tier_model(tier: str) -> str:
    """Map tier string ('3B', '8B', 'LARGE') → model name."""
    mapping = {
        "3B":    settings.tier1_model,
        "8B":    settings.tier2_model,
        "LARGE": settings.tier3_model,
    }
    return mapping.get(tier, settings.tier1_model)
