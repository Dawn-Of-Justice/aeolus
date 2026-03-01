"""
scripts/question_run_with_ollama_locally.py
Interactive Aeolus Q&A with local Ollama models.

What it does:
- Starts agents from scripts/model_description.py.
- Lets you choose a coordinator model for each question.
- Coordinator decides whether to delegate to peer agents.
- If delegated, the task goes through Aeolus negotiation (dashboard-visible).
- Coordinator then synthesises the final answer.

Usage:
  # Terminal 1: nats-server
  # Terminal 2:
  python scripts/question_run_with_ollama_locally.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from warnings import filterwarnings
filterwarnings('ignore')

from dotenv import load_dotenv

from model_description import (
	AGENTS,
	DEFAULT_COORDINATOR_INDEX,
	DELEGATION_INSTRUCTION_TEMPLATE,
	DELEGATION_SYSTEM_PROMPT,
	DIRECT_ANSWER_SYSTEM_PROMPT_TEMPLATE,
	RUN_DASHBOARD,
	SYNTHESIS_SYSTEM_PROMPT_TEMPLATE,
)

ROOT = Path(__file__).parent.parent

load_dotenv()

os.environ["LOCAL_ONLY"] = "true"

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.text import Text

from aeolus.negotiation import llm
from aeolus.network.node import AgentNode

console = Console()
logging.basicConfig(level="WARNING")


def _behavior_prompt(profile: dict) -> str:
	return (
		profile.get("behavior_system_prompt")
		or profile.get("system_prompt")
		or "Be accurate, useful, and concise."
	)


def _normalize_agents(agents: list[dict]) -> list[dict]:
	normalized: list[dict] = []
	for profile in agents:
		model_name = str(profile.get("model_name") or profile.get("name") or "").strip()
		if not model_name:
			continue

		name = str(profile.get("name") or model_name).strip()
		capability_description = profile.get("capability_description") or (
			f"{name} can help with general tasks."
		)

		normalized.append(
			{
				"name": name,
				"model_name": model_name,
				"model_tier": profile.get("model_tier", "3B"),
				"capability_description": capability_description,
				"behavior_system_prompt": _behavior_prompt(profile),
			}
		)
	return normalized


RUNTIME_AGENTS = _normalize_agents(AGENTS)

if RUNTIME_AGENTS:
	os.environ["OLLAMA_MODEL"] = RUNTIME_AGENTS[0]["model_name"]


def maybe_start_dashboard() -> subprocess.Popen | None:
	if not RUN_DASHBOARD:
		return None

	script_path = ROOT / "scripts" / "run_dashboard.py"
	return subprocess.Popen([sys.executable, str(script_path)], cwd=ROOT)


async def decide_delegation(question: str, coordinator_model: str) -> dict:
	"""
	Ask the coordinator model whether to delegate to peer agents.
	Returns a dict with keys: delegate, specialist_task, max_latency_ms, min_quality, reason.
	"""
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

	def _to_int(value, default: int) -> int:
		try:
			if value is None:
				return default
			return int(float(value))
		except (TypeError, ValueError):
			return default

	def _to_float(value, default: float) -> float:
		try:
			if value is None:
				return default
			return float(value)
		except (TypeError, ValueError):
			return default

	coordinator_profile = next(
		(p for p in RUNTIME_AGENTS if p["model_name"] == coordinator_model),
		{},
	)
	coordinator_behavior = _behavior_prompt(coordinator_profile)

	available_agents_info = "\n".join(
		f"- Name: {p['name']}, Tier: {p.get('model_tier', 'unknown')}, Capabilities: {p.get('capability_description', '')}"
		for p in RUNTIME_AGENTS if p["model_name"] != coordinator_model
	)
	if not available_agents_info.strip():
		available_agents_info = "None"

	prompt = DELEGATION_INSTRUCTION_TEMPLATE.format(
		available_agents=available_agents_info,
		coordinator_behavior=coordinator_behavior,
		question=question,
	)

	try:
		decision = await llm.complete_json(
			messages=[
				{"role": "system", "content": DELEGATION_SYSTEM_PROMPT},
				{"role": "user", "content": prompt},
			],
			model=coordinator_model,
			temperature=0.2,
		)
	except Exception:
		decision = {}

	delegate = _to_bool(decision.get("delegate", False), False)
	specialist_raw = decision.get("specialist_task")
	if isinstance(specialist_raw, str):
		specialist_task = specialist_raw.strip()
	elif specialist_raw is None:
		specialist_task = ""
	else:
		specialist_task = str(specialist_raw).strip()
	if specialist_task.lower() in {"", "none", "null", "n/a", "na"}:
		specialist_task = question
	max_latency_ms = _to_int(decision.get("max_latency_ms", 15000), 15000)
	min_quality = _to_float(decision.get("min_quality", 0.75), 0.75)
	reason = str(decision.get("reason", "No reason provided")).strip()

	max_latency_ms = min(max(max_latency_ms, 3000), 45000)
	min_quality = min(max(min_quality, 0.5), 0.98)

	return {
		"delegate": delegate,
		"specialist_task": specialist_task,
		"max_latency_ms": max_latency_ms,
		"min_quality": min_quality,
		"reason": reason,
	}


async def direct_answer(question: str, model_name: str) -> str:
	coordinator_profile = next(
		(p for p in RUNTIME_AGENTS if p["model_name"] == model_name),
		{},
	)
	coordinator_behavior = _behavior_prompt(coordinator_profile)
	system_prompt = DIRECT_ANSWER_SYSTEM_PROMPT_TEMPLATE.format(
		coordinator_behavior=coordinator_behavior,
	)

	return await llm.complete(
		messages=[
			{
				"role": "system",
				"content": system_prompt,
			},
			{"role": "user", "content": question},
		],
		model=model_name,
		temperature=0.4,
	)


async def synthesize_answer(
	question: str,
	coordinator_model: str,
	specialist_result: str,
	reason: str,
) -> str:
	coordinator_profile = next(
		(p for p in RUNTIME_AGENTS if p["model_name"] == coordinator_model),
		{},
	)
	coordinator_behavior = _behavior_prompt(coordinator_profile)
	system_prompt = SYNTHESIS_SYSTEM_PROMPT_TEMPLATE.format(
		coordinator_behavior=coordinator_behavior,
	)

	return await llm.complete(
		messages=[
			{
				"role": "system",
				"content": system_prompt,
			},
			{
				"role": "user",
				"content": (
					f"Original question:\n{question}\n\n"
					f"Delegation reason:\n{reason}\n\n"
					f"Specialist output:\n{specialist_result}\n\n"
					"Now write the final answer for the user."
				),
			},
		],
		model=coordinator_model,
		temperature=0.4,
	)


def choose_model_once() -> str:
	console.print("\n[bold]Choose coordinator model:[/bold]")
	for idx, profile in enumerate(RUNTIME_AGENTS, start=1):
		console.print(
			f"  [cyan]{idx}[/cyan]. {profile['model_name']} "
			f"([dim]{profile['name']} · {profile['model_tier']}[/dim])"
		)

	default_index = DEFAULT_COORDINATOR_INDEX
	if default_index < 1 or default_index > len(RUNTIME_AGENTS):
		default_index = 1
	choice = IntPrompt.ask("Model number", default=default_index)
	if choice < 1 or choice > len(RUNTIME_AGENTS):
		choice = default_index
	return RUNTIME_AGENTS[choice - 1]["model_name"]


async def run_question_loop() -> None:
	if not RUNTIME_AGENTS:
		console.print("[red]No agents configured. Update scripts/model_description.py[/red]")
		return

	console.print(Panel.fit(
		"[bold cyan]🌬️  Aeolus — Ask a Question (Local Ollama)[/bold cyan]\n"
		"[dim]Pick a coordinator model. It may delegate to peers when useful.[/dim]",
		border_style="cyan",
	))

	dashboard_proc = maybe_start_dashboard()
	if dashboard_proc:
		console.print("[green]✓[/green] Dashboard process started")
		console.print("[dim]Dashboard URL: http://localhost:8500[/dim]")

	mode_choice = "ui" # terminal if you want in terminal

	console.print("\n[bold]Starting agents…[/bold]\n")
	nodes: dict[str, AgentNode] = {}
	try:
		for profile in RUNTIME_AGENTS:
			node = AgentNode(
				name=profile["name"],
				capabilities=[],
				capability_description=profile["capability_description"],
				model_tier=profile["model_tier"],
				model_name=profile["model_name"],
			)
			await node.start()
			nodes[profile["model_name"]] = node
			console.print(
				f"  [green]✓[/green] {profile['name']} online "
				f"([dim]{profile['model_tier']} · {profile['model_name']}[/dim])"
			)

		await asyncio.sleep(2)
		known_total = sum(len(node.known_peers) for node in nodes.values())
		console.print(f"\n  [cyan]{known_total}[/cyan] peer-discovery events exchanged")

		if mode_choice == "ui":
			console.print("\n[bold green]Agents are ready![/bold green]")
			console.print("[dim]Please use the Aeolus Dashboard (http://localhost:8500) to ask questions.[/dim]")
			console.print("[dim]Press Ctrl+C to stop.[/dim]")
			# Wait forever while agents handle requests in the background
			await asyncio.Event().wait()
			return

		console.print("\n[dim]Type 'exit' to quit.[/dim]")
		while True:
			coordinator_model = choose_model_once()
			question = Prompt.ask("\n[bold]Your question[/bold]").strip()
			if not question:
				continue
			if question.lower() in {"exit", "quit", "q"}:
				break

			console.rule("[bold yellow]Question Run[/bold yellow]")
			console.print(f"[dim]Coordinator:[/dim] {coordinator_model}")

			try:
				decision = await decide_delegation(question, coordinator_model)
			except asyncio.CancelledError:
				console.print("[red]Request cancelled.[/red]")
				continue
			except Exception as exc:
				console.print(f"[red]Delegation decision failed:[/red] {exc}")
				decision = {
					"delegate": False,
					"specialist_task": question,
					"max_latency_ms": 15000,
					"min_quality": 0.75,
					"reason": "fallback",
				}

			if not decision["delegate"]:
				console.print("[yellow]No delegation needed. Coordinator answering directly.[/yellow]")
				try:
					answer = await direct_answer(question, coordinator_model)
				except asyncio.CancelledError:
					console.print("[red]Request cancelled.[/red]")
					continue
				except Exception as exc:
					console.print(f"[red]Direct answer failed:[/red] {exc}")
					continue
				console.print(Panel(Text(answer[:2500], style="green"), title="[bold green]✅ Answer[/bold green]", border_style="green"))
				continue

			console.print(
				"[yellow]Delegation chosen.[/yellow] "
				f"reason={decision['reason']} "
				f"latency={decision['max_latency_ms']}ms "
				f"min_quality={decision['min_quality']}"
			)

			submitter = nodes[coordinator_model]
			try:
				specialist_result = await submitter.submit_task(
					task_description=decision["specialist_task"],
					max_latency_ms=decision["max_latency_ms"],
					min_quality=decision["min_quality"],
				)
			except asyncio.CancelledError:
				console.print("[red]Delegated request cancelled.[/red]")
				continue
			except Exception as exc:
				console.print(f"[red]Delegated request failed:[/red] {exc}")
				specialist_result = None

			if not specialist_result:
				console.print("[red]✗ Specialist delegation timed out. Falling back to direct answer.[/red]")
				answer = await direct_answer(question, coordinator_model)
				console.print(Panel(Text(answer[:2500], style="green"), title="[bold green]✅ Answer (Fallback)[/bold green]", border_style="green"))
				continue

			specialist_text = specialist_result.strip().lower()
			if (
				"request cannot be completed" in specialist_text
				and "empty" in specialist_text
			):
				console.print("[yellow]Specialist returned an empty-task response. Falling back to direct answer.[/yellow]")
				answer = await direct_answer(question, coordinator_model)
				console.print(Panel(Text(answer[:2500], style="green"), title="[bold green]✅ Answer (Fallback)[/bold green]", border_style="green"))
				continue

			try:
				final_answer = await synthesize_answer(
					question=question,
					coordinator_model=coordinator_model,
					specialist_result=specialist_result,
					reason=decision["reason"],
				)
			except asyncio.CancelledError:
				console.print("[red]Final synthesis cancelled.[/red]")
				continue
			except Exception as exc:
				console.print(f"[red]Final synthesis failed:[/red] {exc}")
				continue
			console.print(Panel(Text(final_answer[:2500], style="green"), title="[bold green]✅ Final Answer[/bold green]", border_style="green"))

	finally:
		console.print("\n[bold]Shutting down agents…[/bold]")
		await asyncio.gather(*[node.stop() for node in nodes.values()])
		if dashboard_proc:
			dashboard_proc.terminate()
			try:
				dashboard_proc.wait(timeout=5)
			except subprocess.TimeoutExpired:
				dashboard_proc.kill()

	console.print("[bold cyan]Session complete![/bold cyan] 🎉")


if __name__ == "__main__":
	try:
		asyncio.run(run_question_loop())
	except KeyboardInterrupt:
		console.print("\n[yellow]Interrupted by user.[/yellow]")
