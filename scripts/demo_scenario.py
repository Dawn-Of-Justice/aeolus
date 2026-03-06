"""
scripts/demo_scenario.py
Scripted 3-agent demo.
Runs three agents locally (same machine, same NATS) and walks through:
  1. Discovery
  2. Simple task (summarisation routed to right agent)
  3. Negotiation with COUNTER round
  4. Tier escalation (complex task → LARGE tier)

Usage:
  # Terminal 1: nats-server
  # Terminal 2: python scripts/demo_scenario.py
"""
from __future__ import annotations

import asyncio
import logging

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from aeolus.network.node import AgentNode

console = Console()
logging.basicConfig(level="WARNING")  # keep logs quiet during demo


# ── Agent profiles ────────────────────────────────────────────────────────────

AGENTS = [
    dict(
        name="agent-alpha",
        capabilities=["text summarisation", "sentiment analysis", "question answering"],
        capability_description=(
            "agent-alpha specialises in fast text processing: "
            "summarisation, sentiment analysis, and extractive Q&A."
        ),
        model_tier="3B",
    ),
    dict(
        name="agent-beta",
        capabilities=["translation", "text rewriting", "paraphrasing"],
        capability_description=(
            "agent-beta specialises in multilingual work: "
            "EN↔FR/ES translation, text rewriting, and paraphrasing."
        ),
        model_tier="3B",
    ),
    dict(
        name="agent-gamma",
        capabilities=["code review", "security analysis", "complex reasoning"],
        capability_description=(
            "agent-gamma is a high-capacity agent specialised in "
            "code review, vulnerability detection, and complex multi-step reasoning."
        ),
        model_tier="LARGE",
    ),
]

DEMO_TASKS = [
    {
        "title": "Step 2 — Simple Task: Summarisation",
        "submitted_by": "agent-beta",
        "description": (
            "Summarise the following article in 3 bullet points:\n"
            "Renewable energy has seen record growth in 2025. Solar capacity doubled "
            "globally, wind energy reached 2 TW, and battery storage costs fell by 40%. "
            "Governments in 60 countries introduced new clean-energy incentives, and "
            "fossil fuel investment declined for the third consecutive year."
        ),
        "max_latency_ms": 15_000,
        "min_quality": 0.6,
    },
    {
        "title": "Step 3 — Negotiation with COUNTER: Translation",
        "submitted_by": "agent-alpha",
        "description": (
            "Translate the following technical paragraph from English to French:\n"
            "Peer-to-peer networks enable direct communication between nodes without "
            "relying on a central server. Each node acts simultaneously as a client "
            "and a server, improving resilience and scalability."
        ),
        "max_latency_ms": 5_000,   # tight — may trigger a COUNTER
        "min_quality": 0.85,
    },
    {
        "title": "Step 4 — Tier Escalation: Code Review",
        "submitted_by": "agent-alpha",
        "description": (
            "Review the following Python function for security vulnerabilities "
            "and suggest concrete fixes:\n\n"
            "def get_user(user_id):\n"
            "    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
            "    return db.execute(query).fetchone()"
        ),
        "max_latency_ms": 20_000,
        "min_quality": 0.8,
    },
]


# ── Demo runner ───────────────────────────────────────────────────────────────

async def run_demo():
    console.print(Panel.fit(
        "[bold cyan]🌬️  Aeolus — P2P Agent Negotiation Demo[/bold cyan]",
        border_style="cyan",
    ))

    # Spawn all three agents
    console.print("\n[bold]Step 1 — Discovery[/bold] Starting 3 agents…\n")
    nodes: dict[str, AgentNode] = {}
    for profile in AGENTS:
        node = AgentNode(**profile)
        await node.start()
        nodes[profile["name"]] = node
        console.print(
            f"  [green]✓[/green] {profile['name']} online "
            f"([dim]{profile['model_tier']}[/dim])"
        )

    await asyncio.sleep(2)  # let agents discover each other

    known_total = sum(len(n.known_peers) for n in nodes.values())
    console.print(f"\n  [cyan]{known_total}[/cyan] peer-discovery events exchanged\n")

    # Run tasks sequentially
    for task_spec in DEMO_TASKS:
        console.rule(f"[bold yellow]{task_spec['title']}[/bold yellow]")
        submitter = nodes[task_spec["submitted_by"]]
        desc = task_spec["description"]
        console.print(f"\n[dim]Submitter:[/dim] {task_spec['submitted_by']}")
        console.print(f"[dim]Task:[/dim] {desc[:100]}…\n")

        result = await submitter.submit_task(
            task_description=desc,
            max_latency_ms=task_spec["max_latency_ms"],
            min_quality=task_spec["min_quality"],
        )

        if result:
            console.print(Panel(
                Text(result[:600], style="green"),
                title="[bold green]✅ Result[/bold green]",
                border_style="green",
            ))
        else:
            console.print("[red]✗ No result received (timeout)[/red]")

        await asyncio.sleep(1)

    # Cleanup
    console.print("\n[bold]Shutting down agents…[/bold]")
    await asyncio.gather(*[n.stop() for n in nodes.values()])
    console.print("[bold cyan]Demo complete![/bold cyan] 🎉")


if __name__ == "__main__":
    asyncio.run(run_demo())
