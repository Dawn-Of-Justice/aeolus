"""
aeolus/negotiation/llm.py
LLM client -- Mistral API primary, Ollama fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Optional

import httpx

from aeolus.config import settings
from aeolus.exceptions import LLMError

logger = logging.getLogger(__name__)

_mistral_client = None
_mistral_lock = threading.Lock()


class CircuitBreaker:
    """Simple circuit breaker to fast-fail when a backend is known-down."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0):
        self._failures = 0
        self._threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._last_failure_time = 0.0
        self._state = "closed"  # closed, open, half-open

    @property
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time > self._reset_timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_failure(self):
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self._threshold:
            self._state = "open"
            logger.warning("LLM circuit breaker OPEN -- fast-failing requests")

    def record_success(self):
        if self._state == "half-open":
            logger.info("LLM circuit breaker CLOSED -- backend recovered")
        self._failures = 0
        self._state = "closed"


_circuit_breaker = CircuitBreaker()


def _get_mistral_client():
    global _mistral_client
    if _mistral_client is None:
        with _mistral_lock:
            if _mistral_client is None:  # double-check after lock
                from mistralai import Mistral
                _mistral_client = Mistral(api_key=settings.mistral_api_key)
    return _mistral_client


# -- Public API --------------------------------------------------------------

async def complete(
    messages: list[dict[str, str]],
    model: Optional[str] = None,
    response_format: Optional[dict] = None,
    temperature: float = 0.3,
    max_retries: int = 3,
    timeout_s: float = 120.0,
) -> str:
    """
    Run a chat completion. Uses Mistral API when configured, else Ollama.
    Returns the text content of the assistant's response.
    """
    if _circuit_breaker.is_open:
        raise LLMError("LLM circuit breaker is open -- backend unavailable")

    model = model or settings.active_model

    for attempt in range(max_retries):
        try:
            if settings.use_api:
                result = await asyncio.wait_for(
                    _complete_mistral(messages, model, response_format, temperature),
                    timeout=timeout_s,
                )
            else:
                result = await asyncio.wait_for(
                        _complete_ollama(messages, model, response_format, temperature),
                    timeout=timeout_s,
                )
            _circuit_breaker.record_success()
            return result
        except asyncio.TimeoutError:
            logger.warning(
                f"LLM attempt {attempt + 1}/{max_retries} timed out "
                f"after {timeout_s}s"
            )
            _circuit_breaker.record_failure()
            if attempt == max_retries - 1:
                raise LLMError(
                    f"LLM completion timed out after {max_retries} retries"
                )
        except LLMError:
            raise
        except Exception as exc:
            logger.warning(f"LLM attempt {attempt + 1}/{max_retries} failed: {exc}")
            _circuit_breaker.record_failure()
            if attempt == max_retries - 1:
                raise LLMError(
                    f"LLM completion failed after {max_retries} retries: {exc}"
                ) from exc
            await asyncio.sleep(2 ** attempt)   # exponential back-off


async def complete_json(
    messages: list[dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """complete() + parse JSON response, stripping markdown fences if present."""
    raw = await complete(
        messages,
        model=model,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return _parse_json(raw)


async def embed(text: str) -> list[float]:
    """Get embedding for semantic matching. Mistral API -> Ollama fallback."""
    if settings.use_api:
        try:
            client = _get_mistral_client()
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: client.embeddings.create(
                    model="mistral-embed",
                    inputs=[text],
                ),
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.warning(f"Mistral embed failed, falling back to Ollama: {exc}")

    # Ollama embeddings
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
    except Exception as exc:
        raise LLMError(f"Embedding failed (both Mistral and Ollama): {exc}") from exc


# -- Internal implementations ------------------------------------------------

async def _complete_mistral(
    messages: list[dict[str, str]],
    model: str,
    response_format: Optional[dict],
    temperature: float,
) -> str:
    client = _get_mistral_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.complete(**kwargs),
    )
    if not response or not response.choices:
        raise LLMError("Mistral API returned empty response")
    return response.choices[0].message.content


async def _complete_ollama(
    messages: list[dict[str, str]],
        model: str,
    response_format: Optional[dict],
    temperature: float,
) -> str:
    payload: dict[str, Any] = {
            "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if response_format and response_format.get("type") == "json_object":
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content")
        if content is None:
            raise LLMError("Ollama returned response without content")
        return content


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Failed to parse LLM JSON response: {exc}") from exc
