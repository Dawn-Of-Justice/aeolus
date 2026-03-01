"""
aeolus/network/node.py
AgentNode — the main runtime for an Aeolus agent.
Connects to NATS, broadcasts capabilities, and handles all negotiation messages.
"""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

import nats
from nats.aio.client import Client as NATSClient

from aeolus.config import settings
from aeolus.exceptions import TransportError, ValidationError
from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    MessageType,
    ModelTierEnum,
    NegotiationMessage,
    TaskRequirements,
)
from aeolus.negotiation.engine import NegotiationEngine
from aeolus.network.messages import (
    decode_acd,
    decode_message,
    encode_acd,
    encode_message,
)

logger = logging.getLogger(__name__)


class AgentNode:
    """
    A single agent node in the Aeolus mesh.
    Runs entirely on asyncio; start with `await node.start()`.
    """

    _file_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        name: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
        capability_description: Optional[str] = None,
        model_tier: Optional[str] = None,
        model_name: Optional[str] = None,
        requester_only: bool = False,
    ):
        self.peer_id = f"{uuid.uuid4().hex[:8]}"
        self.name = name or settings.agent_name
        caps = capabilities or settings.capabilities_list
        tier = model_tier or settings.model_tier.value
        tier_text = tier.value if hasattr(tier, "value") else str(tier)
        model = model_name or settings.active_model

        desc = capability_description or (
            f"I am {self.name}, a {tier_text} agent specialised in: "
            + ", ".join(caps)
        )

        self.acd = AgentCapabilityDocument(
            peer_id=self.peer_id,
            name=self.name,
            model_tier=tier,
            model_name=model,
            capabilities=caps,
            capability_description=desc,
            max_concurrent_tasks=settings.max_concurrent_tasks,
        )

        self.engine = NegotiationEngine(self.acd)
        self._nc: Optional[NATSClient] = None
        self._known_peers: dict[str, AgentCapabilityDocument] = {}
        # task_id -> {request, requirements, offers, result: asyncio.Future}
        self._pending_requests: dict[str, dict] = {}
        self._running = False
        # requester_only: skip provider-side request handling (e.g. dashboard nodes)
        self._requester_only = requester_only
        self._stopping = False

        # Concurrency locks
        self._pending_lock = asyncio.Lock()
        self._peers_lock = asyncio.Lock()
        self._load_lock = asyncio.Lock()

    # -- Lifecycle -----------------------------------------------------------

    async def start(self):
        """Connect to NATS and start the agent."""
        logger.info(f"Starting {self.name} ({self.peer_id})")

        self._nc = await nats.connect(
            settings.nats_url,
            error_cb=self._on_error,
            disconnected_cb=self._on_disconnect,
            reconnected_cb=self._on_reconnect,
        )
        self._running = True

        # Subscribe: capability broadcasts
        await self._nc.subscribe(settings.capability_topic, cb=self._on_capability)

        # Subscribe: broadcast negotiations (REQUESTs from any peer)
        await self._nc.subscribe(
            f"{settings.negotiation_topic_prefix}.broadcast",
            cb=self._on_broadcast_negotiate,
        )

        # Subscribe: direct messages addressed to this peer
        await self._nc.subscribe(
            f"{settings.negotiation_topic_prefix}.{self.peer_id}",
            cb=self._on_direct_message,
        )

        await asyncio.sleep(0.3)   # let subscriptions settle
        await self._broadcast_capabilities()

        # Start periodic heartbeat
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(f"{self.name} is live on {settings.nats_url}")

    async def stop(self, drain_timeout: float = 10.0):
        """Gracefully shut down, waiting for in-flight tasks."""
        self._running = False
        self._stopping = True

        # Cancel heartbeat
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Wait for in-flight tasks
        async with self._pending_lock:
            pending_futures = [
                state["result"]
                for state in self._pending_requests.values()
                if not state["result"].done()
            ]
        if pending_futures:
            logger.info(
                f"[{self.name}] Waiting for {len(pending_futures)} in-flight tasks..."
            )
            await asyncio.wait(pending_futures, timeout=drain_timeout)

        self.acd.status = AgentStatus.OFFLINE
        await self._emit("AGENT_LEAVE", {"peer_id": self.peer_id, "name": self.name})
        if self._nc:
            await self._nc.drain()
        logger.info(f"{self.name} stopped")

    async def _heartbeat_loop(self, interval: float = 15.0):
        """Periodically re-broadcast capabilities so late-joining peers discover us."""
        while self._running:
            await asyncio.sleep(interval)
            if self._running and self._nc:
                try:
                    await self._nc.publish(
                        settings.capability_topic, encode_acd(self.acd)
                    )
                except Exception as exc:
                    logger.warning(f"[{self.name}] Heartbeat broadcast failed: {exc}")

    # -- Task submission (requester role) ------------------------------------

    async def submit_task(
        self,
        task_description: str,
        max_latency_ms: int = 15_000,
        min_quality: float = 0.7,
        priority: int = 5,
    ) -> Optional[str]:
        """
        Broadcast a task REQUEST to the network.
        Blocks until a RESULT is received or the deadline expires.
        Returns the result string, or None on timeout.
        """
        # Validate inputs
        if not task_description or not task_description.strip():
            raise ValidationError("task_description cannot be empty")
        if max_latency_ms <= 0:
            raise ValidationError("max_latency_ms must be positive")
        if not 0.0 <= min_quality <= 1.0:
            raise ValidationError("min_quality must be between 0.0 and 1.0")
        if not 1 <= priority <= 10:
            raise ValidationError("priority must be between 1 and 10")
        if not self._nc or not self._running:
            raise TransportError("Agent is not connected. Call start() first.")

        requirements = TaskRequirements(
            max_latency_ms=max_latency_ms,
            min_quality=min_quality,
            priority=priority,
        )
        request = NegotiationMessage(
            type=MessageType.REQUEST,
            from_agent=self.peer_id,
            task_description=task_description,
            requirements=requirements,
        )
        task_id = request.task_id

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        async with self._pending_lock:
            self._pending_requests[task_id] = {
                "request": request,
                "requirements": requirements,
                "offers": [],
                "result": future,
                "accepted": False,
            }

        logger.info(f"[{self.name}] Submitting task {task_id}: {task_description[:70]}...")
        await self._emit("TASK_SUBMITTED", {
            "task_id": task_id,
            "description": task_description[:100],
            "from": self.peer_id,
        })

        await self._publish_with_retry(
            f"{settings.negotiation_topic_prefix}.broadcast",
            encode_message(request),
        )

        try:
            # Allow generous extra headroom for slow local LLMs (2 round-trip
            # LLM calls: assessment by provider + execution by provider).
            timeout = max_latency_ms / 1000 + 90
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"[{self.name}] Task {task_id} timed out")
            async with self._pending_lock:
                self._pending_requests.pop(task_id, None)
            return None

    # -- NATS callbacks ------------------------------------------------------

    async def _on_capability(self, msg):
        try:
            acd = decode_acd(msg.data)
            if acd.peer_id != self.peer_id:
                async with self._peers_lock:
                    is_new = acd.peer_id not in self._known_peers
                    self._known_peers[acd.peer_id] = acd
                if is_new:
                    logger.info(
                        f"[{self.name}] Discovered peer: {acd.name} "
                        f"({acd.peer_id}) -- {acd.capabilities}"
                    )
                    await self._emit("PEER_DISCOVERED", {
                        "peer_id": acd.peer_id,
                        "name": acd.name,
                        "capabilities": acd.capabilities,
                        "model_tier": acd.model_tier,
                    })
        except Exception as exc:
            logger.warning(f"[{self.name}] Bad ACD: {exc}")

    async def _on_broadcast_negotiate(self, msg):
        # Requester-only nodes (e.g. dashboard) never act as providers.
        if self._requester_only:
            return
        try:
            message = decode_message(msg.data)
            if message.from_agent == self.peer_id:
                return   # ignore own messages
            if message.type == MessageType.REQUEST:
                asyncio.create_task(self._handle_request(message))
        except Exception as exc:
            logger.warning(f"[{self.name}] Bad broadcast msg: {exc}")

    async def _on_direct_message(self, msg):
        try:
            message = decode_message(msg.data)
            dispatch = {
                MessageType.OFFER:  self._handle_offer,
                MessageType.COUNTER: self._handle_counter,
                MessageType.ACCEPT:  self._handle_accept,
                MessageType.BIND:    self._handle_bind,
                MessageType.RESULT:  self._handle_result,
            }
            handler = dispatch.get(message.type)
            if handler:
                asyncio.create_task(handler(message))
        except Exception as exc:
            logger.warning(f"[{self.name}] Bad direct msg: {exc}", exc_info=True)

    # -- Provider-side handlers ----------------------------------------------

    async def _handle_request(self, request: NegotiationMessage):
        await self._emit("REQUEST_RECEIVED", {
            "task_id": request.task_id,
            "from": request.from_agent,
            "to": self.peer_id,
            "description": (request.task_description or "")[:100],
        })

        try:
            offer = await self.engine.evaluate_request(request)
        except Exception as exc:
            logger.error(
                f"[{self.name}] Failed to evaluate request {request.task_id}: {exc}"
            )
            return

        if offer:
            await self._send_direct(request.from_agent, offer)
            await self._emit("OFFER_SENT", {
                "task_id": request.task_id,
                "from": self.peer_id,
                "to": request.from_agent,
                "match_score": offer.match_score,
                "latency_ms": offer.terms.estimated_latency_ms if offer.terms else None,
            })

    async def _handle_bind(self, bind: NegotiationMessage):
        await self._emit("TASK_EXECUTING", {
            "task_id": bind.task_id,
            "executor": self.peer_id,
            "executor_name": self.name,
        })

        async with self._load_lock:
            self.acd.current_load += 1

        try:
            result = await self.engine.handle_bind(bind)
            await self._send_direct(bind.from_agent, result)
            await self._emit("RESULT_SENT", {
                "task_id": bind.task_id,
                "executor": self.peer_id,
                "success": result.success,
                "output_preview": (result.output or "")[:200],
            })
        except Exception as exc:
            logger.error(f"[{self.name}] Task {bind.task_id} execution failed: {exc}")
            error_result = NegotiationMessage(
                type=MessageType.RESULT,
                task_id=bind.task_id,
                from_agent=self.acd.peer_id,
                to_agent=bind.from_agent,
                output=f"Execution error: {exc}",
                success=False,
            )
            await self._send_direct(bind.from_agent, error_result)
            await self._emit("TASK_FAILED", {
                "task_id": bind.task_id,
                "error": str(exc),
            })
        finally:
            async with self._load_lock:
                self.acd.current_load = max(0, self.acd.current_load - 1)

    # -- Requester-side handlers ---------------------------------------------

    async def _handle_offer(self, offer: NegotiationMessage):
        async with self._pending_lock:
            state = self._pending_requests.get(offer.task_id)
            if not state or state.get("accepted"):
                return   # already accepted an offer for this task
            state["offers"].append(offer)

        await self._emit("OFFER_RECEIVED", {
            "task_id": offer.task_id,
            "from": offer.from_agent,
            "to": self.peer_id,
            "match_score": offer.match_score,
        })

        try:
            response = await self.engine.evaluate_offer(offer, state["requirements"])
        except Exception as exc:
            logger.error(
                f"[{self.name}] Failed to evaluate offer for {offer.task_id}: {exc}"
            )
            return

        await self._send_direct(offer.from_agent, response)

        if response.type == MessageType.ACCEPT:
            async with self._pending_lock:
                # Re-check: another offer may have been accepted concurrently
                state = self._pending_requests.get(offer.task_id)
                if not state or state.get("accepted"):
                    return
                state["accepted"] = True

            bind = NegotiationMessage(
                type=MessageType.BIND,
                task_id=offer.task_id,
                from_agent=self.peer_id,
                to_agent=offer.from_agent,
                confirmation=True,
                execution_start=datetime.now(timezone.utc),
                binding_terms=offer.terms,
            )
            await asyncio.sleep(0.05)
            await self._send_direct(offer.from_agent, bind)
            await self._emit("BIND_SENT", {
                "task_id": offer.task_id,
                "from": self.peer_id,
                "to": offer.from_agent,
            })
        elif response.type == MessageType.COUNTER:
            await self._emit("COUNTER_SENT", {
                "task_id": offer.task_id,
                "from": self.peer_id,
                "to": offer.from_agent,
                "reason": response.reason,
            })

    async def _handle_counter(self, counter: NegotiationMessage):
        """Provider received a COUNTER -- re-evaluate as if it's a revised offer."""
        state = self._pending_requests.get(counter.task_id)
        if not state:
            return
        await self._emit("COUNTER_RECEIVED", {
            "task_id": counter.task_id,
            "from": counter.from_agent,
            "to": self.peer_id,
            "reason": counter.reason,
        })
        # Treat adjusted_terms as a new offer
        if counter.adjusted_terms:
            revised = counter.model_copy()
            revised.type = MessageType.OFFER
            revised.terms = counter.adjusted_terms
            await self._handle_offer(revised)

    async def _handle_accept(self, accept: NegotiationMessage):
        await self._emit("ACCEPT_RECEIVED", {
            "task_id": accept.task_id,
            "from": accept.from_agent,
        })

    async def _handle_result(self, result: NegotiationMessage):
        async with self._pending_lock:
            state = self._pending_requests.pop(result.task_id, None)

        if state and not state["result"].done():
            state["result"].set_result(result.output)

        await self._emit("TASK_COMPLETE", {
            "task_id": result.task_id,
            "from": result.from_agent,
            "success": result.success,
            "output_preview": (result.output or "")[:200],
        })
        logger.info(
            f"[{self.name}] Task {result.task_id} complete: "
            f"{(result.output or '')[:80]}..."
        )

    # -- NATS helpers --------------------------------------------------------

    async def _publish_with_retry(
        self, topic: str, data: bytes, max_retries: int = 3
    ):
        """Publish to NATS with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                if not self._nc:
                    raise TransportError("Not connected to NATS")
                await self._nc.publish(topic, data)
                return
            except Exception as exc:
                logger.warning(
                    f"[{self.name}] Publish attempt {attempt + 1}/{max_retries} "
                    f"to {topic} failed: {exc}"
                )
                if attempt == max_retries - 1:
                    raise TransportError(
                        f"Failed to publish to {topic} after {max_retries} retries"
                    ) from exc
                await asyncio.sleep(0.5 * (2 ** attempt))

    async def _send_direct(self, peer_id: str, msg: NegotiationMessage):
        if self._nc:
            try:
                await self._nc.publish(
                    f"{settings.negotiation_topic_prefix}.{peer_id}",
                    encode_message(msg),
                )
            except Exception as exc:
                logger.warning(
                    f"[{self.name}] Failed to send direct msg to {peer_id}: {exc}"
                )

    async def _broadcast_capabilities(self):
        if self._nc:
            try:
                await self._nc.publish(
                    settings.capability_topic, encode_acd(self.acd)
                )
            except Exception as exc:
                logger.warning(
                    f"[{self.name}] Failed to broadcast capabilities: {exc}"
                )
        await self._emit("AGENT_JOIN", {
            "peer_id": self.peer_id,
            "name": self.name,
            "capabilities": self.acd.capabilities,
            "model_tier": self.acd.model_tier,
            "model_name": self.acd.model_name,
        })
        logger.debug(f"[{self.name}] ACD broadcast sent")

    async def _emit(self, event: str, data: dict):
        """Publish a structured event to NATS AND append to events.jsonl."""
        record = {
            "event": event,
            "agent_name": self.name,
            "peer_id": self.peer_id,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        # 1. Write to file (persistent -- dashboard always sees this)
        try:
            log_path = pathlib.Path(settings.event_log_path)
            line = json.dumps(record) + "\n"
            with self._file_lock:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(line)
        except Exception as exc:
            logger.warning(f"[{self.name}] Failed to write event to file: {exc}")

        # 2. Also publish to NATS (real-time, best-effort)
        if self._nc:
            try:
                await self._nc.publish(
                    settings.dashboard_topic, json.dumps(record).encode()
                )
            except Exception as exc:
                logger.warning(f"[{self.name}] Failed to publish event to NATS: {exc}")

    # -- NATS event callbacks ------------------------------------------------

    async def _on_error(self, exc):
        logger.error(f"[{self.name}] NATS error: {exc}")

    async def _on_disconnect(self):
        if self._stopping:
            logger.info(f"[{self.name}] NATS disconnected (graceful shutdown)")
        else:
            logger.warning(f"[{self.name}] NATS disconnected")

    async def _on_reconnect(self):
        logger.info(f"[{self.name}] NATS reconnected -- re-broadcasting capabilities")
        await self._broadcast_capabilities()

    # -- Accessors -----------------------------------------------------------

    @property
    def known_peers(self) -> dict[str, AgentCapabilityDocument]:
        return self._known_peers
