"""
scripts/run_agent.py
CLI entry point to start an Aeolus agent node.

Usage:
  python scripts/run_agent.py --name agent-alpha --tier 3B \
    --caps "text summarisation,sentiment analysis,question answering"

  # Or configure via .env and run:
  python scripts/run_agent.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from dotenv import load_dotenv
load_dotenv()

from aeolus.network.node import AgentNode
from aeolus.config import settings
from rich.logging import RichHandler

logging.basicConfig(
    level=settings.log_level,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)


def parse_args():
    p = argparse.ArgumentParser(description="Start an Aeolus agent node")
    p.add_argument("--name", default=None, help="Agent name (default: from .env)")
    p.add_argument(
        "--tier", default=None, choices=["3B", "8B", "LARGE"],
        help="Model tier (default: from .env)",
    )
    p.add_argument("--caps", default=None, help="Comma-separated capabilities")
    p.add_argument("--desc", default=None, help="Capability description")
    return p.parse_args()


async def main():
    args = parse_args()

    caps = [c.strip() for c in args.caps.split(",")] if args.caps else None

    node = AgentNode(
        name=args.name,
        capabilities=caps,
        capability_description=args.desc,
        model_tier=args.tier,
    )

    loop = asyncio.get_event_loop()

    def _shutdown():
        loop.create_task(node.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass   # Windows doesn't support add_signal_handler for all signals

    await node.start()

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
