"""
aeolus/config.py
Global configuration loaded from environment variables / .env file.
"""
from __future__ import annotations

from enum import Enum
from pydantic_settings import BaseSettings
from pydantic import Field


class ModelTier(str, Enum):
    T1 = "3B"     # ministral-3b-latest — fast, cheap
    T2 = "8B"     # ministral-8b-latest — balanced
    T3 = "LARGE"  # mistral-large-latest — powerful, complex reasoning


class Settings(BaseSettings):
    # ── Mistral API ───────────────────────────────────────────────────────────
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")

    # Model names per tier (overridable via env)
    tier1_model: str = Field(default="ministral-3b-latest", alias="TIER1_MODEL")
    tier2_model: str = Field(default="ministral-8b-latest", alias="TIER2_MODEL")
    tier3_model: str = Field(default="mistral-large-latest", alias="TIER3_MODEL")

    # ── Ollama fallback ───────────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="ministral:3b", alias="OLLAMA_MODEL")
    local_only: bool = Field(default=False, alias="LOCAL_ONLY")

    # ── NATS transport ────────────────────────────────────────────────────────
    nats_url: str = Field(default="nats://localhost:4222", alias="NATS_URL")

    # ── Agent identity ────────────────────────────────────────────────────────
    agent_name: str = Field(default="agent-alpha", alias="AGENT_NAME")
    agent_capabilities: str = Field(
        default="text summarisation,sentiment analysis,question answering",
        alias="AGENT_CAPABILITIES",
    )
    model_tier: ModelTier = Field(default=ModelTier.T1, alias="MODEL_TIER")
    max_concurrent_tasks: int = Field(default=2, alias="MAX_CONCURRENT_TASKS")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard_port: int = Field(default=8501, alias="DASHBOARD_PORT")

    # ── Observability ─────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Peer discovery ─────────────────────────────────────────────────────
    peer_timeout: float = Field(default=30.0, alias="PEER_TIMEOUT")

    # ── Event logging ──────────────────────────────────────────────────────
    event_log_path: str = Field(default="events.jsonl", alias="EVENT_LOG_PATH")

    # ── NATS topic scheme ─────────────────────────────────────────────────────
    capability_topic: str = "aeolus.capabilities"
    negotiation_topic_prefix: str = "aeolus.negotiate"
    dashboard_topic: str = "aeolus.dashboard"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }

    # ── Computed helpers ──────────────────────────────────────────────────────
    @property
    def capabilities_list(self) -> list[str]:
        return [c.strip() for c in self.agent_capabilities.split(",") if c.strip()]

    @property
    def active_model(self) -> str:
        return {
            ModelTier.T1: self.tier1_model,
            ModelTier.T2: self.tier2_model,
            ModelTier.T3: self.tier3_model,
        }[self.model_tier]

    @property
    def use_api(self) -> bool:
        """True when Mistral API key is present and local_only is not set."""
        return bool(self.mistral_api_key) and not self.local_only


settings = Settings()
