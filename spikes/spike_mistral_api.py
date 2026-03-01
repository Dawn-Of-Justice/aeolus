"""
spikes/spike_mistral_api.py
Spike S3 — verify Mistral API access + JSON function-calling mode.

Set MISTRAL_API_KEY in .env or environment before running.

Run: python spikes/spike_mistral_api.py
Expected output: "✅ Mistral API spike PASSED"
"""
from __future__ import annotations

import asyncio
import json
import os

from dotenv import load_dotenv
load_dotenv()

from aeolus.negotiation import llm
from aeolus.config import settings


async def run():
    if not settings.use_api:
        print("⚠️  MISTRAL_API_KEY not set or LOCAL_ONLY=true — testing Ollama fallback")
    else:
        print(f"✓ Using Mistral API — model: {settings.active_model}")

    # 1. Plain completion
    print("\n── Test 1: Plain completion ──────────────────────────────────────")
    result = await llm.complete(
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Be brief."},
            {"role": "user", "content": "Name three renewable energy sources. One sentence."},
        ],
        temperature=0.3,
    )
    print(f"Response: {result}")
    assert len(result) > 10, "Response too short"
    print("✓ Plain completion OK")

    # 2. JSON mode
    print("\n── Test 2: JSON mode (negotiation assessment) ────────────────────")
    assessment = await llm.complete_json(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strategic AI agent. Respond ONLY with valid JSON "
                    "matching the requested schema."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Your capabilities: text summarisation, sentiment analysis\n"
                    "Task: Summarise a 500-word article about climate change\n"
                    "Respond with: "
                    '{"should_offer": true/false, "match_score": 0.0-1.0, '
                    '"reasoning": "...", "estimated_latency_ms": <int>, '
                    '"quality_score": 0.0-1.0, "counter_terms": null}'
                ),
            },
        ],
        temperature=0.1,
    )
    print(f"Assessment: {json.dumps(assessment, indent=2)}")
    assert "should_offer" in assessment, "'should_offer' missing from response"
    assert "match_score" in assessment, "'match_score' missing from response"
    print("✓ JSON mode OK")

    # 3. Embedding (optional)
    print("\n── Test 3: Embeddings ────────────────────────────────────────────")
    try:
        emb = await llm.embed("text summarisation task")
        print(f"Embedding dim: {len(emb)} (first 5: {emb[:5]})")
        assert len(emb) > 100, "Embedding too short"
        print("✓ Embeddings OK")
    except Exception as exc:
        print(f"⚠️  Embeddings unavailable (non-fatal): {exc}")

    print("\n✅ Mistral API spike PASSED")


if __name__ == "__main__":
    asyncio.run(run())
