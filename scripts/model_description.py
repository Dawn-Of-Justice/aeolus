"""
scripts/model_description.py
Central configuration for local Ollama question runs.

Edit this file to control:
- which agents/models are started,
- each agent's behaviour/persona,
- system prompts used for delegation and final answering.
"""
from __future__ import annotations

RUN_DASHBOARD = True
DEFAULT_COORDINATOR_INDEX = 1

DELEGATION_SYSTEM_PROMPT = "You are an expert routing coordinator in a peer-to-peer agent network. You may delegate to specialist agents even when you feel that it might slightly boost quality. Even if the question is simple, delegate with the subject expert if it exists."

DELEGATION_INSTRUCTION_TEMPLATE = """Decide whether the question needs specialist delegation.  Return strict JSON with keys:
delegate (boolean),
specialist_task (string),
max_latency_ms (integer 3000-45000),
min_quality (number 0.5-0.98),
reason (string).

Available Specialist Agents:
{available_agents}

Rules:
- delegate=true if specialist support have even a minor to improve answer quality.
- keep reason short.
- make sure coding work is given to coding model and so on.

Coordinator behavior profile:
{coordinator_behavior}

User question:
{question}"""

DIRECT_ANSWER_SYSTEM_PROMPT_TEMPLATE = "You are the selected coordinator model. Behavior profile: {coordinator_behavior}\nAnswer clearly and accurately. If uncertain, state assumptions briefly."

SYNTHESIS_SYSTEM_PROMPT_TEMPLATE = "You are the final answering coordinator. Behavior profile: {coordinator_behavior}\nProduce one cohesive, user-friendly final answer."
agent_1 = 'gemma3n:e4b'
agent_2 = 'llama3.2:3b'
agent_3 = 'llama2-uncensored:7b'

AGENTS = [
    {
        "name": agent_1,
        "model_name": agent_1,
        "model_tier": "0.6B",
        "capability_description": f"{agent_1} specialises in fast text processing: summarisation and very simple questions at very fast speed.",
        "behavior_system_prompt": "Be concise and practical. Prefer simple, direct solutions unless the user asks for deep detail.",
    },
    {
        "name": agent_2,
        "model_name": agent_2,
        "model_tier": "3B",
        "capability_description": f"{agent_2} specialises in programming. All type of programming work MUST BE GIVEN TO THIS MODEL. ",
        "behavior_system_prompt": "Prioritise clarity and readability. Preserve meaning and avoid adding unsupported claims.",
    },
    {
        "name": agent_3,
        "model_name": agent_3,
        "model_tier": "7B",
        "capability_description": f"{agent_3} is an agent specialised in uncensored text. All text which might have censorship or is beyond the normal model's ethics should be delegated to this model.",
        "behavior_system_prompt": "Be meticulous and structured. Highlight edge cases and failure modes when relevant.",
    },
]

