"""
Q-Guide Streamlit prototype -- "Slate Mint" design system.

Project-centric UI: each sequence run creates a Project with its own design-result
dashboard. Light, professional biotech-SaaS look (muted teal/mint palette, bold
readable type, consistent cards). All data comes from `core.pipeline` (plain
Pydantic models) and every chart is a Plotly figure, so the backend is unchanged.

Run with:
    streamlit run qguide/frontend/streamlit_app.py
"""
from __future__ import annotations

import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from qguide.app import store
from qguide.app.schemas import DesignRequest, DesiredOutcome, TargetRegion
from qguide.core import (
    optimization,
    pipeline,
    visualization as viz,
    experiment_simulation as expsim,
)
from qguide.core.explainability import assumptions
from qguide.core.guide_generator import CAS_PROFILES, clean_sequence

# --------------------------------------------------------------------------- #
# Slate Mint palette                                                            #
# --------------------------------------------------------------------------- #
# Royal Purple palette (royalty / wealth / wisdom).
BG = "#F1E9F7"        # pale lilac (light, not white)
SURFACE = "#FFFFFF"
SOFT = "#F4ECFA"
SIDEBAR = "#3A1B57"   # deep royal purple
INK = "#2C1A3D"       # dark purple-charcoal
MUTED = "#6E5B7B"
BORDER = "#E4D6F0"
PRIMARY = "#7A33A6"   # rich royal purple
PRIMARY_DK = "#5E2585"
ACCENT = "#C49AE0"    # light orchid
GREEN = "#7A33A6"     # positive metrics -> brand purple
BLUE = "#9B59B6"      # secondary -> orchid
AMBER = "#C9892F"     # penalties / warn -> gold (wealth)
ROSE = "#C2566B"      # negative -> rose

st.set_page_config(page_title="Q-Guide", page_icon="🧬", layout="wide",
                   initial_sidebar_state="expanded")

pio.templates["qguide"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, system-ui, sans-serif", color=INK, size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=[PRIMARY, "#A569BD", BLUE, AMBER, ROSE, ACCENT],
    margin=dict(t=48, r=16, b=36, l=16),
))
pio.templates.default = "qguide"

EXAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples", "example_sequence.txt",
)

STEPS = ["Input sequence", "Generate candidates", "Score guides",
         "Run optimization", "Review results"]

# --- Credit model (prototype: in-session, simulated checkout) ---------------- #
CREDITS_PER_RUN = 5          # cost of one full design run (Run Optimization)
SIGNUP_BONUS = 25            # free trial credits on account creation
CREDIT_PACKAGES = [
    {"name": "Starter", "credits": 50, "price": 9, "sub": "~10 design runs"},
    {"name": "Pro", "credits": 250, "price": 39, "sub": "~50 runs · best value", "popular": True},
    {"name": "Team", "credits": 1000, "price": 129, "sub": "~200 runs"},
]


# --------------------------------------------------------------------------- #
# CSS                                                                           #
# --------------------------------------------------------------------------- #
def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');
    :root {{
      --bg:{BG}; --surface:{SURFACE}; --soft:{SOFT}; --ink:{INK}; --muted:{MUTED};
      --border:{BORDER}; --primary:{PRIMARY}; --primary-dk:{PRIMARY_DK}; --accent:{ACCENT};
      --good:{GREEN}; --warn:{AMBER}; --bad:{ROSE};
    }}
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
        font-family:'Inter',system-ui,sans-serif; color:var(--ink);
    }}
    h1,h2,h3,h4,.qg-title {{ font-family:'Plus Jakarta Sans','Inter',sans-serif !important;
        font-weight:800 !important; letter-spacing:-0.01em; color:var(--ink); }}
    [data-testid="stAppViewContainer"] {{ background:var(--bg); }}
    [data-testid="stHeader"] {{ background:transparent; }}
    [data-testid="stToolbar"], .stDeployButton, [data-testid="stDeployButton"] {{ display:none !important; }}
    .block-container {{ padding-top:1.3rem; padding-bottom:3rem; max-width:1540px; }}
    p, label, span, div {{ color:var(--ink); }}
    .qg-sub {{ color:var(--muted); font-weight:500; }}

    /* Sidebar */
    [data-testid="stSidebar"] {{ background:linear-gradient(180deg,{SIDEBAR} 0%,#28123D 100%); }}
    [data-testid="stSidebar"] * {{ color:#E7EFEC; }}
    [data-testid="stSidebar"] .qg-brand {{ font-family:'Plus Jakarta Sans';font-weight:800;font-size:1.4rem;
        background:linear-gradient(90deg,{ACCENT},#EAD7FA);-webkit-background-clip:text;-webkit-text-fill-color:transparent; }}
    [data-testid="stSidebar"] .qg-brand-sub {{ color:#A892BE;font-size:0.7rem;letter-spacing:0.05em;font-weight:600; }}
    [data-testid="stSidebar"] .stButton > button {{ background:rgba(255,255,255,0.05);color:#DCEAE5;
        border:1px solid transparent;text-align:left;justify-content:flex-start;font-weight:600;border-radius:10px;padding:0.5rem 0.8rem; }}
    [data-testid="stSidebar"] .stButton > button:hover {{ background:rgba(196,154,224,0.18);color:#fff; }}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background:linear-gradient(90deg,{PRIMARY},{PRIMARY_DK});color:#fff;border:none;box-shadow:0 6px 16px rgba(122,51,166,0.4); }}
    .qg-help {{ background:rgba(255,255,255,0.05);border:1px solid rgba(196,154,224,0.18);border-radius:12px;
        padding:0.7rem 0.85rem;font-size:0.8rem;color:#D8C9E6; }}
    .qg-acct {{ background:rgba(255,255,255,0.06);border:1px solid rgba(196,154,224,0.2);border-radius:14px;
        padding:0.7rem 0.8rem;margin:0.3rem 0 0.5rem; }}
    .qg-acct-row {{ display:flex;align-items:center;gap:0.6rem; }}
    .qg-avatar {{ width:34px;height:34px;border-radius:999px;display:flex;align-items:center;justify-content:center;
        font-weight:800;color:#fff;background:linear-gradient(135deg,{PRIMARY},{ACCENT}); }}
    .qg-acct-name {{ font-weight:700;color:#F1E8FA;font-size:0.92rem; }}
    .qg-acct-plan {{ color:#A892BE;font-size:0.72rem;font-weight:600; }}
    .qg-credit {{ margin-top:0.55rem;background:rgba(196,154,224,0.16);border-radius:10px;padding:0.4rem 0.6rem;
        font-weight:800;color:#EAD7FA;display:flex;align-items:center;justify-content:space-between; }}
    .qg-credit.low {{ background:rgba(194,86,107,0.22);color:#FFD9E2; }}
    .qg-credit-sub {{ font-weight:600;font-size:0.72rem;color:#C9B5DD; }}
    .qg-price {{ background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:1.2rem;
        box-shadow:0 10px 26px rgba(40,18,60,0.06);text-align:center;height:100%; }}
    .qg-price.pop {{ border:2px solid var(--primary);box-shadow:0 14px 32px rgba(122,51,166,0.18); }}
    .qg-price-name {{ font-weight:800;font-size:1.05rem;font-family:'Plus Jakarta Sans'; }}
    .qg-price-credits {{ font-family:'Plus Jakarta Sans';font-weight:800;font-size:2rem;color:{PRIMARY};margin:0.3rem 0 0; }}
    .qg-price-cost {{ color:var(--muted);font-weight:700;font-size:1.05rem; }}
    .qg-price-sub {{ color:var(--muted);font-size:0.82rem;margin:0.3rem 0 0.2rem; }}
    .qg-poptag {{ display:inline-block;background:var(--primary);color:#fff;font-size:0.66rem;font-weight:800;
        padding:0.12rem 0.5rem;border-radius:999px;letter-spacing:0.04em;text-transform:uppercase;margin-bottom:0.3rem; }}

    /* Buttons */
    .stButton > button[kind="primary"], .stDownloadButton > button {{
        background:linear-gradient(90deg,{PRIMARY},{PRIMARY_DK});border:none;color:#fff;font-weight:700;border-radius:10px;
        box-shadow:0 6px 16px rgba(122,51,166,0.28); }}
    .stButton > button {{ border-radius:10px;font-weight:600; }}

    /* Cards */
    .qg-card {{ background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:1.05rem 1.15rem;
        box-shadow:0 1px 2px rgba(40,18,60,0.04),0 10px 26px rgba(40,18,60,0.05); }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:16px !important;border-color:var(--border) !important;
        background:var(--surface);box-shadow:0 10px 26px rgba(40,18,60,0.05); }}
    /* Bordered st.container() cards that hold a .qg-cardtitle (version-robust) */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .qg-cardtitle) {{
        background:var(--surface) !important; border:1px solid var(--border) !important;
        border-radius:16px !important; padding:1.1rem 1.2rem !important;
        box-shadow:0 10px 26px rgba(40,18,60,0.05); }}
    .qg-cardtitle {{ font-family:'Plus Jakarta Sans';font-weight:800;font-size:1.02rem;margin-bottom:0.2rem; }}

    /* Metric cards */
    .qg-metric {{ background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:0.85rem 1rem;
        box-shadow:0 10px 26px rgba(40,18,60,0.05);height:100%; }}
    .qg-metric-label {{ color:var(--muted);font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.04em; }}
    .qg-metric-value {{ font-family:'Plus Jakarta Sans';font-weight:800;font-size:1.65rem;line-height:1.2;margin-top:0.15rem; }}
    .qg-metric-sub {{ color:var(--muted);font-size:0.76rem;margin-top:0.15rem;font-weight:500; }}

    /* Stepper */
    .qg-stepper {{ display:flex;align-items:center;gap:0;margin:0.2rem 0 0.6rem; }}
    .qg-step {{ display:flex;align-items:center;gap:0.5rem; }}
    .qg-step-dot {{ width:30px;height:30px;border-radius:999px;display:flex;align-items:center;justify-content:center;
        font-weight:800;font-size:0.85rem;border:2px solid var(--border);background:var(--surface);color:var(--muted); }}
    .qg-step-label {{ font-weight:700;font-size:0.84rem;color:var(--muted);white-space:nowrap; }}
    .qg-step-line {{ flex:1;height:2px;background:var(--border);margin:0 0.6rem;min-width:24px; }}
    .qg-active .qg-step-dot {{ background:var(--primary);border-color:var(--primary);color:#fff;box-shadow:0 4px 12px rgba(122,51,166,0.35); }}
    .qg-active .qg-step-label {{ color:var(--ink); }}
    .qg-done .qg-step-dot {{ background:var(--accent);border-color:var(--accent);color:{PRIMARY_DK}; }}
    .qg-done .qg-step-label {{ color:var(--ink); }}

    /* Pills */
    .qg-pill {{ display:inline-block;padding:0.12rem 0.55rem;border-radius:999px;font-weight:700;font-size:0.8rem; }}
    .qg-good {{ background:rgba(122,51,166,0.13);color:{PRIMARY_DK}; }}
    .qg-warn {{ background:rgba(201,137,47,0.16);color:#9A6818; }}
    .qg-bad  {{ background:rgba(194,86,107,0.14);color:{ROSE}; }}

    .qg-badge {{ display:inline-flex;align-items:center;gap:0.5rem;background:rgba(122,51,166,0.12);
        color:{PRIMARY_DK};border:1px solid rgba(122,51,166,0.3);border-radius:12px;padding:0.5rem 0.9rem;font-weight:700; }}
    .qg-badge-idle {{ background:var(--soft);color:var(--muted);border:1px solid var(--border); }}

    /* Summary rows */
    .qg-srow {{ display:flex;justify-content:space-between;padding:0.32rem 0;border-bottom:1px dashed var(--border);font-size:0.88rem; }}
    .qg-srow:last-child {{ border-bottom:none; }}
    .qg-srow .k {{ color:var(--muted);font-weight:600; }}
    .qg-srow .v {{ font-weight:700; }}

    /* Score bars */
    .qg-bar-row {{ display:flex;align-items:center;gap:0.6rem;margin:0.3rem 0; }}
    .qg-bar-label {{ width:118px;font-size:0.8rem;color:var(--muted);font-weight:600; }}
    .qg-bar-track {{ flex:1;height:8px;background:var(--soft);border-radius:999px;overflow:hidden; }}
    .qg-bar-fill {{ height:100%;border-radius:999px; }}
    .qg-bar-val {{ width:38px;text-align:right;font-size:0.8rem;font-weight:700; }}

    /* Checklist */
    .qg-check {{ display:flex;align-items:center;gap:0.55rem;margin:0.4rem 0;font-size:0.9rem;font-weight:600; }}
    .qg-check .dot {{ width:20px;height:20px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;font-size:0.72rem;font-weight:800; }}
    .qg-on {{ background:rgba(122,51,166,0.16);color:{PRIMARY_DK}; }}
    .qg-off {{ background:var(--soft);color:var(--muted); }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap:0.3rem;border-bottom:1px solid var(--border); }}
    .stTabs [data-baseweb="tab"] {{ font-weight:700;color:var(--muted);padding:0.5rem 0.4rem; }}
    .stTabs [aria-selected="true"] {{ color:var(--primary) !important; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background:var(--primary); }}

    code {{ font-family:'JetBrains Mono','SF Mono',monospace;background:var(--soft);color:{PRIMARY_DK};font-weight:600; }}

    .qg-tablewrap {{ overflow-x:auto; max-width:100%; padding-bottom:0.2rem; }}
    .qg-table {{ width:100%;border-collapse:separate;border-spacing:0 0.3rem;font-size:0.8rem;table-layout:auto; }}
    .qg-table th {{ text-align:left;color:var(--muted);font-weight:700;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.02em;padding:0 0.45rem;white-space:nowrap; }}
    .qg-table td {{ background:var(--surface);padding:0.42rem 0.45rem;border-top:1px solid var(--border);border-bottom:1px solid var(--border);font-weight:500;white-space:nowrap; }}
    .qg-table code {{ font-size:0.74rem;padding:0.05rem 0.2rem; }}
    .qg-table td:first-child {{ border-left:1px solid var(--border);border-radius:10px 0 0 10px; }}
    .qg-table td:last-child {{ border-right:1px solid var(--border);border-radius:0 10px 10px 0; }}
    .qg-row-active td {{ background:rgba(122,51,166,0.07); }}
    .qg-gid {{ color:var(--primary);font-weight:800; }}
    .qg-disclaimer {{ background:rgba(122,51,166,0.07);border:1px solid rgba(122,51,166,0.22);color:#4a2a63;
        border-radius:12px;padding:0.7rem 1rem;font-size:0.85rem;font-weight:500; }}
    </style>
    """, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# State & projects                                                              #
# --------------------------------------------------------------------------- #
def _init_state():
    store.init_db()
    st.session_state.setdefault("user", None)          # logged-in email
    st.session_state.setdefault("acct_cache", None)     # working copy of the account
    st.session_state.setdefault("active", None)
    st.session_state.setdefault("view", "new")


# --------------------------------------------------------------------------- #
# Accounts & credits (SQLite-backed; in-session working copy, write-through)   #
# --------------------------------------------------------------------------- #
def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def acct():
    """Working copy of the logged-in account (loaded from the DB at login)."""
    return st.session_state.get("acct_cache") if st.session_state.get("user") else None


def _load_into_session(email):
    st.session_state["user"] = email
    st.session_state["acct_cache"] = store.load_account(email)
    st.session_state["active"] = None


def signup(name, email, password):
    ok, msg = store.create_user(name, email, password, SIGNUP_BONUS)
    if ok:
        _load_into_session((email or "").strip().lower())
    return ok, msg


def login(email, password):
    ok, msg = store.authenticate(email, password)
    if ok:
        _load_into_session((email or "").strip().lower())
    return ok, msg


def logout():
    st.session_state["user"] = None
    st.session_state["acct_cache"] = None
    st.session_state["active"] = None
    goto("new")


def can_afford(cost):
    a = acct()
    return bool(a) and a["credits"] >= cost


def _persist(a):
    store.persist_counters(a["email"], a["credits"], a["plan"], a["runs"], a["counter"])


def charge(cost, desc):
    a = acct()
    a["credits"] -= cost
    a["transactions"].append({"ts": _now(), "type": "usage", "amount": -cost,
                              "balance": a["credits"], "desc": desc, "price": 0.0})
    store.add_transaction(a["email"], "usage", -cost, a["credits"], desc, 0.0)
    _persist(a)


def add_credits(amount, desc, price):
    a = acct()
    a["credits"] += amount
    if a["plan"] == "Free trial":
        a["plan"] = "Pay-as-you-go"
    a["transactions"].append({"ts": _now(), "type": "purchase", "amount": amount,
                              "balance": a["credits"], "desc": desc, "price": price})
    store.add_transaction(a["email"], "purchase", amount, a["credits"], desc, price)
    _persist(a)


def _load_example() -> str:
    try:
        with open(EXAMPLE_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"


def goto(view: str):
    st.session_state["view"] = view
    st.rerun()


def create_project(req, resp, elapsed) -> str:
    a = acct()
    a["counter"] += 1
    pid = f"P{a['counter']:03d}"
    name = req.gene_name or "untitled"
    proj = {
        "id": pid, "name": name, "created": _now(),
        "elapsed": elapsed, "request": req, "response": resp,
        "selected_guide": resp.best_single_guide_id,
        "pred": None, "pred_cmp": None, "sim_results": None,
    }
    a["projects"][pid] = proj
    st.session_state["active"] = pid
    store.save_project(a["email"], proj)
    _persist(a)        # persist incremented counter (+ runs, set just before)
    return pid


def active_project():
    a = acct()
    if not a:
        return None
    pid = st.session_state.get("active")
    return a["projects"].get(pid) if pid else None


# --------------------------------------------------------------------------- #
# HTML helpers                                                                  #
# --------------------------------------------------------------------------- #
def metric_card(col, label, value, sub, color=INK):
    col.markdown(f'<div class="qg-metric"><div class="qg-metric-label">{label}</div>'
                 f'<div class="qg-metric-value" style="color:{color}">{value}</div>'
                 f'<div class="qg-metric-sub">{sub}</div></div>', unsafe_allow_html=True)


def pill(value, kind):
    return f'<span class="qg-pill qg-{kind}">{value}</span>'


def _risk_kind(v):
    return "good" if v < 0.2 else "warn" if v < 0.4 else "bad"


def _score_kind(v):
    return "good" if v >= 0.7 else "warn" if v >= 0.5 else "bad"


def bar_row(label, value, color):
    pct = max(0, min(100, value * 100))
    return (f'<div class="qg-bar-row"><span class="qg-bar-label">{label}</span>'
            f'<div class="qg-bar-track"><div class="qg-bar-fill" style="width:{pct:.0f}%;background:{color}"></div></div>'
            f'<span class="qg-bar-val">{value:.2f}</span></div>')


def dna_helix_svg(width=900, height=72, turns=5.0, s1=PRIMARY, s2=ACCENT,
                  rungs=True, opacity=1.0):
    """A clean vector DNA double helix (two sine strands + base-pair rungs)."""
    n = 160
    amp = height * 0.30
    mid = height / 2
    A, B = [], []
    for i in range(n + 1):
        x = width * i / n
        ph = turns * 2 * math.pi * i / n
        A.append((x, mid + amp * math.sin(ph)))
        B.append((x, mid + amp * math.sin(ph + math.pi)))
    pa = " ".join(f"{x:.1f},{y:.1f}" for x, y in A)
    pb = " ".join(f"{x:.1f},{y:.1f}" for x, y in B)
    bars = ""
    if rungs:
        for i in range(0, n + 1, 7):
            xa, ya = A[i]
            xb, yb = B[i]
            c = s1 if (i // 7) % 2 == 0 else s2
            bars += (f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" '
                     f'stroke="{c}" stroke-width="2" opacity="0.4"/>'
                     f'<circle cx="{xa:.1f}" cy="{ya:.1f}" r="2.6" fill="{s1}"/>'
                     f'<circle cx="{xb:.1f}" cy="{yb:.1f}" r="2.6" fill="{s2}"/>')
    return (f'<div style="opacity:{opacity};line-height:0;">'
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<polyline points="{pa}" fill="none" stroke="{s1}" stroke-width="3" stroke-linecap="round"/>'
            f'<polyline points="{pb}" fill="none" stroke="{s2}" stroke-width="3" stroke-linecap="round"/>'
            f'{bars}</svg></div>')


def stepper(active: int):
    html = '<div class="qg-stepper">'
    for i, label in enumerate(STEPS, start=1):
        state = "done" if i < active else "active" if i == active else "todo"
        mark = "✓" if state == "done" else str(i)
        html += (f'<div class="qg-step qg-{state}"><div class="qg-step-dot">{mark}</div>'
                 f'<div class="qg-step-label">{label}</div></div>')
        if i < len(STEPS):
            html += '<div class="qg-step-line"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def srow(k, v):
    return f'<div class="qg-srow"><span class="k">{k}</span><span class="v">{v}</span></div>'


def why_chosen(g):
    items = [
        ("High predicted knockout probability", g.outcome.knockout_prob >= 0.55),
        ("High on-target efficiency", g.scores.on_target >= 0.6),
        ("Low off-target risk", g.off_target.risk_score < 0.2),
        ("Good GC content and complexity", 0.4 <= g.gc_content <= 0.65 and g.scores.complexity >= 0.7),
        ("Well positioned for target disruption", g.scores.distance_to_target >= 0.5),
    ]
    html = ""
    for text, ok in items:
        cls, mark = ("qg-on", "✓") if ok else ("qg-off", "–")
        html += f'<div class="qg-check"><span class="dot {cls}">{mark}</span>{text}</div>'
    return html


# --------------------------------------------------------------------------- #
# View: Login / Sign-up                                                         #
# --------------------------------------------------------------------------- #
def view_login():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown(
            '<div style="text-align:center;margin-top:1.5rem;">'
            '<div style="font-size:2.4rem;">🧬</div>'
            '<div class="qg-brand" style="font-size:2rem;background:linear-gradient(90deg,#7A33A6,#C49AE0);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-family:Plus Jakarta Sans;'
            'font-weight:800;">Q-Guide</div>'
            '<div class="qg-sub">Quantum-assisted gRNA design</div></div>',
            unsafe_allow_html=True)
        st.markdown(dna_helix_svg(width=520, height=58, turns=5.0, opacity=0.9),
                    unsafe_allow_html=True)
        with st.container(border=True):
            t1, t2 = st.tabs(["Sign in", "Create account"])
            with t1:
                e = st.text_input("Email", key="li_email")
                p = st.text_input("Password", type="password", key="li_pw")
                if st.button("Sign in", type="primary", use_container_width=True):
                    ok, msg = login(e, p)
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        goto("new")
                st.caption("New here? Use the **Create account** tab to get "
                           f"{SIGNUP_BONUS} free credits.")
            with t2:
                n = st.text_input("Full name", key="su_name")
                e2 = st.text_input("Email", key="su_email")
                p2 = st.text_input("Password", type="password", key="su_pw")
                if st.button(f"Create account (+{SIGNUP_BONUS} credits)", type="primary",
                             use_container_width=True):
                    ok, msg = signup(n, e2, p2)
                    st.success(msg) if ok else st.error(msg)
                    if ok:
                        goto("new")
        st.markdown('<div class="qg-sub" style="text-align:center;font-size:0.8rem;">'
                    'Prototype — accounts &amp; credits are in-session only, no real '
                    'authentication or payments.</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar                                                                       #
# --------------------------------------------------------------------------- #
def sidebar():
    st.sidebar.markdown(
        '<div style="display:flex;align-items:center;gap:0.6rem;margin:0.2rem 0 0.5rem;">'
        '<span style="font-size:1.55rem;">🧬</span><div>'
        '<div class="qg-brand">Q-Guide</div>'
        '<div class="qg-brand-sub">QUANTUM-ASSISTED gRNA DESIGN</div></div></div>',
        unsafe_allow_html=True)
    st.sidebar.markdown(dna_helix_svg(width=240, height=44, turns=3.2,
                                      s1=ACCENT, s2="#EAD7FA"), unsafe_allow_html=True)

    # Account / credits chip
    a = acct()
    low = a["credits"] < CREDITS_PER_RUN
    st.sidebar.markdown(
        f'<div class="qg-acct"><div class="qg-acct-row">'
        f'<div class="qg-avatar">{a["name"][:1].upper()}</div>'
        f'<div><div class="qg-acct-name">{a["name"]}</div>'
        f'<div class="qg-acct-plan">{a["plan"]}</div></div></div>'
        f'<div class="qg-credit {"low" if low else ""}">💎 {a["credits"]} credits'
        f'<span class="qg-credit-sub">{CREDITS_PER_RUN}/run</span></div></div>',
        unsafe_allow_html=True)
    if st.sidebar.button("💳  Buy Credits", use_container_width=True,
                         type="primary" if low else "secondary"):
        goto("buy")
    st.sidebar.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    if st.sidebar.button("➕  New Project", use_container_width=True,
                         type="primary" if not low else "secondary"):
        goto("new")
    if st.sidebar.button("📁  Projects", use_container_width=True):
        goto("project" if active_project() else "new")
    if st.sidebar.button("👤  Account", use_container_width=True):
        goto("account")
    if st.sidebar.button("⚙️  Settings", use_container_width=True):
        goto("settings")
    if st.sidebar.button("📄  Documentation", use_container_width=True):
        goto("docs")

    projects = a["projects"]
    if projects:
        st.sidebar.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.sidebar.caption("PROJECTS")
        active = st.session_state.get("active")
        for pid, proj in reversed(list(projects.items())):
            is_active = (pid == active) and st.session_state["view"] == "project"
            if st.sidebar.button(f"📁  {proj['name']} · {pid}", key=f"proj_{pid}",
                                 use_container_width=True,
                                 type="primary" if is_active else "secondary"):
                st.session_state["active"] = pid
                goto("project")

    st.sidebar.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    if projects:
        recent = "".join(
            f"<div style='display:flex;justify-content:space-between;'>"
            f"<span>{p['name']} · {p['id']}</span><span style='color:#A892BE'>"
            f"{len(p['response'].guides)}g</span></div>"
            for p in list(reversed(list(projects.values())))[:3])
        st.sidebar.markdown(f'<div class="qg-help"><b>Recent runs</b><br>{recent}</div>',
                            unsafe_allow_html=True)
    else:
        st.sidebar.markdown('<div class="qg-help"><b>What Q-Guide does</b><br>'
                            'Generates gRNAs, predicts the biological <i>outcome</i> of an edit, '
                            'and picks the best guide set with quantum-inspired optimization.</div>',
                            unsafe_allow_html=True)
    st.sidebar.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.sidebar.button("↪  Log out", use_container_width=True):
        logout()
    st.sidebar.caption("Q-Guide v1.0 (prototype) · © 2026")


# --------------------------------------------------------------------------- #
# View: New project                                                             #
# --------------------------------------------------------------------------- #
def view_new_project():
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">New Project</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="qg-sub">Configure a CRISPR design run. Fill the cards, review the '
                'summary, then run the pipeline.</div>', unsafe_allow_html=True)
    st.markdown(dna_helix_svg(width=1000, height=70, turns=6.0, opacity=0.9),
                unsafe_allow_html=True)
    st.write("")
    stepper(active=1)
    st.write("")

    main, right = st.columns([2.3, 1], gap="medium")

    with main:
        with st.container(border=True):
            st.markdown('<div class="qg-cardtitle">🧬 Sequence Input</div>', unsafe_allow_html=True)
            st.text_area("DNA sequence (FASTA headers ok)", _load_example(), height=140,
                         key="np_seq", label_visibility="collapsed")
            st.text_input("Project / gene name", "DEMO1", key="np_gene")

        with st.container(border=True):
            st.markdown('<div class="qg-cardtitle">⚙️ CRISPR System</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.selectbox("Cas enzyme", list(CAS_PROFILES.keys()), key="np_cas")
            c2.text_input("PAM override (blank = default)", value="", key="np_pam")
            st.selectbox("Organism", ["human", "mouse", "zebrafish", "yeast", "e_coli"], key="np_org")

        with st.container(border=True):
            st.markdown('<div class="qg-cardtitle">🧪 Experimental Context</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.selectbox("Desired outcome", [o.value for o in DesiredOutcome], key="np_outcome")
            c2.selectbox("Cell type (optional)",
                         ["", "stem_cell", "neuron", "hek293", "primary_t", "cancer_line"], key="np_cell")
            c3, c4 = st.columns(2)
            c3.selectbox("Delivery (optional)",
                         ["", "rnp", "plasmid", "lentivirus", "aav", "electroporation"], key="np_delivery")
            c4.selectbox("Expression level (optional)", ["", "low", "medium", "high"], key="np_expr")
            st.number_input("Temperature °C (optional)", value=37.0, step=0.5, key="np_temp")

        with st.container(border=True):
            st.markdown('<div class="qg-cardtitle">🎯 Optimization Settings</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.slider("Optimized set size (N)", 1, 6, 3, key="np_setsize")
            backends = optimization.available_backends()
            c2.selectbox("Optimization backend", list(backends.keys()),
                         format_func=lambda k: backends[k], key="np_backend")
            st.checkbox("Restrict to target region", key="np_usetarget")
            if st.session_state.get("np_usetarget"):
                t1, t2 = st.columns(2)
                t1.number_input("Target start", value=0, min_value=0, key="np_tstart")
                t2.number_input("Target end", value=60, min_value=1, key="np_tend")

    with right:
        _new_project_summary()
        st.write("")
        _new_run_summary()
        st.write("")
        a = acct()
        st.caption(f"💎 This run costs **{CREDITS_PER_RUN} credits** · balance "
                   f"**{a['credits']}**")
        if can_afford(CREDITS_PER_RUN):
            if st.button("🚀  Run Optimization", type="primary", use_container_width=True):
                _run_new_project()
        else:
            st.button("🚀  Run Optimization", type="primary", use_container_width=True,
                      disabled=True)
            st.error("Insufficient credits to run.")
            if st.button("💳  Buy Credits", type="primary", use_container_width=True):
                goto("buy")
        st.markdown('<div class="qg-card" style="margin-top:0.8rem;font-size:0.84rem;">'
                    '<div class="qg-cardtitle" style="font-size:0.92rem;">Input requirements</div>'
                    '<div class="qg-sub">• DNA only (A/C/G/T/N)<br>• ≥ ~25 bp so PAMs have room<br>'
                    '• FASTA headers are ignored<br>• Pick a Cas enzyme + desired outcome</div></div>',
                    unsafe_allow_html=True)


def _new_project_summary():
    ss = st.session_state
    seq_len = len(clean_sequence(ss.get("np_seq", "")))
    cas = ss.get("np_cas", "SpCas9")
    pam = ss.get("np_pam") or CAS_PROFILES.get(cas, CAS_PROFILES["SpCas9"]).pam
    rows = "".join([
        srow("Project", ss.get("np_gene") or "—"),
        srow("Sequence length", f"{seq_len} bp"),
        srow("Cas enzyme", cas),
        srow("PAM pattern", pam),
        srow("Organism", ss.get("np_org", "human")),
        srow("Desired outcome", ss.get("np_outcome", "knockout")),
        srow("Guide set size", str(ss.get("np_setsize", 3))),
        srow("Run status", '<span class="qg-pill qg-warn">Waiting to run</span>'),
    ])
    st.markdown(f'<div class="qg-card"><div class="qg-cardtitle">📋 Project Summary</div>{rows}</div>',
                unsafe_allow_html=True)


def _new_run_summary():
    rows = "".join([
        srow("PAM sites detected", "—"),
        srow("Candidate guides", "—"),
        srow("Guides selected", "—"),
        srow("Avg guide score", "—"),
        srow("Avg off-target risk", "—"),
        srow("Optimization method", "—"),
        srow("Status", '<span class="qg-pill qg-bad">Not started</span>'),
    ])
    st.markdown(f'<div class="qg-card"><div class="qg-cardtitle">📊 Run Summary</div>{rows}</div>',
                unsafe_allow_html=True)


def _run_new_project():
    if not can_afford(CREDITS_PER_RUN):
        st.error("Insufficient credits — buy more to run.")
        return
    ss = st.session_state
    target = (TargetRegion(start=int(ss.get("np_tstart", 0)), end=int(ss.get("np_tend", 60)))
              if ss.get("np_usetarget") else None)
    req = DesignRequest(
        sequence=ss.get("np_seq", ""), gene_name=ss.get("np_gene") or None,
        cas_enzyme=ss.get("np_cas", "SpCas9"), pam=ss.get("np_pam") or None,
        organism=ss.get("np_org", "human"), desired_outcome=ss.get("np_outcome", "knockout"),
        cell_type=ss.get("np_cell") or None, delivery_method=ss.get("np_delivery") or None,
        temperature=ss.get("np_temp", 37.0), expression_level=ss.get("np_expr") or None,
        target_region=target, set_size=ss.get("np_setsize", 3),
        optimizer_backend=ss.get("np_backend", "sa"))
    with st.spinner("Generating, scoring, predicting outcomes, optimizing…"):
        t0 = time.perf_counter()
        resp = pipeline.run_design(req)
        elapsed = time.perf_counter() - t0
    if not resp.guides:
        st.error("No guides found for this sequence / PAM. Check the input and try again.")
        return
    # Charge credits only on a successful run.
    charge(CREDITS_PER_RUN, f"Design run: {req.gene_name or 'untitled'}")
    acct()["runs"] += 1
    create_project(req, resp, elapsed)
    goto("project")


# --------------------------------------------------------------------------- #
# View: Project dashboard                                                       #
# --------------------------------------------------------------------------- #
def view_project():
    proj = active_project()
    if proj is None:
        st.info("No project selected.")
        if st.button("➕  Create one", type="primary"):
            goto("new")
        return

    resp, req = proj["response"], proj["request"]
    guides = resp.guides
    by_id = {g.guide_id: g for g in guides}
    pid = proj["id"]
    opt = resp.optimized_set

    head_l, head_r = st.columns([3, 1])
    with head_l:
        outcome = getattr(req.desired_outcome, "value", req.desired_outcome)
        st.markdown('<div class="qg-title" style="font-size:1.9rem;">Design Result</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="qg-sub">{req.cas_enzyme} ({guides[0].pam}) &nbsp;•&nbsp; '
                    f'{outcome.title()} &nbsp;•&nbsp; {req.organism.title()} &nbsp;•&nbsp; '
                    f'{proj["name"]}</div>', unsafe_allow_html=True)
    with head_r:
        st.markdown(f'<div style="text-align:right;"><span class="qg-badge">✓ Optimization complete</span>'
                    f'<div class="qg-sub" style="font-size:0.78rem;margin-top:0.3rem;margin-bottom:0.4rem;">'
                    f'Completed in {proj["elapsed"]:.2f}s · {opt.method}</div></div>',
                    unsafe_allow_html=True)
        if st.button("📊  Run Summary", key=f"rsbtn_{pid}", use_container_width=True):
            goto("run_summary")
    st.markdown(dna_helix_svg(width=1000, height=54, turns=6.0, opacity=0.8),
                unsafe_allow_html=True)
    st.write("")
    stepper(active=5)
    st.write("")

    on_vals = [g.scores.on_target for g in guides]
    on_mean = sum(on_vals) / len(on_vals)
    on_std = (sum((v - on_mean) ** 2 for v in on_vals) / len(on_vals)) ** 0.5
    off_mean = sum(g.off_target.risk_score for g in guides) / len(guides)
    ko_mean = sum(g.outcome.knockout_prob for g in guides) / len(guides)
    set_score = sum(by_id[s].final_score for s in opt.selected_guide_ids if s in by_id)

    cards = st.columns(6)
    metric_card(cards[0], "Candidate guides", f"{len(guides)}", "PAM sites found", INK)
    metric_card(cards[1], "Best single guide", resp.best_single_guide_id or "—",
                f"Score {guides[0].final_score:.3f}", PRIMARY)
    metric_card(cards[2], f"Best {req.set_size}-guide set",
                ", ".join(s.replace("gRNA_", "") for s in opt.selected_guide_ids),
                f"Set score {set_score:.3f}", PRIMARY)
    metric_card(cards[3], "Avg on-target", f"{on_mean:.2f}", f"± {on_std:.2f}", BLUE)
    metric_card(cards[4], "Avg off-target", f"{off_mean:.2f}", "lower is better", AMBER)
    metric_card(cards[5], "Predicted KO prob.", f"{ko_mean:.2f}", "population average", GREEN)
    st.write("")

    _selected_guide_band(proj, guides, by_id)
    st.write("")

    tabs = st.tabs(["Guide Rankings", "Best Guide Set", "Outcome & Prediction",
                    "Score Breakdown", "Context & Simulation", "Compare"])
    with tabs[0]:
        _tab_rankings(proj, guides)
    with tabs[1]:
        _tab_best_set(proj, guides, by_id)
    with tabs[2]:
        _tab_outcome(proj, guides, by_id)
    with tabs[3]:
        _tab_breakdown(proj, by_id)
    with tabs[4]:
        _tab_context_sim(proj, by_id)
    with tabs[5]:
        _tab_compare(proj, guides, by_id)

    st.write("")
    st.markdown('<div class="qg-disclaimer">ℹ️ Prototype. Scores and predictions are heuristic / '
                'rule-based; off-target is heuristic (no genome alignment). Replace with ML models '
                'and real off-target search for production use.</div>', unsafe_allow_html=True)


def _run_summary_card(proj, guides, by_id, off_mean):
    resp, opt = proj["response"], proj["response"].optimized_set
    avg_score = sum(g.final_score for g in guides) / len(guides)
    rows = "".join([
        srow("PAM sites detected", str(len(guides))),
        srow("Candidate guides", str(len(guides))),
        srow("Guides selected", str(len(opt.selected_guide_ids))),
        srow("Avg guide score", f"{avg_score:.3f}"),
        srow("Avg off-target risk", f"{off_mean:.3f}"),
        srow("Optimization method", opt.method),
        srow("Runtime", f"{proj['elapsed']:.2f}s"),
        srow("Status", '<span class="qg-pill qg-good">Complete</span>'),
    ])
    st.markdown(f'<div class="qg-card"><div class="qg-cardtitle">📊 Run Summary</div>{rows}</div>',
                unsafe_allow_html=True)

    rank_df = pd.DataFrame([{
        "rank": i + 1, "guide_id": g.guide_id, "sequence": g.sequence, "pam": g.pam,
        "strand": getattr(g.strand, "value", g.strand), "position": g.position,
        "final_score": g.final_score, "knockout_prob": g.outcome.knockout_prob,
        "on_target": g.scores.on_target, "off_target_risk": g.off_target.risk_score,
    } for i, g in enumerate(guides)])
    d1, d2 = st.columns(2)
    d1.download_button("⬇ CSV", rank_df.to_csv(index=False).encode(),
                       file_name=f"{proj['name']}_{proj['id']}_guides.csv",
                       mime="text/csv", use_container_width=True, key=f"csv_{proj['id']}")
    d2.download_button("⬇ JSON", resp.model_dump_json(indent=2).encode(),
                       file_name=f"{proj['name']}_{proj['id']}_design.json",
                       mime="application/json", use_container_width=True, key=f"json_{proj['id']}")


def _selected_guide_band(proj, guides, by_id):
    """Full-width horizontal Selected-Guide band (info · score bars · why-chosen)."""
    pid = proj["id"]
    ids = [g.guide_id for g in guides]
    sel = proj.get("selected_guide") or ids[0]

    sb1, sb2 = st.columns([1, 4])
    with sb1:
        st.markdown('<div class="qg-metric-label" style="margin-bottom:0.2rem;">Selected guide</div>',
                    unsafe_allow_html=True)
        gid = st.selectbox("Selected guide", ids, index=ids.index(sel) if sel in ids else 0,
                           key=f"sel_{pid}", label_visibility="collapsed")
    proj["selected_guide"] = gid
    g = by_id[gid]
    strand = getattr(g.strand, "value", g.strand)

    c1, c2, c3 = st.columns([1.1, 1.5, 1.2], gap="medium")
    c1.markdown(f"""
    <div class="qg-card" style="height:100%;">
      <div style="font-family:'Plus Jakarta Sans';font-weight:800;font-size:1.35rem;color:{PRIMARY};">{g.guide_id}</div>
      <div class="qg-metric-label" style="margin-top:0.5rem;">Sequence (5'→3')</div>
      <div><code>{g.sequence}</code></div>
      <div style="display:flex;gap:1.2rem;margin-top:0.7rem;flex-wrap:wrap;">
        <div><div class="qg-metric-label">PAM</div><b>{g.pam}</b></div>
        <div><div class="qg-metric-label">Strand</div><b>{strand}</b></div>
        <div><div class="qg-metric-label">Pos</div><b>{g.position}</b></div>
        <div><div class="qg-metric-label">GC</div><b>{g.gc_content*100:.0f}%</b></div>
        <div><div class="qg-metric-label">Total</div><b style="color:{PRIMARY};">{g.final_score:.3f}</b></div>
      </div>
    </div>""", unsafe_allow_html=True)

    bars = "".join([
        bar_row("On-target", g.scores.on_target, GREEN),
        bar_row("Knockout", g.outcome.knockout_prob, GREEN),
        bar_row("Off-target", g.off_target.risk_score, GREEN if g.off_target.risk_score < 0.2 else AMBER),
        bar_row("GC content", g.scores.gc_content, BLUE),
        bar_row("Complexity", g.scores.complexity, BLUE),
        bar_row("Context", min(1.0, g.context.multiplier), PRIMARY),
        bar_row("Structure pen.", g.scores.secondary_structure_penalty, AMBER),
    ])
    c2.markdown(f'<div class="qg-card" style="height:100%;"><div class="qg-cardtitle">Score breakdown</div>{bars}</div>',
                unsafe_allow_html=True)
    c3.markdown(f'<div class="qg-card" style="height:100%;"><div class="qg-cardtitle">Why this guide?</div>{why_chosen(g)}</div>',
                unsafe_allow_html=True)


def _tab_rankings(proj, guides):
    sel = proj.get("selected_guide")
    head = ("<tr><th>Rank</th><th>Guide</th><th>Sequence (5'→3')</th><th>PAM</th>"
            "<th>Pos</th><th>Strand</th><th>On-target</th><th>KO</th><th>Off-target</th><th>Total</th></tr>")
    body = ""
    for i, g in enumerate(guides[:12]):
        strand = getattr(g.strand, "value", g.strand)
        active = " qg-row-active" if g.guide_id == sel else ""
        star = "⭐ " if i == 0 else ""
        body += (f'<tr class="{active}"><td>{star}{i+1}</td><td class="qg-gid">{g.guide_id}</td>'
                 f'<td><code>{g.sequence}</code></td><td>{g.pam}</td><td>{g.position}</td><td>{strand}</td>'
                 f'<td>{pill(f"{g.scores.on_target:.2f}", _score_kind(g.scores.on_target))}</td>'
                 f'<td>{pill(f"{g.outcome.knockout_prob:.2f}", _score_kind(g.outcome.knockout_prob))}</td>'
                 f'<td>{pill(f"{g.off_target.risk_score:.2f}", _risk_kind(g.off_target.risk_score))}</td>'
                 f'<td><b style="color:{PRIMARY};">{g.final_score:.3f}</b></td></tr>')
    st.markdown(f'<div class="qg-tablewrap"><table class="qg-table">{head}{body}</table></div>',
                unsafe_allow_html=True)
    st.caption(f"Showing top 12 of {len(guides)} guides. Use the **Selected guide** dropdown "
               "(right) to inspect any guide — the panel updates instantly.")


def _tab_best_set(proj, guides, by_id):
    pid, opt, req = proj["id"], proj["response"].optimized_set, proj["request"]
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown('<div class="qg-cardtitle">Optimization mode</div>', unsafe_allow_html=True)
        k = st.slider("Number of guides (k)", 1, min(6, len(guides)), req.set_size, key=f"k_{pid}")
        if st.button("⚡  Re-optimize", type="primary", key=f"reopt_{pid}"):
            optimizer = optimization.make_optimizer(getattr(req, "optimizer_backend", "sa"))
            proj["response"].optimized_set = optimization.optimize_guide_set(
                guides, set_size=k, optimizer=optimizer)
            st.rerun()
    with c2:
        st.markdown('<div class="qg-cardtitle">Selected set</div>', unsafe_allow_html=True)
        st.markdown("  ".join(f"<span class='qg-pill qg-good'>{s}</span>"
                              for s in opt.selected_guide_ids), unsafe_allow_html=True)
        st.caption(f"method `{opt.method}` · objective {opt.objective_value}")
        for t in opt.tradeoffs:
            st.caption("• " + t)
    chosen = [by_id[s] for s in opt.selected_guide_ids if s in by_id]
    if chosen:
        st.plotly_chart(viz.comparison_grouped_bar(chosen), use_container_width=True, key=f"setcmp_{pid}")
        seq_len = len(clean_sequence(req.sequence))
        center = ((req.target_region.start + req.target_region.end) // 2
                  if req.target_region else seq_len // 2)
        st.plotly_chart(viz.genomic_track(chosen[0], chosen, seq_len, center),
                        use_container_width=True, key=f"settrack_{pid}")
    if opt.rejected_explanations:
        with st.expander("Why other guides were rejected"):
            st.dataframe(pd.DataFrame([{"Guide": k2, "Reason": v}
                                       for k2, v in opt.rejected_explanations.items()]),
                         use_container_width=True, hide_index=True)


def _tab_outcome(proj, guides, by_id):
    pid = proj["id"]
    g = by_id[proj.get("selected_guide", guides[0].guide_id)]
    c1, c2 = st.columns(2)
    c1.plotly_chart(viz.outcome_pie(g), use_container_width=True, key=f"opie_{pid}")
    c2.plotly_chart(viz.outcome_probability_bar(g), use_container_width=True, key=f"obar_{pid}")
    st.markdown('<div class="qg-cardtitle">🔮 Predict experiment results</div>', unsafe_allow_html=True)
    st.caption("Monte-Carlo a virtual cell population for any guide — predicted editing %, "
               "biallelic knockout with a 95% CI, genotype mix, and indel spectrum.")
    ids = [x.guide_id for x in guides]
    pc1, pc2 = st.columns([3, 1])
    pgid = pc1.selectbox("Guide to simulate", ids, index=ids.index(g.guide_id), key=f"pred_{pid}")
    quick = pc2.checkbox("Best vs worst", key=f"bw_{pid}")
    if st.button("🔮  Predict outcome", type="primary", key=f"runpred_{pid}"):
        with st.spinner("Simulating cell population…"):
            proj["pred"] = expsim.simulate_experiment(by_id[pgid])
            proj["pred_cmp"] = (expsim.compare_experiments([guides[0], guides[-1]]) if quick else None)
    res = proj.get("pred")
    if res:
        k, e = res["knockout_rate"], res["editing_efficiency"]
        mc = st.columns(3)
        metric_card(mc[0], "Editing efficiency", f"{e['mean']:.0%}",
                    f"95% CI {e['ci_low']:.0%}–{e['ci_high']:.0%}", BLUE)
        metric_card(mc[1], "Biallelic knockout", f"{k['mean']:.0%}",
                    f"95% CI {k['ci_low']:.0%}–{k['ci_high']:.0%}", GREEN)
        metric_card(mc[2], "Simulated", f"{res['replicates']}×{res['n_cells']}", "cells", INK)
        st.write("")
        st.info(res["verdict"])
        pg = st.columns(2)
        pg[0].plotly_chart(viz.ko_distribution_hist(res), use_container_width=True, key=f"kod_{pid}")
        pg[1].plotly_chart(viz.genotype_bar(res), use_container_width=True, key=f"geno_{pid}")
        st.plotly_chart(viz.indel_spectrum_bar(res), use_container_width=True, key=f"indel_{pid}")
        if proj.get("pred_cmp"):
            st.plotly_chart(viz.experiment_comparison_bar(proj["pred_cmp"]),
                            use_container_width=True, key=f"ecmp_{pid}")
        st.caption("⚠️ " + res["model"])


def _tab_breakdown(proj, by_id):
    pid = proj["id"]
    g = by_id[proj["selected_guide"]]
    c1, c2 = st.columns(2)
    c1.plotly_chart(viz.score_breakdown_bar(g), use_container_width=True, key=f"sb_{pid}")
    c2.plotly_chart(viz.final_contribution_bar(g), use_container_width=True, key=f"fc_{pid}")
    st.plotly_chart(viz.score_radar(g), use_container_width=True, key=f"radar_{pid}")


def _tab_context_sim(proj, by_id):
    pid, req = proj["id"], proj["request"]
    g = by_id[proj["selected_guide"]]
    st.markdown('<div class="qg-cardtitle">Context sensitivity</div>', unsafe_allow_html=True)
    st.json(g.context.applied, expanded=False)
    scenarios = [{"label": "stem cell", "cell_type": "stem_cell"},
                 {"label": "neuron", "cell_type": "neuron"},
                 {"label": "HEK293", "cell_type": "hek293"},
                 {"label": "30°C", "temperature": 30.0},
                 {"label": "37°C", "temperature": 37.0},
                 {"label": "SpCas9-HF1", "cas_enzyme": "SpCas9-HF1"}]
    sens = pipeline.context_sensitivity(req, g.guide_id, scenarios)
    st.plotly_chart(viz.context_sensitivity_line(g.guide_id, sens), use_container_width=True, key=f"sens_{pid}")
    st.markdown('<div class="qg-cardtitle">🧪 Experiment simulation</div>', unsafe_allow_html=True)
    axis_labels = {"cas_enzyme": "Cas enzyme", "cell_type": "Cell type",
                   "delivery_method": "Delivery method", "temperature": "Temperature",
                   "desired_outcome": "Editing objective"}
    a1, a2 = st.columns([3, 1])
    axis = a1.selectbox("Sweep axis", list(axis_labels.keys()),
                        format_func=lambda k: axis_labels[k], key=f"axis_{pid}")
    with a2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("Run", type="primary", key=f"runsim_{pid}", use_container_width=True)
    if run:
        with st.spinner("Simulating scenarios…"):
            proj["sim_results"] = pipeline.simulate_axis(req, axis)
    results = proj.get("sim_results")
    if results:
        st.plotly_chart(viz.simulation_comparison_bar(results), use_container_width=True, key=f"sim_{pid}")
        valid = [r for r in results if r["n_guides"] > 0]
        if valid:
            top = max(valid, key=lambda r: r["best_knockout"])
            st.success(f"Highest predicted knockout under **{top['label']}** "
                       f"({top['best_knockout']:.0%} via {top['best_guide']}).")


def _tab_compare(proj, guides, by_id):
    pid = proj["id"]
    ids = [g.guide_id for g in guides]
    pick = st.multiselect("Guides to compare", ids, default=ids[:min(3, len(ids))], key=f"cmp_{pid}")
    chosen = [by_id[i] for i in pick]
    if len(chosen) >= 2:
        st.plotly_chart(viz.comparison_grouped_bar(chosen), use_container_width=True, key=f"cg_{pid}")
        st.plotly_chart(viz.comparison_radar(chosen), use_container_width=True, key=f"cr_{pid}")
    else:
        st.caption("Pick at least two guides to compare.")


# --------------------------------------------------------------------------- #
# Settings / Documentation                                                      #
# --------------------------------------------------------------------------- #
def view_run_summary():
    proj = active_project()
    if proj is None:
        st.info("No project selected.")
        if st.button("➕  New Project", type="primary"):
            goto("new")
        return
    resp, req = proj["response"], proj["request"]
    guides = resp.guides
    by_id = {g.guide_id: g for g in guides}
    off_mean = sum(g.off_target.risk_score for g in guides) / len(guides)

    if st.button("←  Back to dashboard"):
        goto("project")
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">Run Summary</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="qg-sub">{proj["name"]} · {proj["id"]} · completed '
                f'{proj["created"]}</div>', unsafe_allow_html=True)
    st.markdown(dna_helix_svg(width=1000, height=54, turns=6.0, opacity=0.8),
                unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        _run_summary_card(proj, guides, by_id, off_mean)
    with c2:
        cas = req.cas_enzyme
        pam = guides[0].pam
        outcome = getattr(req.desired_outcome, "value", req.desired_outcome)
        seq_len = len(clean_sequence(req.sequence))
        rows = "".join([
            srow("Project / gene", proj["name"]),
            srow("Sequence length", f"{seq_len} bp"),
            srow("Cas enzyme", cas),
            srow("PAM pattern", pam),
            srow("Organism", req.organism),
            srow("Desired outcome", outcome),
            srow("Guide set size", str(req.set_size)),
            srow("Optimization backend", getattr(req, "optimizer_backend", "sa")),
            srow("Run status", '<span class="qg-pill qg-good">Complete</span>'),
        ])
        st.markdown(f'<div class="qg-card"><div class="qg-cardtitle">📋 Project Summary</div>'
                    f'{rows}</div>', unsafe_allow_html=True)


def view_account():
    a = acct()
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">Account</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="qg-sub">{a["name"]} · {a["email"]}</div>', unsafe_allow_html=True)
    st.write("")
    used = sum(-t["amount"] for t in a["transactions"] if t["type"] == "usage")
    cols = st.columns(4)
    metric_card(cols[0], "Credit balance", f"💎 {a['credits']}", "available", PRIMARY)
    metric_card(cols[1], "Plan", a["plan"], f"since {a['created'][:10]}", INK)
    metric_card(cols[2], "Design runs", f"{a['runs']}", f"{used} credits used", BLUE)
    metric_card(cols[3], "Projects", f"{len(a['projects'])}", "this session", GREEN)
    st.write("")

    c1, c2 = st.columns([1.5, 1], gap="medium")
    with c1:
        st.markdown('<div class="qg-cardtitle">Transaction history</div>', unsafe_allow_html=True)
        df = pd.DataFrame([{
            "When": t["ts"], "Type": t["type"].title(),
            "Credits": ("+" if t["amount"] >= 0 else "") + str(t["amount"]),
            "Balance": t["balance"], "Detail": t["desc"],
            "Paid": (f"${t['price']:.2f}" if t.get("price") else "—"),
        } for t in reversed(a["transactions"])])
        st.dataframe(df, use_container_width=True, hide_index=True, height=320)
    with c2:
        with st.container(border=True):
            st.markdown('<div class="qg-cardtitle">Profile</div>', unsafe_allow_html=True)
            new_name = st.text_input("Display name", a["name"], key="acct_name")
            if st.button("Save changes", key="save_name", use_container_width=True):
                a["name"] = new_name.strip() or a["name"]
                st.success("Saved.")
            st.caption(f"Email: {a['email']}")
            st.write("")
            if st.button("💳  Buy more credits", type="primary", use_container_width=True):
                goto("buy")
            if st.button("↪  Log out", use_container_width=True):
                logout()


def view_buy_credits():
    a = acct()
    if st.button("←  Back to account"):
        goto("account")
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">Buy Credits</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="qg-sub">Current balance: <b>💎 {a["credits"]} credits</b> · '
                f'each design run costs {CREDITS_PER_RUN} credits.</div>', unsafe_allow_html=True)
    st.write("")
    cols = st.columns(len(CREDIT_PACKAGES), gap="medium")
    for i, (col, pkg) in enumerate(zip(cols, CREDIT_PACKAGES)):
        pop = pkg.get("popular")
        with col:
            tag = '<span class="qg-poptag">Most popular</span>' if pop else ''
            st.markdown(f'<div class="qg-price {"pop" if pop else ""}">{tag}'
                        f'<div class="qg-price-name">{pkg["name"]}</div>'
                        f'<div class="qg-price-credits">{pkg["credits"]}</div>'
                        f'<div class="qg-price-sub">credits</div>'
                        f'<div class="qg-price-cost">${pkg["price"]}</div>'
                        f'<div class="qg-price-sub">{pkg["sub"]}</div></div>', unsafe_allow_html=True)
            if st.button(f"Buy {pkg['name']}", key=f"buy_{i}", use_container_width=True,
                         type="primary" if pop else "secondary"):
                add_credits(pkg["credits"], f"{pkg['name']} pack", float(pkg["price"]))
                st.success(f"✓ Added {pkg['credits']} credits (simulated payment).")
                st.rerun()
    st.write("")
    with st.expander("Custom amount"):
        amt = st.number_input("Credits", min_value=10, max_value=5000, value=100, step=10, key="cust_amt")
        price = round(amt * 0.18, 2)
        st.caption(f"≈ ${price:.2f} (simulated)")
        if st.button("Buy custom amount", key="buy_custom"):
            add_credits(int(amt), "Custom pack", price)
            st.success("✓ Credits added (simulated payment).")
            st.rerun()
    st.markdown('<div class="qg-disclaimer">💳 Demo checkout — no real payment is processed. '
                'The flow is structured to drop into Stripe (or another processor) later.</div>',
                unsafe_allow_html=True)


def view_settings():
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">Settings</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown('<div class="qg-cardtitle">Supported Cas systems</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([
        {"Enzyme": n, "PAM": p.pam, "Guide length": p.guide_length, "PAM side": p.pam_side}
        for n, p in CAS_PROFILES.items()]), use_container_width=True, hide_index=True)
    st.markdown('<div class="qg-cardtitle">Optimization backends</div>', unsafe_allow_html=True)
    for k, v in optimization.available_backends().items():
        st.write(f"• `{k}` — {v}")
    st.caption("D-Wave runs offline via dimod/dwave-samplers; one-line swap to real quantum "
               "hardware with a Leap token. See docs/QUANTUM_INTEGRATION.md.")


def view_docs():
    st.markdown('<div class="qg-title" style="font-size:1.9rem;">Documentation</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown("**Q-Guide** optimises for the predicted biological *outcome* of an edit — not just "
                "which guide cuts best. Pipeline: generate → score → off-target → context → outcome → "
                "multi-objective → quantum-inspired optimization → explain.")
    st.markdown('<div class="qg-cardtitle">Modelling assumptions</div>', unsafe_allow_html=True)
    for a in assumptions():
        st.write("•", a)
    st.markdown('<div class="qg-disclaimer">Research prototype. Heuristic / rule-based scores and '
                'predictions — not validated against wet-lab data. Not for clinical use.</div>',
                unsafe_allow_html=True)


VIEWS = {"new": view_new_project, "project": view_project,
         "run_summary": view_run_summary, "account": view_account,
         "buy": view_buy_credits, "settings": view_settings, "docs": view_docs}


def main():
    _init_state()
    inject_css()
    if acct() is None:            # not logged in -> gate everything behind login
        view_login()
        return
    sidebar()
    VIEWS.get(st.session_state["view"], view_new_project)()


if __name__ == "__main__":
    main()
