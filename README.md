# Aeolus 

**A peer-to-peer agent negotiation layer — decentralised discovery, semantic matching, and SLA-based task routing for autonomous AI agents.**

Built for the [Mistral Worldwide Hackathon](https://worldwide-hackathon.mistral.ai/) (Feb 28–Mar 1, 2026).

---

## What is Aeolus?

Aeolus is a **Layer 9** (Semantic Negotiation Layer) for AI agents. While A2A handles agent communication and MCP handles tool access, neither supports truly decentralised peer-to-peer networks where agents are equals. Aeolus fills that gap.

**Agents can:**
- 🔍 **Discover** each other on a local network (zero-config mDNS)
- 🤝 **Negotiate** task terms strategically (not just agree)
- 🧠 **Match** capabilities semantically (natural language, not ontologies)
- 📊 **Route** tasks to the right model tier automatically (3B → 8B → API)
- 📈 **Visualise** the live network in a real-time dashboard

## Architecture

```
┌─────────────────────────────────────────┐
│  Layer 3: Dashboard (Streamlit)         │
│  Live topology · Negotiation logs       │
├─────────────────────────────────────────┤
│  Layer 2: Negotiation Engine            │
│  Ministral 3B · Semantic matching       │
│  4-step protocol · SLA evaluation       │
├─────────────────────────────────────────┤
│  Layer 1: P2P Mesh (NATS)               │
│  Transport · mDNS discovery             │
│  GossipSub · Cryptographic PeerIDs      │
└─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- [NATS server](https://docs.nats.io/running-a-nats-service/introduction/installation)
- [Ollama](https://ollama.ai) with `ministral:3b` (for LLM features)

### Install

```bash
pip install -r requirements.txt
```

### Run NATS

```bash
# Option A: Direct install
nats-server &

# Option B: Docker
docker run -d -p 4222:4222 nats
```

### Start Agents

```bash
# Terminal 1 — Agent Alpha (summarisation)
python scripts/run_agent.py \
  --name agent-alpha \
  --caps "text summarisation,sentiment analysis,question answering" \
  --desc "Fast text processing agent" \
  --tier 3B

# Terminal 2 — Agent Beta (translation)
python scripts/run_agent.py \
  --name agent-beta \
  --caps "translation,text rewriting,language detection" \
  --desc "Multilingual translation agent" \
  --tier 3B

# Terminal 3 — Agent Gamma (code review)
python scripts/run_agent.py \
  --name agent-gamma \
  --caps "code review,security analysis,complex reasoning" \
  --desc "Advanced reasoning agent" \
  --tier 8B
```

### Start Dashboard

```bash
streamlit run aeolus/dashboard/app.py
# Open http://localhost:8501
```

### Run Demo Scenario

```bash
python scripts/demo_scenario.py
```

## Project Structure

```
aeolus/
├── aeolus/
│   ├── config.py              # Global configuration
│   ├── network/               # Layer 1: P2P mesh
│   │   ├── node.py            # AgentNode (main agent process)
│   │   ├── discovery.py       # Peer registry & heartbeats
│   │   └── transport.py       # NATS messaging transport
│   ├── negotiation/           # Layer 2: Negotiation engine
│   │   ├── engine.py          # 4-step negotiation protocol
│   │   ├── capability.py      # Agent Capability Document
│   │   ├── messages.py        # Negotiation message schemas
│   │   ├── matcher.py         # Semantic similarity matching
│   │   ├── sla.py             # SLA constraint evaluation
│   │   ├── prompts.py         # LLM system prompts
│   │   └── llm.py             # Ollama client (placeholder)
│   ├── tasks/                 # Task execution
│   │   ├── lifecycle.py       # Task state machine
│   │   ├── router.py          # Multi-tier routing
│   │   └── executor.py        # Task execution
│   └── dashboard/             # Layer 3: Visual dashboard
│       ├── app.py             # Streamlit app
│       ├── graph.py           # Network topology graph
│       ├── logs.py            # Event log formatting
│       └── metrics.py         # Aggregate statistics
├── scripts/                   # CLI entry points
├── spikes/                    # Pre-hackathon PoC scripts
├── tests/                     # Unit tests
└── docs/                      # Pitch deck & diagrams
```

## Negotiation Protocol

```
Agent A (requester)          NATS            Agent B (provider)
       |                       |                      |
       |-- REQUEST ----------->|--------------------->|
       |                       |                      |-- assess fit
       |                       |<---- OFFER ----------|
       |-- COUNTER (opt) ----->|--------------------->|
       |                       |<---- OFFER (rev) ----|
       |-- ACCEPT ------------>|--------------------->|
       |                       |<---- BIND -----------|
       |                       |    ... execution ... |
       |                       |<---- RESULT ---------|
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT

## Hackathon

- **Event**: Mistral Worldwide Hackathon 2026
- **Dates**: February 28 – March 1, 2026
- **Target Award**: Best Use of Agent Skills
