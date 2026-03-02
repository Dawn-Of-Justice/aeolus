# Aeolus 

**A peer-to-peer agent negotiation layer — decentralised discovery, semantic matching, and SLA-based task routing for autonomous AI agents.**


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

### Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Start NATS server
nats-server &

# Run the main application
python scripts/question_run_with_ollama_locally.py
```

### Configure Agent Behaviour

Edit `scripts/model_description.py` to customise agent capabilities, descriptions, and model tiers.

## License

[MIT](LICENSE)
