# Aeolus

**A peer-to-peer semantic negotiation layer for autonomous AI agents.**

Aeolus fills the gap left by A2A and MCP: decentralised discovery, strategic capability matching, and SLA-based task routing — with no central server or registry.

---

## Overview

Current agent protocols (A2A, MCP) assume a client-server model — one agent asks, one executes. Aeolus treats agents as **equals** on a mesh network where they can:

- **Discover** each other automatically via mDNS (zero-config, no registry)
- **Negotiate** task terms strategically with a 4-step protocol (REQUEST → OFFER → COUNTER → ACCEPT → BIND)
- **Match** capabilities semantically using natural language and embedding similarity
- **Route** tasks to the right model tier automatically (3B → 8B → API)
- **Visualise** the live network in a real-time Streamlit dashboard

This is the "Layer 9" — the semantic negotiation layer the agent ecosystem is missing.

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Layer 3: Dashboard (Streamlit)         │
│  Live topology · Negotiation logs       │
├─────────────────────────────────────────┤
│  Layer 2: Negotiation Engine            │
│  Semantic matching · 4-step protocol    │
│  SLA evaluation · LLM-mediated terms    │
├─────────────────────────────────────────┤
│  Layer 1: P2P Mesh (NATS)               │
│  Transport · mDNS discovery             │
│  GossipSub · Cryptographic PeerIDs      │
└─────────────────────────────────────────┘
```

### Negotiation Protocol

```
Agent A (requester)          NATS            Agent B (provider)
       |                       |                      |
       |-- REQUEST ----------->|--------------------->|
       |                       |                      |-- LLM assesses fit
       |                       |<---- OFFER ----------|
       |-- COUNTER (opt) ----->|--------------------->|
       |                       |<---- OFFER (rev) ----|
       |-- ACCEPT ------------>|--------------------->|
       |                       |<---- BIND -----------|
       |                       |    ... execution ... |
       |                       |<---- RESULT ---------|
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- [NATS server](https://docs.nats.io/running-a-nats-service/introduction/installation)
- An LLM backend — either:
  - **Mistral API** (set `MISTRAL_API_KEY` in `.env`)
  - **Ollama** (local, set `LOCAL_ONLY=true`) with a compatible model such as `ministral:3b`

### Install

```bash
git clone https://github.com/aeolus-ai/aeolus.git
cd aeolus
pip install -e ".[dashboard,dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env — at minimum set MISTRAL_API_KEY or LOCAL_ONLY=true
```

### Run NATS

```bash
# Option A: direct install
nats-server

# Option B: Docker
docker run -d -p 4222:4222 nats
```

### Start Agents

Open separate terminals for each agent:

```bash
# Agent Alpha — text processing
python scripts/run_agent.py \
  --name agent-alpha \
  --caps "text summarisation,sentiment analysis,question answering" \
  --desc "Fast text processing agent" \
  --tier 3B

# Agent Beta — translation
python scripts/run_agent.py \
  --name agent-beta \
  --caps "translation,text rewriting,language detection" \
  --desc "Multilingual translation agent" \
  --tier 3B

# Agent Gamma — code review (higher-tier)
python scripts/run_agent.py \
  --name agent-gamma \
  --caps "code review,security analysis,complex reasoning" \
  --desc "Advanced reasoning agent" \
  --tier 8B
```

### Launch the Dashboard

```bash
streamlit run aeolus/dashboard/app.py
# Open http://localhost:8501
```

### Run the Demo Scenario

```bash
python scripts/demo_scenario.py
```

This submits several tasks across the mesh — summarisation, translation, and a code review that auto-escalates to the higher-tier agent — and prints results to stdout while the dashboard updates in real time.

---

## Project Structure

```
aeolus/
├── aeolus/
│   ├── config.py              # Global configuration (env vars, model tiers)
│   ├── exceptions.py          # Custom exception types
│   ├── network/               # Layer 1: P2P mesh
│   │   ├── node.py            # AgentNode — main agent process
│   │   ├── discovery.py       # Peer registry & heartbeats
│   │   ├── transport.py       # NATS messaging transport
│   │   └── messages.py        # Message schemas
│   ├── negotiation/           # Layer 2: Negotiation engine
│   │   ├── engine.py          # 4-step negotiation orchestration
│   │   ├── capability.py      # Agent Capability Document (Pydantic)
│   │   ├── matcher.py         # Semantic similarity matching
│   │   ├── sla.py             # SLA constraint evaluation
│   │   ├── prompts.py         # LLM system prompts
│   │   └── llm.py             # LLM client (Mistral API + Ollama fallback)
│   ├── tasks/                 # Task execution
│   │   ├── lifecycle.py       # Task state machine
│   │   ├── router.py          # Multi-tier routing logic
│   │   └── executor.py        # Task execution
│   └── dashboard/             # Layer 3: Visual dashboard
│       ├── app.py             # Streamlit app
│       └── graph.py           # Network topology graph
├── scripts/
│   ├── run_agent.py           # CLI to start an agent node
│   ├── run_dashboard.py       # CLI to start the dashboard
│   ├── demo_scenario.py       # Scripted 3-agent demo
│   └── model_description.py   # Print agent capability descriptions
├── spikes/                    # Standalone proof-of-concept scripts
│   ├── spike_mistral_api.py   # Verify Mistral API + JSON mode
│   ├── spike_nats.py          # Verify NATS pub/sub
│   ├── spike_ollama_fc.py     # Verify Ollama function calling
│   └── spike_streamlit.py     # Verify live Streamlit graph updates
├── tests/                     # Unit tests
├── docs/                      # Architecture diagrams
├── .env.example               # Environment variable template
└── pyproject.toml             # Project metadata and dependencies
```

---

## Configuration Reference

All settings are read from environment variables or a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `MISTRAL_API_KEY` | _(empty)_ | Mistral API key. When set, the Mistral API is used as the primary LLM backend. |
| `LOCAL_ONLY` | `false` | Set to `true` to force Ollama even when an API key is present. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL for local inference. |
| `OLLAMA_MODEL` | `ministral:3b` | Default Ollama model. |
| `TIER1_MODEL` | `ministral-3b-latest` | Mistral API model for the 3B tier. |
| `TIER2_MODEL` | `ministral-8b-latest` | Mistral API model for the 8B tier. |
| `TIER3_MODEL` | `mistral-large-latest` | Mistral API model for the LARGE tier. |
| `AGENT_NAME` | `agent-alpha` | Name of this agent on the mesh. |
| `AGENT_CAPABILITIES` | `text summarisation,...` | Comma-separated capability list. |
| `MODEL_TIER` | `3B` | Tier of this agent (`3B`, `8B`, or `LARGE`). |
| `MAX_CONCURRENT_TASKS` | `2` | Max tasks this agent will accept simultaneously. |
| `NATS_URL` | `nats://localhost:4222` | NATS server URL. |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## LLM Backend

Aeolus supports two LLM backends and selects automatically:

| Condition | Backend used |
|---|---|
| `MISTRAL_API_KEY` is set and `LOCAL_ONLY=false` | Mistral API |
| `LOCAL_ONLY=true` or no API key | Ollama |

The `llm.py` module includes a circuit breaker (auto fast-fail after repeated errors) and exponential back-off on retries. Embeddings fall back from `mistral-embed` to `nomic-embed-text` via Ollama.

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests cover discovery, negotiation, semantic matching, SLA evaluation, task lifecycle, and routing.

---

## Verification Scripts

The `spikes/` directory contains standalone scripts to verify each integration point independently before running the full system:

```bash
# Verify Mistral API access and JSON mode
python spikes/spike_mistral_api.py

# Verify NATS pub/sub
python spikes/spike_nats.py

# Verify Ollama function calling
python spikes/spike_ollama_fc.py

# Verify Streamlit live graph
streamlit run spikes/spike_streamlit.py
```

---

## Roadmap

- **DID identity** — W3C Decentralised Identifiers for production-grade trust
- **DHT discovery** — Kademlia-based internet-scale peer discovery
- **A2A bridge** — Expose each P2P agent as an A2A-compatible endpoint
- **On-chain SLAs** — Enforceable service agreements via smart contracts
- **Multi-hop task chains** — Agent A orchestrates pipelines across B and C

---

## License

MIT — see [LICENSE](LICENSE).
