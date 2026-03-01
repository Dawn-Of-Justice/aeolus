#!/usr/bin/env python3
"""Spike S4: Streamlit live network graph.

Verifies that a networkx graph can be rendered in Streamlit and updates
when new data is added.

Usage:
    streamlit run spikes/spike_streamlit.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Aeolus Graph Spike", layout="wide")
st.title("🕸️ Network Graph Spike")

# Simulate peer data
if "peers" not in st.session_state:
    st.session_state.peers = [
        {"id": "alpha", "label": "Agent Alpha", "tier": "3B", "x": 0, "y": 0},
        {"id": "beta", "label": "Agent Beta", "tier": "3B", "x": 1, "y": 1},
    ]

if st.button("Add Gamma (8B)"):
    if not any(p["id"] == "gamma" for p in st.session_state.peers):
        st.session_state.peers.append(
            {"id": "gamma", "label": "Agent Gamma", "tier": "8B", "x": -1, "y": 1}
        )

if st.button("Reset"):
    st.session_state.peers = [
        {"id": "alpha", "label": "Agent Alpha", "tier": "3B", "x": 0, "y": 0},
        {"id": "beta", "label": "Agent Beta", "tier": "3B", "x": 1, "y": 1},
    ]

# Build and render graph
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

G = nx.Graph()

color_map = {"3B": "#55efc4", "8B": "#fdcb6e", "14B": "#fd79a8", "API": "#a29bfe"}
size_map = {"3B": 300, "8B": 500, "14B": 700, "API": 600}

for peer in st.session_state.peers:
    G.add_node(peer["id"], label=peer["label"], tier=peer["tier"])

# Add edges between all peers (fully connected for demo)
nodes = list(G.nodes)
for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
        G.add_edge(nodes[i], nodes[j])

colors = [color_map.get(G.nodes[n].get("tier", "3B"), "#55efc4") for n in G.nodes]
sizes = [size_map.get(G.nodes[n].get("tier", "3B"), 300) for n in G.nodes]
labels = {n: G.nodes[n].get("label", n) for n in G.nodes}

fig, ax = plt.subplots(figsize=(8, 5))
pos = nx.spring_layout(G, seed=42)
nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=sizes, ax=ax)
nx.draw_networkx_edges(G, pos, alpha=0.5, ax=ax)
nx.draw_networkx_labels(G, pos, labels, font_size=10, ax=ax)
ax.axis("off")
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)

st.markdown(f"**Peers on network:** {G.number_of_nodes()}")
st.markdown(f"**Connections:** {G.number_of_edges()}")

# Legend
st.markdown("---")
st.markdown("🟢 3B &nbsp; 🟡 8B &nbsp; 🩷 14B &nbsp; 🟣 API")
