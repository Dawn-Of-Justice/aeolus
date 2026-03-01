"""
aeolus/tasks/executor.py
Execute tasks by calling the LLM with the task prompt.
"""
from __future__ import annotations

import logging
import time

from aeolus.negotiation.capability import AgentCapabilityDocument
from aeolus.negotiation import llm, prompts

logger = logging.getLogger(__name__)


async def execute_task(
    task_description: str,
    agent: AgentCapabilityDocument,
) -> str:
    """
    Execute a task using the agent's assigned LLM.
    Returns the output string.
    """
    logger.info(f"[{agent.name}] Executing: {task_description[:80]}…")
    t0 = time.monotonic()

    prompt = prompts.TASK_EXECUTION_PROMPT.format(task_description=task_description)

    result = await llm.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are {agent.name}, a {agent.model_tier}-tier AI agent. "
                    f"Capability profile: {agent.capability_description}"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        model=agent.model_name,
        temperature=0.5,
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.info(f"[{agent.name}] Task done in {elapsed_ms}ms")
    return result
