"""
aeolus/dashboard/app.py -- Aeolus Agent Network Dashboard.
Real-time monitoring, task submission, negotiation analytics, and drill-down views.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import concurrent.futures
import time
from collections import Counter
from datetime import datetime, timezone

import streamlit as st
import plotly.graph_objects as go
from aeolus.dashboard.graph import build_graph_figure
from aeolus.network.node import AgentNode

EVENTS_FILE = pathlib.Path("events.jsonl")

st.set_page_config(
    page_title="Aeolus - P2P Agent Network",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CSS: Font Awesome, Inter font, animations, custom styling
# ============================================================================
st.markdown("""
<link rel="stylesheet"
  href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
  crossorigin="anonymous" referrerpolicy="no-referrer"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1rem !important; }
.fa-icon-label { margin-right: 6px; }

/* Pulse animation for live indicator */
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.4;} }

/* Metric card styling */
.metric-card {
    background: linear-gradient(135deg, rgba(108,99,255,0.06) 0%, rgba(72,201,176,0.03) 100%);
    border: 1px solid rgba(108,99,255,0.12);
    border-radius: 12px; padding: 18px 14px; text-align: center;
    transition: all 0.3s ease;
}
.metric-card:hover {
    border-color: rgba(108,99,255,0.35);
    box-shadow: 0 4px 24px rgba(108,99,255,0.1);
    transform: translateY(-2px);
}
.metric-value {
    font-size: 2rem; font-weight: 800; line-height: 1.1;
    margin: 8px 0 4px; letter-spacing: -0.02em;
}
.metric-label {
    font-size: .65rem; color: #8888bb; text-transform: uppercase;
    letter-spacing: .1em; font-weight: 600;
}

/* Agent card styling */
.agent-card {
    border-left: 3px solid; padding: 10px 14px; margin: 6px 0;
    border-radius: 0 10px 10px 0; background: rgba(255,255,255,0.03);
    transition: background 0.2s ease;
}
.agent-card:hover { background: rgba(255,255,255,0.06); }

/* Event table styling */
.event-table { width:100%; border-collapse:collapse; }
.event-table thead tr { border-bottom: 1px solid rgba(108,99,255,0.15); }
.event-table th {
    padding: 8px 10px; font-size: .65rem; color: #555588;
    text-align: left; font-weight: 600; text-transform: uppercase;
    letter-spacing: .08em;
}
.event-table td { padding: 6px 10px; }
.event-table tr { border-bottom: 1px solid rgba(255,255,255,.04); }
.event-table tr:hover { background: rgba(108,99,255,0.04); }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    padding: 10px 24px; font-weight: 600; font-size: .85rem;
    letter-spacing: .02em;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.01); }
::-webkit-scrollbar-thumb { background: rgba(108,99,255,0.25); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Helper functions
# ============================================================================
def icon(name: str, color: str = "inherit", extra: str = "") -> str:
    return f'<i class="fa-solid fa-{name} fa-icon-label" style="color:{color};{extra}"></i>'


def load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events = []
    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return list(reversed(events))


def build_state(events):
    agents: dict[str, dict] = {}
    edges: list[dict] = []
    tasks: dict[str, dict] = {}
    for ev in reversed(events):
        etype = ev.get("event", "")
        data = ev.get("data", {})
        ts = ev.get("ts", "")
        agent_name = ev.get("agent_name", "?")
        peer_id = data.get("peer_id", ev.get("peer_id", ""))
        if etype == "AGENT_JOIN":
            agents[peer_id] = {
                "name": data.get("name", agent_name),
                "capabilities": data.get("capabilities", []),
                "model_tier": data.get("model_tier", "3B"),
                "model_name": data.get("model_name", ""),
                "status": "online", "peer_id": peer_id,
            }
        elif etype == "AGENT_LEAVE":
            if peer_id in agents:
                agents[peer_id]["status"] = "offline"
        elif etype in ("OFFER_SENT", "BIND_SENT", "COUNTER_SENT"):
            label = {"OFFER_SENT": "OFFER", "BIND_SENT": "BIND",
                     "COUNTER_SENT": "COUNTER"}.get(etype, etype)
            edges.append({"from": data.get("from", ""),
                          "to": data.get("to", ""), "label": label, "ts": ts})
        elif etype == "TASK_SUBMITTED":
            tid = data.get("task_id", "")
            tasks[tid] = {"state": "submitted",
                          "description": data.get("description", ""),
                          "ts": ts, "executor": None}
        elif etype == "TASK_EXECUTING":
            tid = data.get("task_id", "")
            if tid in tasks:
                tasks[tid].update({"state": "executing",
                                   "executor": data.get("executor_name")})
        elif etype == "TASK_FAILED":
            tid = data.get("task_id", "")
            if tid in tasks:
                tasks[tid].update({"state": "failed",
                                   "error": data.get("error", "Unknown error")})
        elif etype in ("TASK_COMPLETE", "RESULT_SENT"):
            tid = data.get("task_id", "")
            if tid in tasks:
                success = data.get("success", True)
                tasks[tid]["state"] = "completed" if success else "failed"
    return agents, edges[-60:], tasks


def _default_requester_profile(model_name: str) -> dict:
    return {
        "name": f"dashboard-{model_name}",
        "capabilities": ["question answering", "task orchestration",
                         "semantic routing"],
        "capability_description": (
            "Dashboard requester that submits user tasks for negotiation and "
            "collects final results."),
        "model_tier": "3B",
        "model_name": model_name,
    }


def _profiles_from_agents(agents: dict[str, dict]) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for info in agents.values():
        if info.get("status") != "online":
            continue
        model_name = info.get("model_name") or info.get("name")
        if not model_name:
            continue
        profiles[model_name] = {
            "name": f"dashboard-{model_name}",
            "capabilities": info.get("capabilities") or ["question answering"],
            "capability_description":
                f"Dashboard requester using {model_name} to coordinate a task.",
            "model_tier": info.get("model_tier") or "3B",
            "model_name": model_name,
        }
    return profiles


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=300)


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
EVENT_ICONS: dict[str, tuple[str, str]] = {
    "AGENT_JOIN":        ("user-plus",           "#48C9B0"),
    "AGENT_LEAVE":       ("user-minus",          "#E74C3C"),
    "PEER_DISCOVERED":   ("satellite-dish",      "#9B59B6"),
    "TASK_SUBMITTED":    ("upload",              "#3498DB"),
    "REQUEST_RECEIVED":  ("envelope-open-text",  "#5DADE2"),
    "OFFER_SENT":        ("paper-plane",         "#F39C12"),
    "OFFER_RECEIVED":    ("envelope-open",       "#F39C12"),
    "COUNTER_SENT":      ("right-left",          "#E67E22"),
    "COUNTER_RECEIVED":  ("right-left",          "#E67E22"),
    "BIND_SENT":         ("link",                "#1ABC9C"),
    "ACCEPT_RECEIVED":   ("circle-check",        "#2ECC71"),
    "TASK_EXECUTING":    ("gear",                "#F7DC6F"),
    "RESULT_SENT":       ("inbox",               "#27AE60"),
    "TASK_COMPLETE":     ("flag-checkered",      "#27AE60"),
    "TASK_FAILED":       ("circle-exclamation",  "#E74C3C"),
}

TASK_STATE_ICONS: dict[str, tuple[str, str]] = {
    "submitted": ("clock",              "#3498DB"),
    "executing": ("gear",               "#F7DC6F"),
    "completed": ("circle-check",       "#2ECC71"),
    "failed":    ("circle-exclamation",  "#E74C3C"),
}

TIER_COLORS = {"3B": "#48C9B0", "8B": "#F7DC6F", "LARGE": "#E74C3C"}

PROTOCOL_COLORS = {
    "REQUEST":  "#6C63FF",
    "OFFER":    "#F39C12",
    "COUNTER":  "#E67E22",
    "ACCEPT":   "#2ECC71",
    "BIND":     "#1ABC9C",
    "RESULT":   "#27AE60",
}


# ============================================================================
# Analytics chart builders
# ============================================================================
def _hex_to_rgba(hex_color: str, alpha: float = 0.35) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _build_negotiation_sankey(events: list[dict]) -> go.Figure | None:
    """Sankey diagram of the negotiation protocol flow."""
    stages = ["REQUEST", "OFFER", "COUNTER", "ACCEPT", "BIND", "RESULT"]
    stage_idx = {s: i for i, s in enumerate(stages)}
    stage_colors = [PROTOCOL_COLORS[s] for s in stages]

    event_to_stage = {
        "REQUEST_RECEIVED": "REQUEST", "TASK_SUBMITTED": "REQUEST",
        "OFFER_SENT": "OFFER", "OFFER_RECEIVED": "OFFER",
        "COUNTER_SENT": "COUNTER", "COUNTER_RECEIVED": "COUNTER",
        "ACCEPT_RECEIVED": "ACCEPT",
        "BIND_SENT": "BIND",
        "RESULT_SENT": "RESULT", "TASK_COMPLETE": "RESULT",
    }

    transitions: Counter = Counter()
    task_stages: dict[str, list[str]] = {}

    for ev in reversed(events):
        stage = event_to_stage.get(ev.get("event", ""))
        if not stage:
            continue
        tid = ev.get("data", {}).get("task_id", "")
        if not tid:
            continue
        task_stages.setdefault(tid, []).append(stage)

    for stages_list in task_stages.values():
        seen = []
        for s in stages_list:
            if s not in seen:
                seen.append(s)
        for i in range(len(seen) - 1):
            transitions[(seen[i], seen[i + 1])] += 1

    if not transitions:
        return None

    sources, targets, values, colors = [], [], [], []
    for (src, tgt), count in transitions.items():
        if src in stage_idx and tgt in stage_idx:
            sources.append(stage_idx[src])
            targets.append(stage_idx[tgt])
            values.append(count)
            colors.append(_hex_to_rgba(PROTOCOL_COLORS.get(src, "#6C63FF"), 0.35))

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=30, thickness=20,
            line=dict(color="#0D0D22", width=0),
            label=[f"  {s}  " for s in stages],
            color=stage_colors,
        ),
        link=dict(source=sources, target=targets,
                  value=values, color=colors),
    ))
    fig.update_layout(
        paper_bgcolor="#0D0D22", font=dict(color="#E0E0FF", size=12),
        height=260, margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


def _build_success_gauge(tasks: dict) -> go.Figure:
    total = len(tasks)
    completed = sum(1 for t in tasks.values() if t["state"] == "completed")
    rate = (completed / total * 100) if total > 0 else 0

    bar_color = "#2ECC71" if rate >= 70 else "#F39C12" if rate >= 40 else "#E74C3C"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rate,
        number={"suffix": "%", "font": {"size": 32, "color": "#E0E0FF"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#333355",
                     "tickfont": {"color": "#555588"}},
            "bar": {"color": bar_color},
            "bgcolor": "#111128", "borderwidth": 0,
            "steps": [
                {"range": [0, 40], "color": "rgba(231,76,60,0.08)"},
                {"range": [40, 70], "color": "rgba(243,156,18,0.08)"},
                {"range": [70, 100], "color": "rgba(46,204,113,0.08)"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor="#0D0D22", font={"color": "#8888bb"},
        height=200, margin=dict(l=30, r=30, t=20, b=10),
    )
    return fig


def _build_event_timeline(events: list[dict]) -> go.Figure | None:
    """Scatter timeline showing negotiation activity over time."""
    plot_events = []
    for ev in events[:100]:
        etype = ev.get("event", "")
        if etype not in EVENT_ICONS:
            continue
        ts_str = ev.get("ts", "")
        try:
            ts = datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            continue
        agent = ev.get("agent_name", "?")
        color = EVENT_ICONS[etype][1]
        plot_events.append({"ts": ts, "agent": agent,
                            "event": etype, "color": color})

    if not plot_events:
        return None

    fig = go.Figure()
    grouped: dict[str, list] = {}
    for pe in plot_events:
        grouped.setdefault(pe["event"], []).append(pe)

    for etype, items in grouped.items():
        color = items[0]["color"]
        fig.add_trace(go.Scatter(
            x=[i["ts"] for i in items],
            y=[i["agent"] for i in items],
            mode="markers",
            marker=dict(size=10, color=color, opacity=0.8,
                        line=dict(width=1, color="#0D0D22")),
            name=etype,
            hovertemplate="<b>%{y}</b><br>%{x|%H:%M:%S}<br>" + etype + "<extra></extra>",
        ))

    fig.update_layout(
        paper_bgcolor="#0D0D22", plot_bgcolor="#0D0D22",
        height=320, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(font=dict(color="#8888bb", size=10), bgcolor="rgba(0,0,0,0)",
                    orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(showgrid=True, gridcolor="rgba(108,99,255,0.06)",
                   tickfont=dict(color="#555588"), title=None),
        yaxis=dict(showgrid=False, tickfont=dict(color="#8888bb"), title=None),
        hoverlabel=dict(bgcolor="#1a1a3e", font_size=12, font_family="Inter"),
    )
    return fig


# ============================================================================
# Load data
# ============================================================================
events = load_events()
agents, edges, tasks = build_state(events)

# ============================================================================
# Sidebar
# ============================================================================
with st.sidebar:
    # Header with live indicator
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px;'>"
        f"<h2 style='margin:0'>{icon('wind','#48C9B0')} Aeolus</h2>"
        f"</div>"
        f"<div style='display:flex;align-items:center;gap:6px;margin:2px 0 12px;'>"
        f"<span style='display:inline-block;width:7px;height:7px;background:#2ECC71;"
        f"border-radius:50%;animation:pulse 2s infinite;'></span>"
        f"<span style='color:#2ECC71;font-size:.65rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:.12em;'>Live</span>"
        f"<span style='color:#555588;font-size:.65rem;margin-left:4px;'>"
        f"P2P Semantic Negotiation Layer</span></div>",
        unsafe_allow_html=True,
    )
    st.divider()

    requester_profiles = _profiles_from_agents(agents)
    if not requester_profiles:
        default_model = "qwen3:0.6b"
        requester_profiles = {default_model: _default_requester_profile(default_model)}
    requester_options = list(requester_profiles.keys())

    # -- Task Submission -------
    st.markdown(
        f"<h4 style='margin-bottom:8px;'>{icon('bolt','#6C63FF')} Submit Task</h4>",
        unsafe_allow_html=True,
    )
    with st.form("task_form", clear_on_submit=True):
        requester_model = st.selectbox(
            "Requester Model", options=requester_options, index=0,
            help="Model used as the requester/coordinator on the mesh.",
        )
        task_desc = st.text_area(
            "Task Description", height=80,
            placeholder="e.g., Summarise this article about renewable energy...",
            help="Describe the task for agents to negotiate and execute.",
        )
        fc1, fc2 = st.columns(2)
        with fc1:
            max_latency = st.number_input(
                "Max Latency (ms)", value=30000, min_value=5000, step=5000,
                help="Max acceptable latency. Increase for slow local models.",
            )
        with fc2:
            min_quality = st.slider(
                "Min Quality", 0.0, 1.0, 0.7, 0.05,
                help="Minimum quality score required from the provider.",
            )
        priority = st.slider(
            "Priority", 1, 10, 5,
            help="Task urgency (1=low, 10=critical). Higher favours speed.",
        )
        submitted = st.form_submit_button("Submit Task", use_container_width=True)

    if "dashboard_results" not in st.session_state:
        st.session_state["dashboard_results"] = []

    if submitted and task_desc and task_desc.strip():
        profile = requester_profiles.get(requester_model)
        if not profile:
            st.error("No requester profile found for selected model.")
            st.stop()
        submitted_text = task_desc.strip()
        try:
            with st.spinner("Submitting and waiting for network result..."):
                result = _run_async(
                    _submit_task_once(
                        profile=profile, task_description=submitted_text,
                        max_latency_ms=int(max_latency),
                        min_quality=float(min_quality),
                        priority=int(priority),
                    )
                )
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "requester_model": requester_model,
                "task_description": submitted_text,
                "result": result,
            }
            st.session_state["dashboard_results"].insert(0, entry)
            if result:
                st.success("Task completed.")
            else:
                st.warning("No result received (timeout).")
        except Exception as exc:
            st.error(f"Task submission failed: {exc}")
    elif submitted:
        st.warning("Please enter a task description.")

    st.divider()

    # -- Agents Panel -------
    st.markdown(
        f"<h4 style='margin-bottom:8px;'>{icon('robot','#6C63FF')} Agents"
        f"<span style='font-size:.7rem;color:#555588;font-weight:400;"
        f"margin-left:8px;'>{len(agents)}</span></h4>",
        unsafe_allow_html=True,
    )
    if not agents:
        st.caption("No agents discovered. Start agents on the network.")
    else:
        for info in agents.values():
            col = TIER_COLORS.get(info["model_tier"], "#aaa")
            is_online = info["status"] == "online"
            status_dot = (
                f"<span style='display:inline-block;width:6px;height:6px;"
                f"background:{('#2ECC71' if is_online else '#333355')};"
                f"border-radius:50%;margin-right:6px;"
                f"{'animation:pulse 2s infinite;' if is_online else ''}'></span>"
            )
            caps = ", ".join(info["capabilities"][:3])
            model_name = info.get("model_name") or "unknown"
            st.markdown(
                f"<div class='agent-card' style='border-left-color:{col};'>"
                f"<strong style='font-size:.85rem;'>{status_dot}{info['name']}</strong>"
                f"<div style='margin-top:3px;'>"
                f"<span style='display:inline-block;background:{col}15;color:{col};"
                f"font-size:.6rem;padding:1px 6px;border-radius:4px;"
                f"font-weight:700;margin-right:4px;'>{info['model_tier']}</span>"
                f"<span style='color:#555588;font-size:.7rem;'>{model_name}</span>"
                f"</div>"
                f"<div style='color:#555588;font-size:.65rem;margin-top:2px;'>{caps}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # -- Controls -------
    st.markdown(
        f"<h4 style='margin-bottom:8px;'>{icon('sliders','#6C63FF')} Controls</h4>",
        unsafe_allow_html=True,
    )
    refresh = st.slider(
        "Auto-refresh (s)", 1, 10, 3,
        help="How often the dashboard reloads event data.",
    )
    if st.button("Clear Event Log", use_container_width=True):
        if EVENTS_FILE.exists():
            EVENTS_FILE.unlink()
        st.rerun()

    event_count = len(events)
    st.markdown(
        f"<div style='text-align:center;margin-top:8px;'>"
        f"<span style='background:rgba(108,99,255,0.1);color:#6C63FF;"
        f"font-size:.7rem;padding:3px 10px;border-radius:12px;"
        f"font-weight:600;'>{icon('database','#6C63FF','font-size:.65rem;')}"
        f"{event_count} events</span></div>",
        unsafe_allow_html=True,
    )


# ============================================================================
# Main content area
# ============================================================================

# -- Header --
st.markdown(
    f"<div style='margin-bottom:4px;'>"
    f"<h1 style='margin:0;font-size:1.8rem;font-weight:800;letter-spacing:-.02em;'>"
    f"{icon('wind','#48C9B0')} Aeolus Agent Network</h1>"
    f"<p style='color:#555588;margin:2px 0 0;font-size:.8rem;'>"
    f"P2P Semantic Negotiation Layer &mdash; "
    f"Mistral Worldwide Hackathon 2026</p></div>",
    unsafe_allow_html=True,
)

# -- Latest Result Banner --
results = st.session_state.get("dashboard_results", [])
if results:
    latest = results[0]
    with st.expander("Latest Submission Result", expanded=True, icon=":material/task_alt:"):
        rc1, rc2 = st.columns([1, 3])
        with rc1:
            st.markdown(
                f"**Model:** {latest['requester_model']}<br>"
                f"**Time:** {latest['ts'][11:19]}",
                unsafe_allow_html=True,
            )
        with rc2:
            if latest.get("result"):
                st.text_area("Result", value=latest["result"], height=140,
                             disabled=True, label_visibility="collapsed")
            else:
                st.warning("Timed out or no result received.")

# -- Compute metrics --
online = sum(1 for a in agents.values() if a["status"] == "online")
completed = sum(1 for t in tasks.values() if t["state"] == "completed")
executing = sum(1 for t in tasks.values() if t["state"] == "executing")
failed = sum(1 for t in tasks.values() if t["state"] == "failed")
offers = sum(1 for e in events if e.get("event") == "OFFER_SENT")
counters = sum(1 for e in events if e.get("event") == "COUNTER_SENT")

# -- Metric cards --
metrics_data = [
    ("circle-nodes", "#48C9B0", "Agents Online",  str(online)),
    ("list-check",   "#6C63FF", "Total Tasks",    str(len(tasks))),
    ("gear",         "#F7DC6F", "Executing",       str(executing)),
    ("circle-check", "#2ECC71", "Completed",       str(completed)),
    ("circle-exclamation", "#E74C3C", "Failed",    str(failed)),
    ("paper-plane",  "#F39C12", "Offers",          str(offers)),
    ("right-left",   "#E67E22", "Counters",        str(counters)),
]
cols = st.columns(len(metrics_data))
for col_m, (fa, color, label, value) in zip(cols, metrics_data):
    col_m.markdown(
        f"<div class='metric-card'>"
        f"<i class='fa-solid fa-{fa}' style='font-size:1.2rem;color:{color};'></i>"
        f"<div class='metric-value' style='color:{color};'>{value}</div>"
        f"<div class='metric-label'>{label}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

# ============================================================================
# Tabs: Overview | Negotiations | Analytics
# ============================================================================
tab_overview, tab_negotiations, tab_analytics = st.tabs([
    "Overview",
    "Negotiations",
    "Analytics",
])

# -- TAB 1: Overview ----------------------------------------------------------
with tab_overview:
    col_graph, col_feed = st.columns([3, 2], gap="large")

    with col_graph:
        st.markdown(
            f"<h3 style='font-size:1.1rem;margin-bottom:8px;'>"
            f"{icon('diagram-project','#6C63FF')} Network Topology</h3>",
            unsafe_allow_html=True,
        )
        graph_height = max(400, min(620, 220 + len(agents) * 60))
        fig = build_graph_figure(agents, edges, height=graph_height)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})

    with col_feed:
        st.markdown(
            f"<h3 style='font-size:1.1rem;margin-bottom:8px;'>"
            f"{icon('comments','#6C63FF')} Live Event Feed</h3>",
            unsafe_allow_html=True,
        )

        fc1, fc2 = st.columns(2)
        with fc1:
            event_type_filter = st.multiselect(
                "Event Types", options=list(EVENT_ICONS.keys()),
                default=list(EVENT_ICONS.keys()),
                help="Filter events by type.",
                label_visibility="collapsed",
            )
        with fc2:
            agent_name_filter = st.text_input(
                "Agent Filter", placeholder="Filter by agent...",
                help="Substring match on agent name.",
                label_visibility="collapsed",
            )

        filtered_events = [
            ev for ev in events
            if ev.get("event", "") in event_type_filter
            and (not agent_name_filter
                 or agent_name_filter.lower() in ev.get("agent_name", "").lower())
        ]

        if not filtered_events:
            st.info("No events match the current filters.")
        else:
            def _event_row(ev):
                etype = ev.get("event", "?")
                ei = EVENT_ICONS.get(etype, ("circle", "#888"))
                ts = ev.get("ts", "")[11:19]
                agent = ev.get("agent_name", "?")
                return (
                    f"<tr>"
                    f"<td style='color:#555588;font-size:.7rem;padding:5px 8px;"
                    f"white-space:nowrap;font-family:monospace;'>{ts}</td>"
                    f"<td style='padding:5px 8px;white-space:nowrap;'>"
                    f"<i class='fa-solid fa-{ei[0]}' style='color:{ei[1]};"
                    f"margin-right:5px;font-size:.75rem;'></i>"
                    f"<span style='font-size:.75rem;color:#ccc;'>{etype}</span></td>"
                    f"<td style='color:#8888bb;font-size:.7rem;padding:5px 8px;'>"
                    f"{agent}</td></tr>"
                )

            rows_html = "".join(_event_row(ev) for ev in filtered_events[:60])
            st.markdown(
                f"<div style='overflow-y:auto;max-height:440px;"
                f"border:1px solid rgba(108,99,255,0.1);border-radius:10px;"
                f"background:rgba(0,0,0,0.15);'>"
                f"<table class='event-table'>"
                f"<thead><tr><th>TIME</th><th>EVENT</th><th>AGENT</th>"
                f"</tr></thead><tbody>{rows_html}</tbody></table></div>",
                unsafe_allow_html=True,
            )

# -- TAB 2: Negotiations ------------------------------------------------------
with tab_negotiations:
    if not tasks:
        st.markdown(
            "<div style='text-align:center;padding:60px 0;'>"
            "<i class='fa-solid fa-handshake' style='font-size:2.5rem;"
            "color:#333355;'></i>"
            "<p style='color:#555588;margin-top:12px;font-size:.9rem;'>"
            "No negotiations yet. Submit a task to get started.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<h3 style='font-size:1.1rem;margin-bottom:12px;'>"
            f"{icon('table-list','#6C63FF')} Task Ledger"
            f"<span style='font-size:.75rem;color:#555588;font-weight:400;"
            f"margin-left:8px;'>{len(tasks)} tasks</span></h3>",
            unsafe_allow_html=True,
        )

        for tid, info in list(tasks.items())[-20:]:
            si = TASK_STATE_ICONS.get(info.get("state", ""), ("circle", "#888"))
            state = info.get("state", "")
            executor = info.get("executor") or "--"
            desc_preview = (info.get("description") or "")[:90]
            error_msg = info.get("error")

            state_badge = (
                f"<span style='display:inline-block;background:{si[1]}18;"
                f"color:{si[1]};font-size:.65rem;padding:2px 8px;"
                f"border-radius:4px;font-weight:700;text-transform:uppercase;"
                f"letter-spacing:.05em;'>"
                f"<i class='fa-solid fa-{si[0]}' style='margin-right:4px;"
                f"font-size:.6rem;'></i>{state}</span>"
            )

            with st.expander(
                f"Task {tid[:8]}... | {state.upper()} | {desc_preview}",
                expanded=False,
            ):
                st.markdown(state_badge, unsafe_allow_html=True)
                tc1, tc2 = st.columns(2)
                with tc1:
                    st.markdown(f"**Executor:** {executor}")
                with tc2:
                    st.markdown(f"**Submitted:** {info.get('ts', 'N/A')[11:19]}")
                st.markdown(f"**Description:** {info.get('description', 'N/A')}")

                if error_msg:
                    st.error(f"Error: {error_msg}")

                task_events = [
                    e for e in events
                    if e.get("data", {}).get("task_id") == tid
                ]
                if task_events:
                    st.markdown("**Event Timeline:**")
                    timeline_html = ""
                    for te in task_events:
                        te_type = te.get("event", "?")
                        te_ts = te.get("ts", "")[11:19]
                        te_agent = te.get("agent_name", "?")
                        te_icon = EVENT_ICONS.get(te_type, ("circle", "#888"))
                        timeline_html += (
                            f"<div style='display:flex;align-items:center;gap:8px;"
                            f"padding:4px 0;border-left:2px solid {te_icon[1]}20;"
                            f"padding-left:12px;margin-left:4px;'>"
                            f"<span style='color:#555588;font-size:.7rem;"
                            f"font-family:monospace;min-width:55px;'>{te_ts}</span>"
                            f"<i class='fa-solid fa-{te_icon[0]}' style='color:{te_icon[1]};"
                            f"font-size:.75rem;'></i>"
                            f"<span style='font-size:.8rem;color:#ccc;'>{te_type}</span>"
                            f"<span style='color:#555588;font-size:.7rem;'>{te_agent}</span>"
                            f"</div>"
                        )
                    st.markdown(timeline_html, unsafe_allow_html=True)

# -- TAB 3: Analytics ---------------------------------------------------------
with tab_analytics:
    if not events:
        st.markdown(
            "<div style='text-align:center;padding:60px 0;'>"
            "<i class='fa-solid fa-chart-line' style='font-size:2.5rem;"
            "color:#333355;'></i>"
            "<p style='color:#555588;margin-top:12px;font-size:.9rem;'>"
            "No data yet. Analytics will appear after agents negotiate.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        ac1, ac2 = st.columns([2, 1], gap="large")

        with ac1:
            st.markdown(
                f"<h3 style='font-size:1.1rem;margin-bottom:8px;'>"
                f"{icon('diagram-project','#6C63FF')} Protocol Flow</h3>",
                unsafe_allow_html=True,
            )
            sankey = _build_negotiation_sankey(events)
            if sankey:
                st.plotly_chart(sankey, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.caption("Not enough negotiation data for the flow diagram.")

        with ac2:
            st.markdown(
                f"<h3 style='font-size:1.1rem;margin-bottom:8px;'>"
                f"{icon('bullseye','#2ECC71')} Success Rate</h3>",
                unsafe_allow_html=True,
            )
            if tasks:
                gauge = _build_success_gauge(tasks)
                st.plotly_chart(gauge, use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.caption("No tasks to measure.")

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # Event timeline
        st.markdown(
            f"<h3 style='font-size:1.1rem;margin-bottom:8px;'>"
            f"{icon('timeline','#6C63FF')} Event Activity</h3>",
            unsafe_allow_html=True,
        )
        timeline_fig = _build_event_timeline(events)
        if timeline_fig:
            st.plotly_chart(timeline_fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.caption("No timestamped events to display.")

        # Breakdown section
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<h3 style='font-size:1.1rem;margin-bottom:12px;'>"
            f"{icon('chart-pie','#6C63FF')} Breakdown</h3>",
            unsafe_allow_html=True,
        )
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.markdown("**Tier Distribution**")
            tier_counts = Counter(
                a.get("model_tier", "?") for a in agents.values()
                if a.get("status") == "online"
            )
            for tier, count in sorted(tier_counts.items()):
                tc = TIER_COLORS.get(tier, "#888")
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"margin:4px 0;'>"
                    f"<span style='display:inline-block;width:10px;height:10px;"
                    f"background:{tc};border-radius:2px;'></span>"
                    f"<span style='color:#ccc;font-size:.85rem;'>{tier}</span>"
                    f"<span style='color:#555588;font-size:.8rem;'>({count})</span></div>",
                    unsafe_allow_html=True,
                )
            if not tier_counts:
                st.caption("No online agents.")

        with sc2:
            st.markdown("**Task States**")
            state_counts = Counter(t.get("state", "?") for t in tasks.values())
            for state, count in state_counts.items():
                si = TASK_STATE_ICONS.get(state, ("circle", "#888"))
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"margin:4px 0;'>"
                    f"<i class='fa-solid fa-{si[0]}' style='color:{si[1]};"
                    f"font-size:.75rem;'></i>"
                    f"<span style='color:#ccc;font-size:.85rem;'>"
                    f"{state.title()}</span>"
                    f"<span style='color:#555588;font-size:.8rem;'>({count})</span></div>",
                    unsafe_allow_html=True,
                )
            if not state_counts:
                st.caption("No tasks recorded.")

        with sc3:
            st.markdown("**Top Event Types**")
            event_counts = Counter(e.get("event", "?") for e in events)
            for etype, count in event_counts.most_common(6):
                ei = EVENT_ICONS.get(etype, ("circle", "#888"))
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"margin:4px 0;'>"
                    f"<i class='fa-solid fa-{ei[0]}' style='color:{ei[1]};"
                    f"font-size:.7rem;'></i>"
                    f"<span style='color:#ccc;font-size:.8rem;'>{etype}</span>"
                    f"<span style='color:#555588;font-size:.75rem;'>({count})</span></div>",
                    unsafe_allow_html=True,
                )

# ============================================================================
# Empty state (shown when no events at all)
# ============================================================================
if not events:
    st.markdown(
        "<div style='text-align:center;padding:80px 0;'>"
        "<i class='fa-solid fa-wind' style='font-size:3.5rem;color:#1a1a3e;'></i>"
        "<h3 style='color:#333355;margin-top:16px;font-weight:700;'>"
        "Waiting for Agents</h3>"
        "<p style='color:#555588;max-width:400px;margin:8px auto;font-size:.85rem;'>"
        "Start agents on the NATS mesh to see the network come alive. "
        "The dashboard will auto-refresh every few seconds.</p>"
        "<div style='margin-top:16px;'>"
        "<code style='background:#111128;color:#6C63FF;padding:8px 16px;"
        "border-radius:8px;font-size:.8rem;'>python scripts/demo_scenario.py</code>"
        "</div></div>",
        unsafe_allow_html=True,
    )

# ============================================================================
# Auto-refresh
# ============================================================================
time.sleep(refresh)
st.rerun()
