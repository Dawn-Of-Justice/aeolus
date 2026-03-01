"""Aeolus -- P2P Semantic Negotiation Layer for Autonomous AI Agents."""

__version__ = "0.1.0"

from aeolus.config import Settings, settings
from aeolus.exceptions import (
    AeolusError,
    ConfigurationError,
    LLMError,
    NegotiationError,
    TaskExecutionError,
    TransportError,
    ValidationError,
)
from aeolus.negotiation.capability import (
    AgentCapabilityDocument,
    AgentStatus,
    MessageType,
    ModelTierEnum,
    NegotiationMessage,
    NegotiationTerms,
    TaskRequirements,
)
from aeolus.network.node import AgentNode

__all__ = [
    # Core runtime
    "AgentNode",
    # Models
    "AgentCapabilityDocument",
    "NegotiationMessage",
    "NegotiationTerms",
    "TaskRequirements",
    "MessageType",
    "AgentStatus",
    "ModelTierEnum",
    # Config
    "Settings",
    "settings",
    # Exceptions
    "AeolusError",
    "TransportError",
    "NegotiationError",
    "TaskExecutionError",
    "LLMError",
    "ConfigurationError",
    "ValidationError",
]
