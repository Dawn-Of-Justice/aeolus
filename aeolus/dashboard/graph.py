"""
aeolus/dashboard/graph.py
Premium Plotly network topology with glow effects, directional arrows,
edge labels, and dark-theme styling matching the Aeolus dashboard.
"""
from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Colour palette (matches app.py & .streamlit/config.toml)
# ---------------------------------------------------------------------------
TIER_COLORS = {"3B": "#48C9B0", "8B": "#F7DC6F", "LARGE": "#E74C3C"}
EDGE_COLORS = {
    "OFFER": "#6C63FF",
    "BIND": "#48C9B0",
    "COUNTER": "#E67E22",
    "ACCEPT": "#2ECC71",
    "REQUEST": "#5DADE2",
    "RESULT": "#27AE60",
}
EDGE_DASH = {
    "OFFER": "dash",
    "COUNTER": "dot",
    "REQUEST": "dashdot",
}
BG = "#0A0A1B"  # matches .streamlit/config.toml backgroundColor


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_graph_figure(
    agents: dict, edges: list[dict], height: int = 420
) -> go.Figure:
    """Build a premium Plotly network-topology figure.

    Parameters
    ----------
    agents : dict[str, dict]
        Mapping of peer_id -> agent info (name, capabilities, model_tier, ...).
    edges : list[dict]
        Recent edge dicts with keys ``from``, ``to``, ``label``, ``ts``.
    height : int
        Figure height in pixels.
    """

    G = nx.DiGraph()
    for pid, info in agents.items():
        G.add_node(pid, **info)
    for edge in edges[-50:]:
        frm, to = edge.get("from"), edge.get("to")
        if frm and to and frm in agents and to in agents:
            G.add_edge(frm, to, label=edge.get("label", ""))

    # ── empty state ────────────────────────────────────────────────────────
    if not G.nodes:
        return _empty_figure(height)

    # ── layout ─────────────────────────────────────────────────────────────
    n = G.number_of_nodes()
    if n <= 3:
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42, k=3.0 / math.sqrt(max(n, 1)))

    traces: list[go.BaseTraceType] = []

    # ── 1. Draw edges (lines) ──────────────────────────────────────────────
    edge_groups: dict[str, list[tuple[str, str]]] = {}
    for u, v, data in G.edges(data=True):
        label = data.get("label", "OFFER")
        edge_groups.setdefault(label, []).append((u, v))

    for label, edge_list in edge_groups.items():
        ex, ey = [], []
        for u, v in edge_list:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            ex += [x0, x1, None]
            ey += [y0, y1, None]
        color = EDGE_COLORS.get(label, "#6C63FF")
        dash_style = EDGE_DASH.get(label, "solid")
        traces.append(
            go.Scatter(
                x=ex,
                y=ey,
                mode="lines",
                line=dict(width=2.5, color=color, dash=dash_style),
                opacity=0.55,
                hoverinfo="none",
                name=label,
                showlegend=False,
            )
        )

    # ── 2. Node glow layer (online only) ───────────────────────────────────
    glow_x, glow_y, glow_colors, glow_sizes = [], [], [], []
    for pid in G.nodes():
        info = agents.get(pid, {})
        if info.get("status") != "online":
            continue
        x, y = pos[pid]
        tier = info.get("model_tier", "3B")
        base_color = TIER_COLORS.get(tier, "#48C9B0")
        glow_x.append(x)
        glow_y.append(y)
        glow_colors.append(_hex_to_rgba(base_color, 0.12))
        glow_sizes.append({"3B": 52, "8B": 62, "LARGE": 76}.get(tier, 52))

    if glow_x:
        traces.append(
            go.Scatter(
                x=glow_x,
                y=glow_y,
                mode="markers",
                marker=dict(
                    size=glow_sizes,
                    color=glow_colors,
                    line=dict(width=0),
                ),
                hoverinfo="none",
                showlegend=False,
            )
        )

    # ── 3. Node outer ring (second glow ring for depth) ────────────────────
    ring_x, ring_y, ring_colors, ring_sizes = [], [], [], []
    for pid in G.nodes():
        info = agents.get(pid, {})
        if info.get("status") != "online":
            continue
        x, y = pos[pid]
        tier = info.get("model_tier", "3B")
        base_color = TIER_COLORS.get(tier, "#48C9B0")
        ring_x.append(x)
        ring_y.append(y)
        ring_colors.append(_hex_to_rgba(base_color, 0.25))
        ring_sizes.append({"3B": 36, "8B": 44, "LARGE": 54}.get(tier, 36))

    if ring_x:
        traces.append(
            go.Scatter(
                x=ring_x,
                y=ring_y,
                mode="markers",
                marker=dict(
                    size=ring_sizes,
                    color=ring_colors,
                    line=dict(width=0),
                ),
                hoverinfo="none",
                showlegend=False,
            )
        )

    # ── 4. Main node markers ───────────────────────────────────────────────
    node_x, node_y = [], []
    node_colors, node_sizes, node_border_colors = [], [], []
    node_labels, node_hover = [], []

    for pid in G.nodes():
        x, y = pos[pid]
        info = agents.get(pid, {})
        tier = info.get("model_tier", "3B")
        online = info.get("status") == "online"
        base_color = TIER_COLORS.get(tier, "#48C9B0")

        node_x.append(x)
        node_y.append(y)
        node_colors.append(base_color if online else "#252540")
        node_border_colors.append(
            base_color if online else "#333355"
        )
        node_sizes.append(
            ({"3B": 26, "8B": 32, "LARGE": 40}.get(tier, 26) if online else 16)
        )
        node_labels.append(info.get("name", pid[:6]))

        # Rich hover
        caps = ", ".join(info.get("capabilities", [])[:3]) or "none"
        model_name = info.get("model_name", "unknown")
        status_str = (
            "<span style='color:#2ECC71;font-weight:700;'>ONLINE</span>"
            if online
            else "<span style='color:#555588;'>offline</span>"
        )
        node_hover.append(
            f"<b style='font-size:14px;'>{info.get('name', pid[:8])}</b><br>"
            f"<span style='color:{base_color};font-weight:700;'>"
            f"{tier}</span> &middot; {model_name}<br>"
            f"{status_str}<br>"
            f"<span style='color:#8888bb;font-size:11px;'>{caps}</span>"
        )

    traces.append(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_labels,
            textposition="top center",
            textfont=dict(
                color="#C0C0EE", size=11, family="Inter, sans-serif"
            ),
            hovertext=node_hover,
            hoverinfo="text",
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2.5, color=node_border_colors),
            ),
            name="Agents",
            showlegend=False,
        )
    )

    # ── 5. Edge arrow annotations ──────────────────────────────────────────
    fig = go.Figure(data=traces)

    for label, edge_list in edge_groups.items():
        color = EDGE_COLORS.get(label, "#6C63FF")
        for u, v in edge_list:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            # Place arrow at 65% along the edge (closer to target)
            mx = x0 + 0.65 * (x1 - x0)
            my = y0 + 0.65 * (y1 - y0)
            # Anchor point for arrow tail direction
            ax = x0 + 0.45 * (x1 - x0)
            ay = y0 + 0.45 * (y1 - y0)
            fig.add_annotation(
                x=mx,
                y=my,
                ax=ax,
                ay=ay,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.4,
                arrowwidth=2,
                arrowcolor=color,
                opacity=0.7,
            )

    # ── 6. Edge midpoint labels ────────────────────────────────────────────
    for label, edge_list in edge_groups.items():
        color = EDGE_COLORS.get(label, "#6C63FF")
        for u, v in edge_list:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            mx = (x0 + x1) / 2
            my = (y0 + y1) / 2
            # Offset label slightly to avoid overlapping the edge line
            dx = y1 - y0
            dy = -(x1 - x0)
            length = math.sqrt(dx * dx + dy * dy) or 1
            offset = 0.04
            mx += offset * dx / length
            my += offset * dy / length
            fig.add_annotation(
                x=mx,
                y=my,
                text=f"<b>{label}</b>",
                showarrow=False,
                font=dict(size=9, color=color, family="Inter"),
                opacity=0.65,
                bgcolor=_hex_to_rgba(BG, 0.8),
                borderpad=2,
            )

    # ── 7. Legend entries ──────────────────────────────────────────────────
    # Tier legend
    for tier, color in TIER_COLORS.items():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=9, color=color, symbol="circle"),
                name=f"{tier} tier",
                showlegend=True,
            )
        )
    # Edge type legend
    for label in ("OFFER", "BIND", "COUNTER"):
        color = EDGE_COLORS.get(label, "#6C63FF")
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                line=dict(
                    width=2.5,
                    color=color,
                    dash=EDGE_DASH.get(label, "solid"),
                ),
                name=f"{label}",
                showlegend=True,
            )
        )

    # ── 8. Layout ──────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor="rgba(10,10,27,0.7)",
            bordercolor="rgba(108,99,255,0.12)",
            borderwidth=1,
            font=dict(color="#8888bb", size=10, family="Inter"),
            itemsizing="constant",
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[
                min(x for x, _ in pos.values()) - 0.3,
                max(x for x, _ in pos.values()) + 0.3,
            ],
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="x",
            scaleratio=1,
            range=[
                min(y for _, y in pos.values()) - 0.3,
                max(y for _, y in pos.values()) + 0.3,
            ],
        ),
        hoverlabel=dict(
            bgcolor="#1a1a3e",
            font_size=12,
            font_family="Inter",
            bordercolor="rgba(108,99,255,0.2)",
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
def _empty_figure(height: int) -> go.Figure:
    """Polished empty-state matching the app.py visual language."""
    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        annotations=[
            dict(
                text=(
                    "<b style='font-size:16px;color:#333355;'>"
                    "Waiting for Agents</b><br>"
                    "<span style='font-size:12px;color:#444466;'>"
                    "Start agents on the NATS mesh to see the topology</span>"
                ),
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=14, color="#555588", family="Inter"),
            )
        ],
        xaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False, visible=False
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showticklabels=False, visible=False
        ),
    )
    return fig
