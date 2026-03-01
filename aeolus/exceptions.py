"""
aeolus/exceptions.py
Custom exception hierarchy for the Aeolus framework.
"""
from __future__ import annotations


class AeolusError(Exception):
    """Base exception for all Aeolus errors."""


class TransportError(AeolusError):
    """NATS connection or publish failure."""


class NegotiationError(AeolusError):
    """Error during negotiation protocol."""


class TaskExecutionError(AeolusError):
    """Error executing a delegated task."""


class LLMError(AeolusError):
    """Error calling the LLM (Mistral or Ollama)."""


class ConfigurationError(AeolusError):
    """Invalid or missing configuration."""


class ValidationError(AeolusError):
    """Invalid message or parameter."""
