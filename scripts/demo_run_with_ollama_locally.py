"""
scripts/demo_run_with_ollama_locally.py
Run the 3-agent Aeolus demo locally with Ollama models.

Usage:
  # Terminal 1: nats-server
  # Terminal 2:
  python scripts/demo_run_with_ollama_locally.py

	# Optional: set RUN_DASHBOARD = True below to launch dashboard too.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Local Ollama config (edit here) ─────────────────────────────────────────

RUN_DASHBOARD = True

MODEL_NAME_AGENT_ALPHA = "qwen3:0.6b"
MODEL_NAME_AGENT_BETA = "llama3.2:3b"
MODEL_NAME_AGENT_GAMMA = "llama2-uncensored:7b"

ROOT = Path(__file__).parent.parent

load_dotenv()

os.environ["LOCAL_ONLY"] = "true"
os.environ["OLLAMA_MODEL"] = MODEL_NAME_AGENT_ALPHA

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from aeolus.network.node import AgentNode

console = Console()
logging.basicConfig(level="WARNING")


# ── Agent profiles ───────────────────────────────────────────────────────────

AGENTS = [
	dict(
		name=MODEL_NAME_AGENT_ALPHA,
		capabilities=["text summarisation", "sentiment analysis", "question answering"],
		capability_description=(
			"agent-alpha specialises in fast text processing: "
			"summarisation, sentiment analysis, and extractive Q&A."
		),
		model_tier="3B",
		model_name=MODEL_NAME_AGENT_ALPHA,
	),
	dict(
		name=MODEL_NAME_AGENT_BETA,
		capabilities=["translation", "text rewriting", "paraphrasing"],
		capability_description=(
			"agent-beta specialises in multilingual work: "
			"EN↔FR/ES translation, text rewriting, and paraphrasing."
		),
		model_tier="8B",
		model_name=MODEL_NAME_AGENT_BETA,
	),
	dict(
		name=MODEL_NAME_AGENT_GAMMA,
		capabilities=["code review", "security analysis", "complex reasoning"],
		capability_description=(
			"agent-gamma is a high-capacity agent specialised in "
			"code review, vulnerability detection, and complex multi-step reasoning."
		),
		model_tier="LARGE",
		model_name=MODEL_NAME_AGENT_GAMMA,
	),
]

DEMO_TASKS = [
	{
		"title": "Step 2 — Simple Task: Summarisation",
		"submitted_by": MODEL_NAME_AGENT_BETA,
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
		"submitted_by": MODEL_NAME_AGENT_ALPHA,
		"description": (
			"Translate the following technical paragraph from English to French:\n"
			"Peer-to-peer networks enable direct communication between nodes without "
			"relying on a central server. Each node acts simultaneously as a client "
			"and a server, improving resilience and scalability."
		),
		"max_latency_ms": 5_000,
		"min_quality": 0.85,
	},
	{
		"title": "Step 4 — Tier Escalation: Code Review",
		"submitted_by": MODEL_NAME_AGENT_ALPHA,
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


def maybe_start_dashboard() -> subprocess.Popen | None:
	if not RUN_DASHBOARD:
		return None

	script_path = ROOT / "scripts" / "run_dashboard.py"
	return subprocess.Popen(
		[sys.executable, str(script_path)],
		cwd=ROOT,
	)


async def run_demo():
	console.print(Panel.fit(
		"[bold cyan]🌬️  Aeolus — Local Ollama Demo[/bold cyan]",
		border_style="cyan",
	))
	console.print(
		"[dim]Configured models: "
		f"alpha={MODEL_NAME_AGENT_ALPHA}, "
		f"beta={MODEL_NAME_AGENT_BETA}, "
		f"gamma={MODEL_NAME_AGENT_GAMMA}[/dim]"
	)

	dashboard_proc = maybe_start_dashboard()
	if dashboard_proc:
		console.print("[green]✓[/green] Dashboard process started")

	console.print("\n[bold]Step 1 — Discovery[/bold] Starting 3 agents…\n")
	nodes: dict[str, AgentNode] = {}
	try:
		for profile in AGENTS:
			node = AgentNode(**profile)
			await node.start()
			nodes[profile["name"]] = node
			tier = profile["model_tier"]
			model_name = profile["model_name"]
			console.print(
				f"  [green]✓[/green] {profile['name']} online "
				f"([dim]{tier} · {model_name}[/dim])"
			)

		await asyncio.sleep(2)

		known_total = sum(len(n.known_peers) for n in nodes.values())
		console.print(f"\n  [cyan]{known_total}[/cyan] peer-discovery events exchanged\n")

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
	finally:
		console.print("\n[bold]Shutting down agents…[/bold]")
		await asyncio.gather(*[n.stop() for n in nodes.values()])
		if dashboard_proc:
			dashboard_proc.terminate()
			try:
				dashboard_proc.wait(timeout=5)
			except subprocess.TimeoutExpired:
				dashboard_proc.kill()

	console.print("[bold cyan]Demo complete![/bold cyan] 🎉")


if __name__ == "__main__":
	asyncio.run(run_demo())
