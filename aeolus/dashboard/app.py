"""
aeolus/dashboard/app.py
Network admin / debug dashboard for the Aeolus P2P agent mesh.

Target audience: developers and network operators monitoring a live system.
Design principles: information density, operational clarity, full traceability.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import concurrent.futures
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import streamlit as st
import plotly.graph_objects as go
from aeolus.dashboard.graph import build_graph_figure
from aeolus.network.node import AgentNode

EVENTS_FILE = pathlib.Path("events.jsonl")

st.set_page_config(
    page_title="Aeolus Monitor",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CSS — dense, ops-tool aesthetic
# ============================================================================
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*          { font-family: 'Inter', sans-serif !important; }
code, .mono{ font-family: 'JetBrains Mono', monospace !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0.75rem 1.5rem 1rem !important; }

/* ── Status bar ─────────────────────────────────────────── */
.status-bar {
    display: flex; align-items: center; gap: 20px;
    padding: 8px 14px; margin-bottom: 12px;
    background: rgba(108,99,255,0.04);
    border: 1px solid rgba(108,99,255,0.1);
    border-radius: 8px; font-size: .78rem;
}
.status-bar .sep { color: #222240; }
.kpi { display: flex; align-items: center; gap: 5px; }
.kpi-val { font-weight: 700; font-size: .9rem; }
.kpi-lbl { color: #555577; font-size: .7rem; }

/* ── Live dot ───────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.25;} }
.live-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #2ECC71; animation: pulse 2.5s infinite;
    margin-right: 4px; vertical-align: middle;
}
.offline-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #E74C3C; margin-right: 4px; vertical-align: middle;
}

/* ── Log stream ─────────────────────────────────────────── */
.log-wrap {
    height: 520px; overflow-y: auto;
    background: #08080f; border: 1px solid #111128;
    border-radius: 8px; padding: 4px 0;
    font-family: 'JetBrains Mono', monospace !important;
}
.log-row {
    display: grid;
    grid-template-columns: 68px 190px 160px 1fr;
    align-items: center; gap: 0;
    padding: 3px 10px; border-bottom: 1px solid #0d0d1e;
    font-size: .72rem; line-height: 1.5;
}
.log-row:hover { background: #0f0f22; }
.log-row.ev-error   { border-left: 2px solid #E74C3C; }
.log-row.ev-task    { border-left: 2px solid #3498DB; }
.log-row.ev-negot   { border-left: 2px solid #F39C12; }
.log-row.ev-disco   { border-left: 2px solid #9B59B6; }
.log-ts   { color: #2a2a50; font-size: .68rem; letter-spacing: -.01em; }
.log-type { font-weight: 600; font-size: .7rem; letter-spacing: .01em; }
.log-agent{ color: #555577; font-size: .7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log-data { color: #444460; font-size: .68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Agent table ────────────────────────────────────────── */
.agent-tbl { width: 100%; border-collapse: collapse; font-size: .78rem; }
.agent-tbl th {
    font-size: .62rem; font-weight: 700; color: #444466;
    text-transform: uppercase; letter-spacing: .08em;
    padding: 6px 10px; border-bottom: 1px solid #111128;
    text-align: left;
}
.agent-tbl td { padding: 7px 10px; border-bottom: 1px solid #0d0d1e; vertical-align: top; }
.agent-tbl tr:hover td { background: #0c0c1e; }
.agent-tbl .caps-list { color: #555577; font-size: .68rem; }

/* ── Trace view ─────────────────────────────────────────── */
.trace-header {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; margin: 6px 0;
    background: #0c0c1e; border: 1px solid #111128; border-radius: 8px;
    font-size: .78rem; cursor: pointer;
}
.trace-step {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 5px 12px 5px 28px; border-bottom: 1px solid #0a0a1a;
    font-size: .73rem;
}
.trace-step:hover { background: #0d0d20; }
.trace-connector {
    border-left: 2px solid #111128; margin-left: 19px;
    padding-left: 0;
}
.trace-ts  { color: #2a2a50; font-family: monospace; min-width: 58px; flex-shrink: 0; }
.trace-dir { font-size: .65rem; color: #333355; min-width: 18px; flex-shrink: 0; }

/* ── Pills / badges ─────────────────────────────────────── */
.pill {
    display: inline-block; font-size: .6rem; font-weight: 700;
    padding: 1px 7px; border-radius: 3px;
    text-transform: uppercase; letter-spacing: .04em;
}
.section-hd {
    font-size: .62rem; font-weight: 700; color: #333355;
    text-transform: uppercase; letter-spacing: .1em; margin: 0 0 6px;
}

/* ── Sidebar agent row ──────────────────────────────────── */
.ag-row {
    display: flex; align-items: center; gap: 7px;
    padding: 6px 8px; margin: 2px 0;
    border-radius: 6px; border: 1px solid transparent;
}
.ag-row:hover { background: #0c0c20; border-color: #111130; }
.ag-name { font-size: .8rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.ag-model{ font-size: .62rem; color: #333355; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1a1a38; border-radius: 2px; }
</style>
""")


# ============================================================================
# Data helpers
# ============================================================================
def load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    rows: list[dict] = []
    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return list(reversed(rows))          # newest first


def build_state(events: list[dict]):
    agents: dict[str, dict] = {}
    edges:  list[dict]      = []
    tasks:  dict[str, dict] = {}
    for ev in reversed(events):
        etype   = ev.get("event", "")
        data    = ev.get("data", {})
        ts      = ev.get("ts", "")
        aname   = ev.get("agent_name", "?")
        peer_id = data.get("peer_id", ev.get("peer_id", ""))

        if etype == "AGENT_JOIN":
            agents[peer_id] = {
                "name": data.get("name", aname),
                "capabilities": data.get("capabilities", []),
                "model_tier": data.get("model_tier", "3B"),
                "model_name": data.get("model_name", ""),
                "status": "online", "peer_id": peer_id,
                "last_seen": ts,
            }
        elif etype == "AGENT_LEAVE":
            if peer_id in agents:
                agents[peer_id]["status"] = "offline"
                agents[peer_id]["last_seen"] = ts
        elif etype in ("OFFER_SENT", "BIND_SENT", "COUNTER_SENT"):
            label = {"OFFER_SENT": "OFFER", "BIND_SENT": "BIND",
                     "COUNTER_SENT": "COUNTER"}.get(etype, etype)
            edges.append({"from": data.get("from", ""),
                          "to": data.get("to", ""), "label": label, "ts": ts})
        elif etype == "TASK_SUBMITTED":
            tid = data.get("task_id", "")
            tasks[tid] = {
                "state": "submitted",
                "description": data.get("description", ""),
                "ts": ts, "executor": None, "error": None,
                "ts_end": None,
            }
        elif etype == "TASK_EXECUTING":
            tid = data.get("task_id", "")
            if tid in tasks:
                tasks[tid].update({"state": "executing",
                                   "executor": data.get("executor_name")})
        elif etype == "TASK_FAILED":
            tid = data.get("task_id", "")
            if tid in tasks:
                tasks[tid].update({"state": "failed",
                                   "error": data.get("error", "Unknown"),
                                   "ts_end": ts})
        elif etype in ("TASK_COMPLETE", "RESULT_SENT"):
            tid = data.get("task_id", "")
            if tid in tasks:
                tasks[tid]["state"] = "completed" if data.get("success", True) else "failed"
                tasks[tid]["ts_end"] = ts
    return agents, edges[-60:], tasks


def build_task_traces(events: list[dict]) -> dict[str, list[dict]]:
    """Group events by task_id for trace view."""
    traces: dict[str, list[dict]] = defaultdict(list)
    for ev in reversed(events):
        tid = ev.get("data", {}).get("task_id", "")
        if tid:
            traces[tid].append(ev)
    return dict(traces)


def _default_requester_profile(model_name: str) -> dict:
    return {
        "name": f"dashboard-{model_name}",
        "capabilities": ["question answering", "task orchestration"],
        "capability_description": "Dashboard requester.",
        "model_tier": "3B", "model_name": model_name,
    }


def _profiles_from_agents(agents: dict[str, dict]) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for info in agents.values():
        if info.get("status") != "online":
            continue
        mn = info.get("model_name") or info.get("name")
        if not mn:
            continue
        profiles[mn] = {
            "name": f"dashboard-{mn}",
            "capabilities": info.get("capabilities") or ["question answering"],
            "capability_description": f"Dashboard requester using {mn}.",
            "model_tier": info.get("model_tier") or "3B",
            "model_name": mn,
        }
    return profiles


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=300)


async def _submit_task_once(profile, task_description, max_latency_ms,
                             min_quality, priority):
    node = AgentNode(
        name=profile["name"],
        capabilities=profile["capabilities"],
        capability_description=profile["capability_description"],
        model_tier=profile["model_tier"],
        model_name=profile["model_name"],
        requester_only=True,
    )
    try:
        await node.start()
        await asyncio.sleep(2.5)
        return await node.submit_task(
            task_description=task_description,
            max_latency_ms=max_latency_ms,
            min_quality=min_quality,
            priority=priority,
        )
    finally:
        await node.stop()


# ============================================================================
# Constants
# ============================================================================
TIER_COLORS = {
    "3B": "#48C9B0", "8B": "#F7DC6F", "LARGE": "#E74C3C",
}

# event → (emoji, hex_color, css_class)
EVENT_META: dict[str, tuple[str, str, str]] = {
    "AGENT_JOIN":       ("↑",  "#48C9B0", "ev-disco"),
    "AGENT_LEAVE":      ("↓",  "#E74C3C", "ev-error"),
    "PEER_DISCOVERED":  ("◎",  "#9B59B6", "ev-disco"),
    "TASK_SUBMITTED":   ("→",  "#3498DB", "ev-task"),
    "REQUEST_RECEIVED": ("⟵",  "#5DADE2", "ev-task"),
    "OFFER_SENT":       ("↗",  "#F39C12", "ev-negot"),
    "OFFER_RECEIVED":   ("↙",  "#F39C12", "ev-negot"),
    "COUNTER_SENT":     ("⇄",  "#E67E22", "ev-negot"),
    "COUNTER_RECEIVED": ("⇄",  "#E67E22", "ev-negot"),
    "BIND_SENT":        ("⊕",  "#1ABC9C", "ev-negot"),
    "ACCEPT_RECEIVED":  ("✓",  "#2ECC71", "ev-negot"),
    "TASK_EXECUTING":   ("⚙",  "#F7DC6F", "ev-task"),
    "RESULT_SENT":      ("✓",  "#27AE60", "ev-task"),
    "TASK_COMPLETE":    ("■",  "#27AE60", "ev-task"),
    "TASK_FAILED":      ("✗",  "#E74C3C", "ev-error"),
}

TASK_STATE_COLOR = {
    "submitted": "#3498DB",
    "executing": "#F7DC6F",
    "completed": "#2ECC71",
    "failed":    "#E74C3C",
}

PROTOCOL_COLORS = {
    "REQUEST": "#6C63FF", "OFFER": "#F39C12", "COUNTER": "#E67E22",
    "ACCEPT":  "#2ECC71", "BIND":  "#1ABC9C", "RESULT":  "#27AE60",
}

BG = "#080810"


# ============================================================================
# Chart builders
# ============================================================================
def _hex_to_rgba(h: str, a: float) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def _build_sankey(events: list[dict]) -> go.Figure | None:
    stages = ["REQUEST", "OFFER", "COUNTER", "ACCEPT", "BIND", "RESULT"]
    sidx = {s: i for i, s in enumerate(stages)}
    e2s = {
        "REQUEST_RECEIVED": "REQUEST", "TASK_SUBMITTED": "REQUEST",
        "OFFER_SENT": "OFFER",         "OFFER_RECEIVED": "OFFER",
        "COUNTER_SENT": "COUNTER",     "COUNTER_RECEIVED": "COUNTER",
        "ACCEPT_RECEIVED": "ACCEPT",   "BIND_SENT": "BIND",
        "RESULT_SENT": "RESULT",       "TASK_COMPLETE": "RESULT",
    }
    trans: Counter = Counter()
    task_stages: dict[str, list[str]] = {}
    for ev in reversed(events):
        s   = e2s.get(ev.get("event", ""))
        tid = ev.get("data", {}).get("task_id", "")
        if s and tid:
            task_stages.setdefault(tid, []).append(s)
    for sl in task_stages.values():
        seen: list[str] = []
        for s in sl:
            if s not in seen:
                seen.append(s)
        for i in range(len(seen) - 1):
            trans[(seen[i], seen[i + 1])] += 1
    if not trans:
        return None
    srcs, tgts, vals, cols = [], [], [], []
    for (src, tgt), cnt in trans.items():
        if src in sidx and tgt in sidx:
            srcs.append(sidx[src]); tgts.append(sidx[tgt])
            vals.append(cnt)
            cols.append(_hex_to_rgba(PROTOCOL_COLORS.get(src, "#6C63FF"), 0.4))
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=24, thickness=16, line=dict(color=BG, width=0),
                  label=[f"  {s}  " for s in stages],
                  color=[PROTOCOL_COLORS[s] for s in stages]),
        link=dict(source=srcs, target=tgts, value=vals, color=cols),
    ))
    fig.update_layout(paper_bgcolor=BG, font=dict(color="#8888bb", size=11),
                      height=220, margin=dict(l=8, r=8, t=4, b=4))
    return fig


def _build_gauge(tasks: dict) -> go.Figure:
    total = len(tasks)
    done  = sum(1 for t in tasks.values() if t["state"] == "completed")
    rate  = (done / total * 100) if total else 0
    bar_c = "#2ECC71" if rate >= 70 else "#F39C12" if rate >= 40 else "#E74C3C"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rate,
        number={"suffix": "%", "font": {"size": 26, "color": "#C0C0EE"}},
        gauge={"axis": {"range": [0, 100], "tickfont": {"color": "#333355"}},
               "bar": {"color": bar_c}, "bgcolor": "#0d0d1e", "borderwidth": 0,
               "steps": [{"range": [0,  40], "color": "rgba(231,76,60,0.06)"},
                          {"range": [40, 70], "color": "rgba(243,156,18,0.06)"},
                          {"range": [70,100], "color": "rgba(46,204,113,0.06)"}]},
    ))
    fig.update_layout(paper_bgcolor=BG, font={"color": "#555577"},
                      height=170, margin=dict(l=16, r=16, t=10, b=4))
    return fig


def _build_timeline(events: list[dict]) -> go.Figure | None:
    rows = []
    for ev in events[:120]:
        etype = ev.get("event", "")
        if etype not in EVENT_META:
            continue
        try:
            ts = datetime.fromisoformat(ev.get("ts", ""))
        except (ValueError, TypeError):
            continue
        rows.append({"ts": ts, "agent": ev.get("agent_name", "?"),
                     "event": etype, "color": EVENT_META[etype][1]})
    if not rows:
        return None
    fig = go.Figure()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r["event"], []).append(r)
    for etype, items in grouped.items():
        c = items[0]["color"]
        fig.add_trace(go.Scatter(
            x=[i["ts"] for i in items], y=[i["agent"] for i in items],
            mode="markers",
            marker=dict(size=8, color=c, opacity=0.8,
                        line=dict(width=1, color=BG)),
            name=etype,
            hovertemplate="<b>%{y}</b><br>%{x|%H:%M:%S}<br>" + etype + "<extra></extra>",
        ))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        height=280, margin=dict(l=6, r=6, t=6, b=6),
        showlegend=True,
        legend=dict(font=dict(color="#555577", size=9), bgcolor="rgba(0,0,0,0)",
                    orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=True, gridcolor="#0d0d1e", tickfont=dict(color="#333355")),
        yaxis=dict(showgrid=False, tickfont=dict(color="#444460")),
        hoverlabel=dict(bgcolor="#111128", font_size=11),
    )
    return fig


# ============================================================================
# Log stream HTML builder
# ============================================================================
def _log_html(events: list[dict], agent_filter: str = "",
              type_filter: list[str] | None = None, limit: int = 200) -> str:
    rows = ""
    count = 0
    for ev in events:
        if count >= limit:
            break
        etype = ev.get("event", "?")
        if type_filter is not None and etype not in type_filter:
            continue
        agent = ev.get("agent_name", "?")
        if agent_filter and agent_filter.lower() not in agent.lower():
            continue

        em, ec, css = EVENT_META.get(etype, ("·", "#555577", ""))
        ts   = ev.get("ts", "")[11:19]
        data = ev.get("data", {})

        # Extract the most useful data field to show inline
        extra_parts = []
        if data.get("task_id"):
            extra_parts.append(f"task:{data['task_id'][:8]}")
        if data.get("match_score") is not None:
            extra_parts.append(f"score:{data['match_score']:.2f}")
        if data.get("estimated_latency_ms") is not None:
            extra_parts.append(f"lat:{data['estimated_latency_ms']}ms")
        if data.get("from") and data.get("to"):
            extra_parts.append(f"{data['from'][:10]}→{data['to'][:10]}")
        if data.get("error"):
            extra_parts.append(f"err:{str(data['error'])[:40]}")
        if data.get("model_tier"):
            extra_parts.append(f"tier:{data['model_tier']}")
        extra = "  ".join(extra_parts)

        type_cell = (f"<span class='log-type' style='color:{ec};'>"
                     f"{em} {etype}</span>")
        rows += (
            f"<div class='log-row {css}'>"
            f"<span class='log-ts'>{ts}</span>"
            f"{type_cell}"
            f"<span class='log-agent'>{agent}</span>"
            f"<span class='log-data'>{extra}</span>"
            f"</div>"
        )
        count += 1
    if not rows:
        return ("<div style='padding:40px;text-align:center;color:#222240;"
                "font-size:.8rem;font-family:monospace;'>no events</div>")
    return f"<div class='log-wrap'>{rows}</div>"


# ============================================================================
# Duration helper
# ============================================================================
def _duration(ts_start: str, ts_end: str | None) -> str:
    if not ts_end:
        return "—"
    try:
        a = datetime.fromisoformat(ts_start)
        b = datetime.fromisoformat(ts_end)
        ms = int((b - a).total_seconds() * 1000)
        return f"{ms / 1000:.1f}s" if ms >= 1000 else f"{ms}ms"
    except Exception:
        return "—"


# ============================================================================
# Load data (used in sidebar before fragment)
# ============================================================================
events             = load_events()
agents, edges, tasks = build_state(events)

# ============================================================================
# Sidebar — agent registry + task injection
# ============================================================================
with st.sidebar:

    # Branding
    n_online = sum(1 for a in agents.values() if a["status"] == "online")
    n_failed = sum(1 for t in tasks.values() if t["state"] == "failed")

    st.markdown(
        "<div style='display:flex;align-items:center;gap:7px;margin-bottom:2px;'>"
        "<span style='font-size:1.1rem;'>🌬️</span>"
        "<span style='font-size:1.05rem;font-weight:800;letter-spacing:-.01em;'>Aeolus</span>"
        "<span style='font-size:.62rem;font-weight:600;color:#444466;"
        "margin-left:2px;text-transform:uppercase;letter-spacing:.08em;'>Monitor</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;"
        f"margin-bottom:14px;font-size:.7rem;'>"
        f"<span><span class='live-dot'></span>"
        f"<span style='color:#2ECC71;font-weight:700;'>{n_online}</span>"
        f"<span style='color:#333355;'> online</span></span>"
        f"<span style='color:#111128;'>|</span>"
        f"<span style='color:#555577;'>{len(agents)} agents</span>"
        f"<span style='color:#111128;'>|</span>"
        f"<span style='color:#555577;'>{len(tasks)} tasks</span>"
        + (f"<span style='color:#111128;'>|</span>"
           f"<span style='color:#E74C3C;font-weight:700;'>{n_failed} failed</span>"
           if n_failed else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    # Agent registry
    st.markdown("<p class='section-hd'>Agent Registry</p>", unsafe_allow_html=True)
    if not agents:
        st.caption("No agents discovered. Start agents on the mesh.")
    else:
        for info in agents.values():
            tier_c  = TIER_COLORS.get(info["model_tier"], "#888888")
            is_on   = info["status"] == "online"
            dot     = "<span class='live-dot'></span>" if is_on else "<span class='offline-dot'></span>"
            model_s = info.get("model_name") or "?"
            tier_s  = info["model_tier"]
            st.markdown(
                f"<div class='ag-row'>"
                f"{dot}"
                f"<div style='flex:1;min-width:0;'>"
                f"<div class='ag-name'>{info['name']}</div>"
                f"<div class='ag-model'>{model_s}</div>"
                f"</div>"
                f"<span class='pill' style='background:{tier_c}18;color:{tier_c};'>"
                f"{tier_s}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # Controls
    st.markdown("<p class='section-hd'>Controls</p>", unsafe_allow_html=True)
    refresh = st.slider("Refresh (s)", 1, 15, 3)
    if st.button("Clear Log", use_container_width=True):
        if EVENTS_FILE.exists():
            EVENTS_FILE.unlink()
        st.rerun()
    st.caption(f"{len(events)} events · {len(edges)} edges")

    st.divider()

    # Task injection — secondary, for devs testing
    with st.expander("⚡ Inject Task", expanded=False):
        st.caption("Manually submit a task to the mesh for testing.")
        requester_profiles = _profiles_from_agents(agents)
        if not requester_profiles:
            default_model = "qwen3:0.6b"
            requester_profiles = {default_model: _default_requester_profile(default_model)}
        requester_options = list(requester_profiles.keys())

        with st.form("task_form", clear_on_submit=True):
            requester_model = st.selectbox("Via", options=requester_options, index=0)
            task_desc = st.text_area("Task", height=80,
                                     placeholder="Describe the task…")
            c1, c2 = st.columns(2)
            with c1:
                max_latency = st.number_input("Max ms", value=30000,
                                              min_value=5000, step=5000)
            with c2:
                min_quality = st.slider("Min Q", 0.0, 1.0, 0.7, 0.05)
            priority = st.slider("Priority", 1, 10, 5)
            submitted = st.form_submit_button("Submit →", use_container_width=True)

        if "dashboard_results" not in st.session_state:
            st.session_state["dashboard_results"] = []

        if submitted and task_desc and task_desc.strip():
            profile = requester_profiles.get(requester_model)
            if not profile:
                st.error("No profile found.")
                st.stop()
            try:
                with st.spinner("Waiting…"):
                    result = _run_async(_submit_task_once(
                        profile=profile,
                        task_description=task_desc.strip(),
                        max_latency_ms=int(max_latency),
                        min_quality=float(min_quality),
                        priority=int(priority),
                    ))
                st.session_state["dashboard_results"].insert(0, {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "requester_model": requester_model,
                    "task_description": task_desc.strip(),
                    "result": result,
                })
                st.success("Done." if result else "Timed out.")
            except Exception as exc:
                st.error(f"{exc}")
        elif submitted:
            st.warning("Enter a task.")


# ============================================================================
# Main content
# ============================================================================
@st.fragment(run_every=timedelta(seconds=refresh))
def _render_main():
    ev          = load_events()
    ag, ed, tk  = build_state(ev)
    traces      = build_task_traces(ev)

    # ── Status bar ───────────────────────────────────────────────────────
    online    = sum(1 for a in ag.values() if a["status"] == "online")
    executing = sum(1 for t in tk.values() if t["state"] == "executing")
    completed = sum(1 for t in tk.values() if t["state"] == "completed")
    failed    = sum(1 for t in tk.values() if t["state"] == "failed")
    offers    = sum(1 for e in ev if e.get("event") == "OFFER_SENT")
    counters  = sum(1 for e in ev if e.get("event") == "COUNTER_SENT")
    success_r = f"{completed / len(tk) * 100:.0f}%" if tk else "—"

    def _kpi(label: str, value, color: str = "#C0C0EE") -> str:
        return (f"<span class='kpi'>"
                f"<span class='kpi-val' style='color:{color};'>{value}</span>"
                f"<span class='kpi-lbl'>{label}</span>"
                f"</span>")

    st.markdown(
        f"<div class='status-bar'>"
        f"<span style='font-size:.7rem;font-weight:700;color:#6C63FF;"
        f"letter-spacing:.05em;'>AEOLUS</span>"
        f"<span class='sep'>│</span>"
        + _kpi("agents", online, "#48C9B0")
        + f"<span class='sep'>·</span>"
        + _kpi("executing", executing, "#F7DC6F" if executing else "#333355")
        + f"<span class='sep'>·</span>"
        + _kpi("completed", completed, "#2ECC71")
        + f"<span class='sep'>·</span>"
        + _kpi("failed", failed, "#E74C3C" if failed else "#333355")
        + f"<span class='sep'>│</span>"
        + _kpi("offers", offers)
        + f"<span class='sep'>·</span>"
        + _kpi("counters", counters)
        + f"<span class='sep'>│</span>"
        + _kpi("success", success_r, "#2ECC71" if success_r != "—" else "#333355")
        + f"<span class='sep'>·</span>"
        + _kpi("tasks", len(tk))
        + f"</div>",
        unsafe_allow_html=True,
    )

    # Latest injected result (if any)
    results = st.session_state.get("dashboard_results", [])
    if results:
        latest = results[0]
        with st.expander(
            f"Last inject result — {latest['requester_model']} @ {latest['ts'][11:19]}",
            expanded=True,
        ):
            if latest.get("result"):
                st.text_area("", value=latest["result"], height=90,
                             disabled=True, label_visibility="collapsed")
            else:
                st.warning("No result received (timed out).")

    # ── Tabs ─────────────────────────────────────────────────────────────
    tab_net, tab_traces, tab_agents, tab_analytics = st.tabs([
        "🌐  Network",
        "🔍  Traces",
        "🤖  Agents",
        "📊  Analytics",
    ])

    # ── TAB 1 — Network & Live Log ────────────────────────────────────────
    with tab_net:
        if not ag and not ev:
            st.markdown(
                "<div style='text-align:center;padding:80px 0;'>"
                "<div style='font-size:2.5rem;color:#111128;'>🌬️</div>"
                "<div style='color:#1a1a38;font-weight:700;margin-top:12px;'>"
                "No agents on the mesh</div>"
                "<div style='color:#222240;font-size:.8rem;margin-top:6px;'>"
                "Start agents to see the network topology.</div>"
                "<div style='margin-top:18px;'>"
                "<code style='background:#0c0c1e;color:#6C63FF;"
                "padding:7px 14px;border-radius:6px;font-size:.78rem;'>"
                "python scripts/question_run_with_ollama_locally.py"
                "</code></div></div>",
                unsafe_allow_html=True,
            )
        else:
            col_g, col_l = st.columns([3, 2], gap="large")

            with col_g:
                st.markdown("<p class='section-hd'>Topology</p>",
                            unsafe_allow_html=True)
                h = max(380, min(560, 180 + len(ag) * 72))
                st.plotly_chart(
                    build_graph_figure(ag, ed, height=h),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

            with col_l:
                st.markdown("<p class='section-hd'>Live Log</p>",
                            unsafe_allow_html=True)

                # Filter controls — compact
                fc1, fc2 = st.columns([3, 2])
                with fc1:
                    agent_f = st.text_input("agent", placeholder="filter by agent…",
                                            label_visibility="collapsed")
                with fc2:
                    log_group = st.selectbox(
                        "group", ["All", "Negotiation", "Tasks", "Discovery", "Errors"],
                        label_visibility="collapsed",
                    )

                group_map = {
                    "Negotiation": {"OFFER_SENT", "OFFER_RECEIVED", "COUNTER_SENT",
                                    "COUNTER_RECEIVED", "BIND_SENT", "ACCEPT_RECEIVED",
                                    "REQUEST_RECEIVED"},
                    "Tasks":       {"TASK_SUBMITTED", "TASK_EXECUTING", "TASK_COMPLETE",
                                    "TASK_FAILED", "RESULT_SENT"},
                    "Discovery":   {"AGENT_JOIN", "AGENT_LEAVE", "PEER_DISCOVERED"},
                    "Errors":      {"TASK_FAILED", "AGENT_LEAVE"},
                }
                type_f = list(group_map[log_group]) if log_group != "All" else None

                st.markdown(
                    _log_html(ev, agent_filter=agent_f, type_filter=type_f),
                    unsafe_allow_html=True,
                )

    # ── TAB 2 — Negotiation Traces ────────────────────────────────────────
    with tab_traces:
        if not traces:
            st.markdown(
                "<div style='text-align:center;padding:60px 0;"
                "color:#222240;font-size:.85rem;'>"
                "No tasks yet — submit one to see traces here.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("<p class='section-hd'>"
                        f"{len(traces)} task traces</p>",
                        unsafe_allow_html=True)

            # Newest tasks first
            for tid, t_events in reversed(list(traces.items())):
                task    = tk.get(tid, {})
                state   = task.get("state", "unknown")
                sc      = TASK_STATE_COLOR.get(state, "#888888")
                desc    = (task.get("description") or tid)[:80]
                ts_s    = task.get("ts", "")[11:19]
                dur     = _duration(task.get("ts", ""), task.get("ts_end"))
                n_steps = len(t_events)
                executor = task.get("executor") or "—"

                state_pill = (f"<span class='pill' "
                              f"style='background:{sc}1a;color:{sc};'>{state}</span>")
                dur_str  = (f"<span style='color:#555577;font-size:.68rem;'>"
                            f"{dur}</span>")
                step_str = (f"<span style='color:#333355;font-size:.68rem;'>"
                            f"{n_steps} events</span>")

                with st.expander(
                    f"`{tid[:8]}` — {desc}",
                    expanded=(state in ("executing", "failed")),
                ):
                    # Summary row
                    h1, h2, h3, h4 = st.columns(4)
                    h1.markdown(
                        f"**State** &nbsp; {state_pill}",
                        unsafe_allow_html=True,
                    )
                    h2.markdown(f"**Duration** &nbsp; {dur}", unsafe_allow_html=True)
                    h3.markdown(f"**Executor** &nbsp; {executor}")
                    h4.markdown(f"**Submitted** &nbsp; {ts_s}")

                    if task.get("description"):
                        st.markdown(
                            f"<div style='font-size:.8rem;color:#444466;"
                            f"padding:6px 10px;background:#0a0a18;"
                            f"border-radius:6px;border-left:3px solid #6C63FF44;"
                            f"margin:6px 0;font-family:monospace;'>"
                            f"{task['description']}</div>",
                            unsafe_allow_html=True,
                        )
                    if task.get("error"):
                        st.error(f"Error: {task['error']}")

                    # Message timeline (Jaeger-style)
                    st.markdown(
                        "<p class='section-hd' style='margin-top:10px;'>"
                        "Message trace</p>",
                        unsafe_allow_html=True,
                    )
                    tl_html = "<div class='trace-connector'>"
                    for te in t_events:
                        te_type  = te.get("event", "?")
                        em, ec, _= EVENT_META.get(te_type, ("·", "#444466", ""))
                        te_ts    = te.get("ts", "")[11:19]
                        te_agent = te.get("agent_name", "?")
                        te_data  = te.get("data", {})

                        # Extract meaningful fields
                        detail_parts = []
                        if te_data.get("match_score") is not None:
                            detail_parts.append(
                                f"<span style='color:#F39C12;'>score "
                                f"{te_data['match_score']:.2f}</span>")
                        if te_data.get("estimated_latency_ms") is not None:
                            detail_parts.append(
                                f"<span style='color:#555577;'>lat "
                                f"{te_data['estimated_latency_ms']}ms</span>")
                        if te_data.get("from") and te_data.get("to"):
                            detail_parts.append(
                                f"<span style='color:#333355;'>"
                                f"{te_data['from'][:12]} → {te_data['to'][:12]}"
                                f"</span>")
                        if te_data.get("error"):
                            detail_parts.append(
                                f"<span style='color:#E74C3C;'>"
                                f"{str(te_data['error'])[:60]}</span>")
                        detail_str = "&nbsp;&nbsp;".join(detail_parts)

                        tl_html += (
                            f"<div class='trace-step'>"
                            f"<span class='trace-ts'>{te_ts}</span>"
                            f"<span style='font-size:.8rem;color:{ec};"
                            f"min-width:18px;text-align:center;'>{em}</span>"
                            f"<span style='font-size:.72rem;color:{ec};"
                            f"font-weight:600;min-width:180px;'>{te_type}</span>"
                            f"<span style='font-size:.7rem;color:#444466;"
                            f"min-width:120px;'>{te_agent}</span>"
                            f"<span style='font-size:.68rem;'>{detail_str}</span>"
                            f"</div>"
                        )
                    tl_html += "</div>"
                    st.markdown(tl_html, unsafe_allow_html=True)

    # ── TAB 3 — Agent Registry ────────────────────────────────────────────
    with tab_agents:
        if not ag:
            st.markdown(
                "<div style='text-align:center;padding:60px 0;"
                "color:#222240;font-size:.85rem;'>"
                "No agents discovered.</div>",
                unsafe_allow_html=True,
            )
        else:
            # Build a proper table
            rows_html = ""
            for info in ag.values():
                tier_c   = TIER_COLORS.get(info["model_tier"], "#888888")
                is_on    = info["status"] == "online"
                dot      = ("<span class='live-dot'></span>" if is_on
                            else "<span class='offline-dot'></span>")
                caps     = ", ".join(info["capabilities"]) or "—"
                model_s  = info.get("model_name") or "?"
                peer_s   = info.get("peer_id", "")[:16] + "…"
                last_s   = info.get("last_seen", "")[11:19] or "—"
                state_s  = "online" if is_on else "offline"
                rows_html += (
                    f"<tr>"
                    f"<td>{dot} <b>{info['name']}</b></td>"
                    f"<td><span class='pill' "
                    f"style='background:{tier_c}18;color:{tier_c};'>"
                    f"{info['model_tier']}</span></td>"
                    f"<td style='font-family:monospace;font-size:.7rem;"
                    f"color:#9B59B6;'>{model_s}</td>"
                    f"<td class='caps-list'>{caps}</td>"
                    f"<td style='font-family:monospace;font-size:.65rem;"
                    f"color:#222240;'>{peer_s}</td>"
                    f"<td style='font-size:.7rem;color:#444466;'>{last_s}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<table class='agent-tbl'>"
                f"<thead><tr>"
                f"<th>Name</th><th>Tier</th><th>Model</th>"
                f"<th>Capabilities</th><th>Peer ID</th><th>Last seen</th>"
                f"</tr></thead>"
                f"<tbody>{rows_html}</tbody>"
                f"</table>",
                unsafe_allow_html=True,
            )

            st.divider()

            # Per-agent task breakdown
            st.markdown("<p class='section-hd'>Per-agent task counts</p>",
                        unsafe_allow_html=True)
            exec_counts = Counter(
                t.get("executor") for t in tk.values() if t.get("executor")
            )
            if exec_counts:
                cols = st.columns(min(len(exec_counts), 5))
                for col, (name, cnt) in zip(cols, exec_counts.most_common(5)):
                    col.metric(name, cnt)
            else:
                st.caption("No task execution data yet.")

    # ── TAB 4 — Analytics ────────────────────────────────────────────────
    with tab_analytics:
        if not ev:
            st.markdown(
                "<div style='text-align:center;padding:60px 0;"
                "color:#222240;font-size:.85rem;'>"
                "Analytics appear after agents negotiate.</div>",
                unsafe_allow_html=True,
            )
        else:
            r1, r2 = st.columns([3, 2], gap="large")
            with r1:
                st.markdown("<p class='section-hd'>Protocol Flow (Sankey)</p>",
                            unsafe_allow_html=True)
                sankey = _build_sankey(ev)
                if sankey:
                    st.plotly_chart(sankey, use_container_width=True,
                                    config={"displayModeBar": False})
                else:
                    st.caption("Not enough data.")
            with r2:
                st.markdown("<p class='section-hd'>Task Success Rate</p>",
                            unsafe_allow_html=True)
                if tk:
                    st.plotly_chart(_build_gauge(tk), use_container_width=True,
                                    config={"displayModeBar": False})
                else:
                    st.caption("No tasks.")

            st.markdown("<p class='section-hd' style='margin-top:12px;'>"
                        "Event Activity</p>", unsafe_allow_html=True)
            tl = _build_timeline(ev)
            if tl:
                st.plotly_chart(tl, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.caption("No timestamped events.")

            st.divider()
            b1, b2, b3 = st.columns(3)

            with b1:
                st.markdown("<p class='section-hd'>Tier distribution</p>",
                            unsafe_allow_html=True)
                for tier, cnt in sorted(Counter(
                    a.get("model_tier", "?")
                    for a in ag.values() if a.get("status") == "online"
                ).items()):
                    tc = TIER_COLORS.get(tier, "#888888")
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;"
                        f"padding:2px 0;font-size:.78rem;'>"
                        f"<span style='width:7px;height:7px;background:{tc};"
                        f"border-radius:1px;display:inline-block;'></span>"
                        f"<span style='color:#aaa;'>{tier}</span>"
                        f"<span style='color:#444466;'>({cnt})</span></div>",
                        unsafe_allow_html=True,
                    )

            with b2:
                st.markdown("<p class='section-hd'>Task states</p>",
                            unsafe_allow_html=True)
                for state, cnt in Counter(
                    t.get("state", "?") for t in tk.values()
                ).items():
                    sc = TASK_STATE_COLOR.get(state, "#888888")
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;"
                        f"padding:2px 0;font-size:.78rem;'>"
                        f"<span style='width:7px;height:7px;background:{sc};"
                        f"border-radius:1px;display:inline-block;'></span>"
                        f"<span style='color:#aaa;'>{state.title()}</span>"
                        f"<span style='color:#444466;'>({cnt})</span></div>",
                        unsafe_allow_html=True,
                    )

            with b3:
                st.markdown("<p class='section-hd'>Top event types</p>",
                            unsafe_allow_html=True)
                for etype, cnt in Counter(
                    e.get("event", "?") for e in ev
                ).most_common(6):
                    em, ec, _ = EVENT_META.get(etype, ("·", "#888888", ""))
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;"
                        f"padding:2px 0;font-size:.75rem;'>"
                        f"<span style='color:{ec};min-width:14px;'>{em}</span>"
                        f"<span style='color:#aaa;'>{etype}</span>"
                        f"<span style='color:#444466;'>({cnt})</span></div>",
                        unsafe_allow_html=True,
                    )


_render_main()
