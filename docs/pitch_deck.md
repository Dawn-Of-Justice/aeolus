# Pitch Deck — Aeolus: P2P Agent Negotiation Layer

---

## Slide 1 — The Problem

> "A2A and MCP solved agent communication — but only client-server.
> When agents are equals, there is no protocol for that."

- A2A: client → remote agent (one asks, one executes)
- MCP: host → tool server
- Neither supports: peer discovery, decentralised identity, or strategic negotiation

---

## Slide 2 — The Gap

| | Client-Server | Peer-to-Peer |
|---|---|---|
| Communication (A2A) | ✅ | ❌ |
| Tool Access (MCP) | ✅ | ❌ |
| Peer Discovery | ❌ | ❌ |
| Semantic Negotiation | ❌ | ❌ |

**The empty quadrant: decentralised + semantic negotiation**

---

## Slide 3 — Aeolus

> A peer-to-peer semantic negotiation layer where agents:
> 1. **Discover** each other (zero-config, no registry)
> 2. **Negotiate** task terms (strategic, not agreeable)
> 3. **Route** work (to the right tier, automatically)
>
> With zero central coordination.

---

## Slide 4 — Architecture

```
┌─────────────────────────────────────────┐
│  Layer 3: Dashboard (Streamlit)         │
│  Live topology · Negotiation logs       │
├─────────────────────────────────────────┤
│  Layer 2: Negotiation Engine            │
│  Ministral 3B · Semantic matching       │
│  4-step protocol · SLA evaluation       │
├─────────────────────────────────────────┤
│  Layer 1: P2P Mesh                      │
│  NATS transport · mDNS discovery        │
│  GossipSub · Cryptographic PeerIDs      │
└─────────────────────────────────────────┘
```

---

## Slide 5 — Live Demo

*(Run the 3-agent scenario)*

1. 🟢 Agents appear on the network
2. 📤 Summarisation request → Alpha handles it
3. 🔄 Translation with counter-offer negotiation
4. ⬆️ Complex code review → auto-escalates to Gamma (8B)

---

## Slide 6 — Why Mistral

- **Ministral 3B**: 2-3 GB, runs on laptop CPUs, native function calling
- **Multi-tier**: 3B → 8B → 14B → API cascade mirrors real network heterogeneity
- **JSON mode**: Structured negotiation messages without parsing hacks
- **Apache 2.0**: True P2P — no API key required per node

---

## Slide 7 — Future

- **Layer 9**: The semantic negotiation layer the ecosystem is missing
- **DID identity**: W3C Decentralised Identifiers for production trust
- **On-chain SLAs**: Enforceable service agreements
- **A2A bridge**: Every P2P agent exposes an A2A-compatible endpoint
- **Internet-scale**: DHT discovery, gossip protocols, global mesh

---

## Slide 8 — Team & Links

- **Project**: Aeolus
- **Hackathon**: Mistral Worldwide Hackathon, Feb 28–Mar 1, 2026
- **Target**: Best Use of Agent Skills award
- **Stack**: Ministral 3B + NATS + Streamlit + Python
