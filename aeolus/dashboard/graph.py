"""
aeolus/dashboard/graph.py
Plotly network topology with dark theme, tier-colored nodes, animated edges.
"""
from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go


TIER_COLORS = {"3B": "#48C9B0", "8B": "#F7DC6F", "LARGE": "#E74C3C"}
EDGE_COLORS = {"OFFER": "#6C63FF", "BIND": "#48C9B0", "COUNTER": "#E67E22"}
BG = "#0D0D22"


def build_graph_figure(
    agents: dict, edges: list[dict], height: int = 380
) -> go.Figure:
    G = nx.Graph()
    for pid, info in agents.items():
        G.add_node(pid, **info)
    for edge in edges[-40:]:
        frm, to = edge.get("from"), edge.get("to")
        if frm and to and frm in agents and to in agents:
            G.add_edge(frm, to, label=edge.get("label", ""))

    if not G.nodes:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=BG, plot_bgcolor=BG,
            height=height, margin=dict(l=0, r=0, t=0, b=0),
            annotations=[dict(
                text="<b>No agents yet</b><br><span style='font-size:12px;color:#444466'>"
                     "Start some agents to see the mesh</span>",
                x=0.5, y=0.5, xref="paper", yref="paper",
                showarrow=False, font=dict(size=16, color="#555588"),
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    pos = nx.spring_layout(G, seed=42, k=2.5 / math.sqrt(max(G.number_of_nodes(), 1)))

    traces = []

    # -- Draw edges ----------------------------------------------------------
    edge_groups: dict[str, list] = {}
    for u, v, data in G.edges(data=True):
        label = data.get("label", "OFFER")
        edge_groups.setdefault(label, []).append((u, v))

    for label, edge_list in edge_groups.items():
        ex, ey = [], []
        for u, v in edge_list:
            x0, y0 = pos[u]; x1, y1 = pos[v]
            ex += [x0, x1, None]; ey += [y0, y1, None]
        color = EDGE_COLORS.get(label, "#6C63FF")
        dash_style = "dash" if label == "OFFER" else "solid"
        traces.append(go.Scatter(
            x=ex, y=ey, mode="lines",
            line=dict(width=2, color=color, dash=dash_style),
            opacity=0.6, hoverinfo="none",
            name=label,
        ))

    # -- Draw nodes ----------------------------------------------------------
    node_x, node_y, node_text, node_colors, node_sizes = [], [], [], [], []
    node_labels = []

    for pid in G.nodes():
        x, y = pos[pid]
        info = agents.get(pid, {})
        tier = info.get("model_tier", "3B")
        online = info.get("status") == "online"
        color = TIER_COLORS.get(tier, "#48C9B0") if online else "#333355"
        size = {"3B": 24, "8B": 28, "LARGE": 34}.get(tier, 24) if online else 16

        node_x.append(x); node_y.append(y)
        node_colors.append(color)
        node_sizes.append(size)
        node_labels.append(info.get("name", pid[:6]))
        caps = ", ".join(info.get("capabilities", [])[:2])
        status_str = "Online" if online else "Offline"
        model_name = info.get("model_name", "unknown")
        node_text.append(
            f"<b>{info.get('name', pid[:8])}</b><br>"
            f"Tier: {tier} | Model: {model_name} | {status_str}<br>"
            f"{caps}"
        )

    traces.append(go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        text=node_labels,
        textposition="top center",
        textfont=dict(color="#C0C0EE", size=11, family="Inter, sans-serif"),
        hovertext=node_text,
        hoverinfo="text",
        marker=dict(
            size=node_sizes, color=node_colors,
            line=dict(width=2, color=BG),
        ),
        name="Agents",
    ))

    # -- Legend entries for tiers --------------------------------------------
    for tier, color in TIER_COLORS.items():
        traces.append(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=10, color=color),
            name=f"{tier} tier",
            showlegend=True,
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(
            x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8888bb", size=10),
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        hoverlabel=dict(bgcolor="#1a1a3e", font_size=12, font_family="Inter"),
    )
    return fig
