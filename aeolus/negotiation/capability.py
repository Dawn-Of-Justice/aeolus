"""
aeolus/negotiation/capability.py
Pydantic models for Agent Capability Documents and Negotiation Messages.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────

class ModelTierEnum(str, Enum):
    """Kept for backward compatibility; AgentCapabilityDocument now uses plain str."""
    T1 = "3B"
    T2 = "8B"
    T3 = "LARGE"


class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    OFFLINE = "offline"


class MessageType(str, Enum):
    REQUEST = "REQUEST"
    OFFER = "OFFER"
    COUNTER = "COUNTER"
    ACCEPT = "ACCEPT"
    BIND = "BIND"
    RESULT = "RESULT"
    CANCEL = "CANCEL"


# ── Agent Capability Document (ACD) ───────────────────────────────────────────

class AgentCapabilityDocument(BaseModel):
    """Broadcast by every agent on startup and periodically thereafter."""
    peer_id: str
    name: str
    model_tier: str = "3B"
    model_name: str = "ministral-3b-latest"
    capabilities: list[str]
    capability_description: str
    status: AgentStatus = AgentStatus.AVAILABLE
    max_concurrent_tasks: int = 2
    current_load: int = 0
    supported_protocols: list[str] = ["aeolus/negotiate/v1"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_available(self) -> bool:
        return (
            self.status == AgentStatus.AVAILABLE
            and self.current_load < self.max_concurrent_tasks
        )

    @property
    def load_ratio(self) -> float:
        if self.max_concurrent_tasks == 0:
            return 1.0
        return self.current_load / self.max_concurrent_tasks


# ── Negotiation sub-schemas ───────────────────────────────────────────────────

class TaskRequirements(BaseModel):
    max_latency_ms: int = 10_000
    min_quality: float = 0.7      # 0.0 – 1.0
    priority: int = 5             # 1 (low) – 10 (high)
    max_cost_tokens: Optional[int] = None


class NegotiationTerms(BaseModel):
    estimated_latency_ms: int
    quality_score: float
    model_name: str
    price_tokens: Optional[int] = None
    notes: Optional[str] = None


# ── Negotiation Message ───────────────────────────────────────────────────────

class NegotiationMessage(BaseModel):
    """
    Universal message envelope for all negotiation protocol steps.
    Fields are optional and populated depending on the message type.
    """
    type: MessageType
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: Optional[str] = None        # None = broadcast
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # REQUEST
    task_description: Optional[str] = None
    requirements: Optional[TaskRequirements] = None

    # OFFER / COUNTER
    match_score: Optional[float] = None
    terms: Optional[NegotiationTerms] = None
    adjusted_terms: Optional[NegotiationTerms] = None
    reason: Optional[str] = None

    # ACCEPT / BIND
    binding_terms: Optional[NegotiationTerms] = None
    confirmation: Optional[bool] = None
    execution_start: Optional[datetime] = None

    # RESULT
    output: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
    success: Optional[bool] = None
