# Building a P2P agent negotiation layer for the Mistral Hackathon

**A decentralized peer-to-peer agent negotiation layer is technically feasible as a hackathon prototype — and the timing is ideal.** The agent protocol landscape as of early 2026 has standardized on A2A (agent-to-agent) and MCP (agent-to-tool), but both assume client-server architectures. The critical missing piece — a semantic negotiation layer for truly decentralized agent networks — exists only in research papers and early prototypes. This gap represents both a real technical need and a compelling hackathon project. The Mistral Worldwide Hackathon (February 28–March 1, 2026) [Algo-Mania](https://algo-mania.com/en/blog/hackathons-coding/mistral-hackathon-2026-french-ai-shines-across-7-cities-worldwide/) explicitly rewards agent-focused projects through a "Best Use of Agent Skills" special award, and Ministral 3B's ability to run on consumer hardware with native function calling makes it a natural fit for local P2P agent nodes.

---

## The protocol landscape has standardized but left P2P unaddressed

The agent communication ecosystem consolidated rapidly through 2025. **Google's A2A protocol (v0.3)**, now under the Linux Foundation with 150+ supporting organizations, [Google Cloud](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade) handles agent-to-agent communication via Agent Cards, JSON-RPC [Platform Engineering](https://platformengineering.com/editorial-calendar/best-of-2025/google-cloud-unveils-agent2agent-protocol-a-new-standard-for-ai-agent-interoperability-2/) 2.0, and task lifecycle management. [GitHub](https://github.com/google/A2A/blob/main/README.md) **Anthropic's MCP (spec v2025-11-25)**, [Anthropic](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation) governed by the Agentic AI Foundation with 97M+ monthly SDK downloads, [Anthropic](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation) handles agent-to-tool integration. IBM's ACP merged into A2A in August 2025, further consolidating the landscape. [Lfaidata](https://lfaidata.foundation/communityblog/2025/08/29/acp-joins-forces-with-a2a-under-the-linux-foundations-lf-ai-data/) The industry consensus is clear: "Build with any framework, equip with MCP, communicate with A2A." [A2a-protocol](https://a2a-protocol.org/latest/)

Both protocols, however, assume a **client-server model**. A2A explicitly designates "client agents" and "remote agents" — one asks, one executes. [GitHub](https://github.com/google/A2A/blob/main/README.md) MCP connects hosts to servers through clients. [GitHub](https://github.com/modelcontextprotocol/typescript-sdk) [TrueFoundry](https://www.truefoundry.com/blog/mcp-vs-a2a) Neither supports peer discovery, decentralized identity, or strategic negotiation between equal agents. Three initiatives attempt to fill this gap:

- **AGNTCY (Cisco/Linux Foundation)** provides decentralized directory, identity, and messaging infrastructure for an "Internet of Agents," [Google Developers](https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/) with 65+ supporting companies. [Linux Foundation](https://www.linuxfoundation.org/press/linux-foundation-welcomes-the-agntcy-project-to-standardize-open-multi-agent-system-infrastructure-and-break-down-ai-agent-silos) It works *with* A2A and MCP but adds the missing discovery and identity layers. [Linux Foundation](https://www.linuxfoundation.org/press/linux-foundation-welcomes-the-agntcy-project-to-standardize-open-multi-agent-system-infrastructure-and-break-down-ai-agent-silos) [A2a-protocol](https://a2a-protocol.org/latest/)
- **Agent Network Protocol (ANP)** offers a fully P2P architecture with W3C DID-based identity, dynamic meta-protocol negotiation, and semantic capability descriptions. [GitHub +2](https://github.com/agent-network-protocol/AgentNetworkProtocol) Its Python SDK (AgentConnect) is functional but community-driven with limited adoption. [GitHub](https://github.com/agent-network-protocol/AgentConnect)
- **The "Layer 9" concept** — a Semantic Negotiation Layer — was formalized [arXiv](https://arxiv.org/html/2511.19699) in Charles Fleming's November 2025 paper proposing two new layers atop the traditional stack: L8 for communication structure (where A2A operates) and L9 for shared meaning, semantic grounding, and coordination. [arXiv](https://www.arxiv.org/pdf/2511.19699) Salesforce's research team independently identified the same need, noting the **"echoing problem"** where LLM agents trained to be helpful agree with each other rather than negotiate strategically. [StartupHub.ai](https://www.startuphub.ai/ai-news/ai-research/2025/ai-agent-negotiation-needs-a-semantic-layer/)

No production-ready protocol combines all three requirements — decentralized discovery, semantic negotiation, and SLA-based coordination. This is the gap a hackathon prototype can target.

## Ministral 3B is purpose-built for local P2P agent nodes

Mistral's December 2025 Ministral 3 family (3B, 8B, 14B parameters, all Apache 2.0) was designed for edge deployment [Mistral AI](https://mistral.ai/news/mistral-3) through cascade distillation from Mistral Small 3.1. [arXiv](https://arxiv.org/html/2601.08584v1) **Ministral 3B is the sweet spot for P2P agents**: at ~2–3 GB quantized (Q4_K_M), it runs on consumer laptop CPUs, [LM Studio](https://lmstudio.ai/models/ministral) achieves **385 tokens/second on an RTX 5090**, [NVIDIA Developer](https://developer.nvidia.com/blog/nvidia-accelerated-mistral-3-open-models-deliver-efficiency-accuracy-at-any-scale/) and even runs in-browser via WebGPU. [Simon Willison](https://simonwillison.net/2025/Dec/2/introducing-mistral-3/)

Critical capabilities for a negotiation layer are built in. Native **function calling** lets agents invoke protocol operations. [APXML](https://apxml.com/models/ministral-3-3b) **JSON mode with schema enforcement** enables structured message passing. [Mistral AI](https://docs.mistral.ai/capabilities/structured_output/json_mode) A **256K token context window** accommodates full negotiation histories. [APXML](https://apxml.com/models/ministral-3-3b) [arXiv](https://arxiv.org/html/2601.08584v1) Ministral instruct models generate an order of magnitude fewer tokens than comparable models for equivalent tasks [Medium](https://medium.com/data-science-in-your-pocket/mistral-3-best-open-sourced-model-is-here-3b93a6b2b2e8) [Mistral AI](https://mistral.ai/news/mistral-3) — directly reducing per-turn latency in multi-round negotiation.

The multi-tier deployment model maps naturally to a heterogeneous P2P network. Lightweight peers run Ministral 3B for fast, cheap operations (discovery broadcasts, capability matching, simple negotiations). Capable nodes run 8B or 14B for complex reasoning tasks (multi-issue SLA negotiation, conflict resolution). The Mistral API provides frontier-class fallback for tasks exceeding local capability. This tiered architecture mirrors real network heterogeneity — laptops, desktops, and servers each contribute proportionally.

## Four technical challenges define the feasibility boundary

**Decentralized discovery** is the most tractable challenge. libp2p provides production-grade mDNS (local LAN, zero-config) and Kademlia DHT (internet-scale) out of the box. [Medium](https://medium.com/rahasak/libp2p-pubsub-peer-discovery-with-kademlia-dht-c8b131550ac7) The Python implementation (py-libp2p v0.4.0) now supports mDNS discovery and GossipSub 1.2, though it remains under active development. [Readthedocs](https://py-libp2p.readthedocs.io/) For a hackathon demo on a shared network, mDNS alone suffices — agents announce themselves and discover peers automatically with zero configuration. [GitHub](https://github.com/libp2p/specs/blob/master/discovery/mdns.md) Two recent papers — "A Gossip-Enhanced Communication Substrate for Agentic AI" (December 2025) and "Revisiting Gossip Protocols for Multi-Agent Systems" (August 2025) — argue gossip protocols fill critical gaps that structured protocols like A2A cannot, enabling emergent coordination and decentralized state propagation. [arXiv](https://arxiv.org/abs/2512.03285)

**Semantic capability matching** is where LLMs provide a paradigm shift. Traditional approaches required formal ontologies (OWL/RDF) for agents to understand each other's capabilities. [arXiv](https://arxiv.org/html/2507.10644v3) With Ministral models, agents can describe capabilities in natural language and use **embedding similarity** to match requests with providers. The Symplex Protocol (GitHub: olserra/agent-semantic-protocol) demonstrates this approach in Go over libp2p, using cosine similarity on semantic intent vectors. For a hackathon, a simplified version — agents publish natural-language capability descriptions, an embedding model computes similarity scores, and matches above a threshold trigger negotiation — is both feasible and compelling.

**SLA-based negotiation** is the most novel and challenging component. The AgentSLA DSL (Jouneaux & Cabot, November 2025) provides a formal framework for specifying service-level agreements between agents, extending ISO/IEC 25010 with AI-specific quality metrics. [arxiv](https://arxiv.org/html/2511.02885) The "AgenticPay" system (February 2026) demonstrates multi-agent LLM negotiation across 110+ task types. However, research consistently warns about LLM negotiation limitations: agents **anchor at ZOPA extremes** and exhibit the echoing problem. [arXiv](https://arxiv.org/html/2512.13063v1) The hackathon prototype should use a hybrid approach — deterministic rules for hard constraints [Salesforce](https://www.salesforce.com/blog/agent-to-agent-interaction/?bc=OTH) (latency thresholds, memory limits) with LLM-mediated negotiation for soft preferences (task priority, quality tradeoffs). [Salesforce](https://www.salesforce.com/blog/agent-to-agent-interaction/?bc=OTH)

**Real-time hardware capacity trading** is the stretch goal that makes the demo visually compelling but is technically hardest. Agents would need to report current hardware utilization, estimate inference capacity, and bid on tasks from resource-constrained peers. This requires reliable benchmarking, which is difficult to fake. A simplified version — agents report static capability tiers (e.g., "CPU-only/3B," "GPU/8B," "GPU/14B") and route tasks to the most capable available peer — captures the essence without real-time monitoring complexity.

## Proposed architecture: three layers, one weekend

The prototype architecture separates concerns into three layers that can be developed in parallel by team members, with clean interfaces between them.

### Layer 1 — P2P mesh and identity (the transport)

Use **py-libp2p** for peer-to-peer networking with mDNS discovery on the local network. Each agent node generates a cryptographic PeerID on startup, providing decentralized identity without a registry. [Wikipedia](https://en.wikipedia.org/wiki/Libp2p) Agents publish an **Agent Capability Document** (inspired by A2A's Agent Card [Tietoevry](https://www.tietoevry.com/en/blog/2025/07/building-multi-agents-google-ai-services/) [Platform Engineering](https://platformengineering.com/editorial-calendar/best-of-2025/google-cloud-unveils-agent2agent-protocol-a-new-standard-for-ai-agent-interoperability-2/) but extended for P2P) as a JSON manifest containing: [Gravitee](https://www.gravitee.io/blog/googles-agent-to-agent-a2a-and-anthropics-model-context-protocol-mcp) [A2a-protocol](https://a2a-protocol.org/latest/topics/agent-discovery/) PeerID, supported task types, model size/tier, current availability status, and a natural-language capability description. On joining the network, agents broadcast their Capability Document via GossipSub and listen for others. The result is a self-organizing mesh where every peer maintains a local view of network capabilities.

**Technology choices**: py-libp2p for networking, mDNS for discovery, GossipSub for capability broadcasts, Protocol Buffers or JSON for message serialization. Fallback option: if py-libp2p proves too rough, use NATS with a single lightweight broker as the messaging backbone (sacrificing true P2P for reliability). [NATS.io](https://nats.io/about/)

### Layer 2 — Semantic negotiation engine (the brain)

Each agent runs **Ministral 3B locally via Ollama** (one-command setup, OpenAI-compatible API). The negotiation engine handles three types of interactions:

**Capability matching**: When an agent needs a task performed, it broadcasts a natural-language task description. Receiving agents use Ministral to assess whether they can fulfill it, generating a structured JSON response (match score, estimated latency, confidence level). The requesting agent ranks responses and initiates negotiation with the best candidate.

**SLA negotiation**: A simplified multi-round protocol inspired by ACNBP's 10-step sequence, [arXiv](https://arxiv.org/html/2506.13590v1) collapsed to 4 steps for the hackathon: (1) REQUEST — task description + requirements, (2) OFFER — capability assessment + terms, (3) COUNTER/ACCEPT — adjusted terms or acceptance, (4) BIND — mutual commitment with a task ID. Each message is a JSON object processed by the local Ministral model, which generates responses following a negotiation system prompt that enforces strategic behavior rather than default agreeableness.

**Task execution and reporting**: Once bound, the provider agent executes the task (using MCP for tool access if needed) and streams results back. Task states follow A2A's lifecycle (submitted → working → completed/failed). [IBM](https://www.ibm.com/think/topics/agent2agent-protocol)

**Technology choices**: Ollama for local inference, Mistral function calling for structured protocol messages, MCP Python SDK for tool integration, [Openai](https://developers.openai.com/apps-sdk/build/mcp-server/) A2A-compatible task lifecycle.

### Layer 3 — Orchestration dashboard (the demo)

A simple web UI (Streamlit or FastAPI + HTMX) showing: the live P2P network topology as a graph, agent capability cards, real-time negotiation logs, task routing decisions, and aggregate network statistics. This layer is essential for the hackathon demo — judges need to *see* agents discovering each other, negotiating, and routing tasks without central coordination.

### Recommended technology stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| P2P networking | py-libp2p (primary) or NATS (fallback) | Built-in mDNS, DHT, GossipSub; or rapid prototyping |
| Local inference | Ollama + Ministral 3B GGUF Q4_K_M | One-command setup, OpenAI-compatible API |
| Protocol messages | JSON over libp2p streams | Simple, debuggable, Ministral JSON mode |
| Agent discovery | mDNS + GossipSub capability broadcast | Zero-config, works on hackathon WiFi |
| Tool integration | MCP Python SDK | Standard, well-documented, 97M+ downloads |
| Task lifecycle | A2A-compatible states + Agent Cards | Leverages ecosystem familiarity |
| Negotiation logic | Ministral function calling + rules engine | Hybrid deterministic + LLM reasoning |
| Dashboard | Streamlit or FastAPI + HTMX | Fastest path to visual demo |
| Identity | libp2p PeerID (Ed25519) | Cryptographic, no registry needed |

## Phased approach from MVP to stretch goals

**Phase 1 — MVP (Saturday, hours 1–8): "Agents find each other and talk"**

Get two Ministral 3B agents running on separate machines, discovering each other via mDNS, exchanging Agent Capability Documents, and completing a simple request-response task. This proves the core loop: discovery → capability check → task delegation → result return. Use Ollama for inference and either py-libp2p or a minimal WebSocket server for communication. Hardcode two task types (e.g., "text summarization" and "translation"). Build a terminal-based log viewer showing the message exchange.

**Phase 2 — Negotiation (Saturday, hours 8–16): "Agents negotiate terms"**

Add the 4-step negotiation protocol. Agents now assess incoming requests against their current load and capabilities, generate structured offers with latency estimates, and negotiate terms. Introduce a simple "busy" state so agents can decline tasks. Add a third agent to create routing decisions — when multiple agents can handle a task, the requester selects based on negotiated terms. Build the Streamlit dashboard showing the network graph and negotiation logs.

**Phase 3 — Semantic layer (Sunday, hours 16–24): "Agents understand meaning"**

Replace hardcoded task types with natural-language capability descriptions. Use Ministral's embedding capabilities (or a lightweight sentence-transformer) for semantic matching. Agents now accept open-ended task descriptions and self-assess capability fit. Add multi-tier routing — if a 3B agent determines a task exceeds its capability, it negotiates handoff to an 8B node or escalates to the Mistral API.

**Phase 4 — Stretch goals (Sunday, hours 24–30): "The wow factor"**

Pick one or two based on progress:

- **Hardware capacity trading**: Agents report GPU/CPU utilization and bid on tasks from resource-constrained peers
- **Multi-hop task chains**: Agent A needs a task requiring capabilities split across Agents B and C; A orchestrates a pipeline
- **Adversarial resilience**: Demonstrate the network recovering when an agent goes offline mid-task
- **Cross-protocol bridge**: Expose each P2P agent as an A2A-compatible endpoint, showing interoperability with the standard ecosystem

## What to simplify versus what to implement for real

**Simplify aggressively:**
- Use mDNS only (skip DHT/internet-scale discovery — hackathon WiFi is fine)
- Use JSON over raw streams instead of Protocol Buffers (debuggability over performance)
- Skip authentication/encryption for the prototype (mention it in the pitch as a production requirement)
- Use static capability tiers instead of real-time hardware monitoring
- Limit negotiation to 2–3 rounds maximum (sufficient for demo, avoids infinite loops)

**Implement for real — these are what make the demo convincing:**
- **Actual local inference** on Ministral 3B via Ollama (not mocked API calls)
- **Real peer discovery** via mDNS (agents genuinely finding each other on the network)
- **Structured negotiation messages** generated by the LLM with function calling (not scripted)
- **Live dashboard** showing the network topology and message flow in real-time
- **At least 3 agents** with different capability profiles demonstrating routing decisions

## Hackathon positioning and competitive angle

The Mistral Worldwide Hackathon runs **February 28–March 1, 2026** across seven cities and online, [Competehub](https://www.competehub.dev/en/competitions/urls340f5fecde6d34b774492774885841f4) with 48 hours of development time, [Algo-Mania](https://algo-mania.com/en/blog/hackathons-coding/mistral-hackathon-2026-french-ai-shines-across-7-cities-worldwide/) [Manus](https://academy.manus.im/events/019c8c6a-fd35-76b9-b13b-c45d5a05e0f5) teams of 1–4, [Competehub](https://www.competehub.dev/en/competitions/urls340f5fecde6d34b774492774885841f4) and over **$200K in prizes**. [Algo-Mania](https://algo-mania.com/en/blog/hackathons-coding/mistral-hackathon-2026-french-ai-shines-across-7-cities-worldwide/) The "Best Use of Agent Skills" special award (prize: Reachy Mini robot from Hugging Face) directly aligns with this project. [mistral](https://worldwide-hackathon.mistral.ai/) Judging criteria emphasize creativity, technical innovation, future potential, implementation quality, and pitch quality. [Algo-Mania](https://algo-mania.com/en/blog/hackathons-coding/mistral-hackathon-2026-french-ai-shines-across-7-cities-worldwide/)

The competitive angle is strong: this project addresses a **recognized gap** in the agent ecosystem (no P2P negotiation standard exists), uses Mistral's 