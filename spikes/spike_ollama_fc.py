#!/usr/bin/env python3
"""Spike S3: Ollama function calling test (placeholder).

Tests that Ministral 3B can generate structured JSON responses
via Ollama's function calling / JSON mode.

Prerequisites:
    1. Install Ollama: https://ollama.ai
    2. Pull model: ollama pull ministral:3b
    3. pip install ollama

Usage:
    python spikes/spike_ollama_fc.py

NOTE: This is a placeholder — fill in when Ollama is installed.
"""

from __future__ import annotations


def main() -> None:
    print("🔮 Spike S3: Ollama Function Calling")
    print("=" * 50)

    try:
        import ollama  # type: ignore
    except ImportError:
        print("⚠️  ollama package not installed.")
        print("   Install Ollama first, then: pip install ollama")
        print("   Skipping this spike for now.")
        print()
        print("   When ready, this spike will test:")
        print("   1. Chat completion with JSON mode")
        print("   2. Function calling for structured negotiation responses")
        print("   3. Embedding generation for semantic matching")
        return

    # --- Test 1: JSON mode chat completion ---
    print("\n📝 Test 1: JSON mode chat completion")
    try:
        response = ollama.chat(
            model="ministral:3b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an agent assessing task capability. "
                        'Respond with JSON: {"can_handle": bool, "match_score": float, "reasoning": string}'
                    ),
                },
                {
                    "role": "user",
                    "content": "Can you summarise a 500-word article about renewable energy?",
                },
            ],
            format="json",
            options={"temperature": 0.3},
        )
        content = response["message"]["content"]
        print(f"   Response: {content}")

        import json

        parsed = json.loads(content)
        print(f"   ✅ Valid JSON: {parsed}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # --- Test 2: Embedding generation ---
    print("\n📝 Test 2: Embedding generation")
    try:
        response = ollama.embed(model="nomic-embed-text", input="text summarisation")
        emb = response["embeddings"][0]
        print(f"   ✅ Embedding dimension: {len(emb)}")
        print(f"   First 5 values: {emb[:5]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        print("   (You may need: ollama pull nomic-embed-text)")

    print("\n🏁 Spike complete.")


if __name__ == "__main__":
    main()
