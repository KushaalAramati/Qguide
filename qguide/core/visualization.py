"""
Step 9 -- Visualization.

Pure functions that turn a `Guide` (or a list of guides) into Plotly figures.
They return `plotly.graph_objects.Figure` objects so they can be embedded by the
Streamlit frontend, returned as JSON from FastAPI (`fig.to_json()`), or rendered
in a future React client via react-plotly.

No figure here depends on any other Q-Guide module beyond the data model -- the
visualization layer is fully decoupled and individually replaceable.
"""
from __future__ import annotations

from typing import List

import plotly.graph_objects as go

from qguide.app.schemas import Guide

# Royal Purple palette (kept in sync with the frontend design system).
_POS = "#7A33A6"     # rich royal purple
_NEG = "#C2566B"     # rose
_ACCENT = "#9B59B6"  # orchid


# A. Score breakdown ---------------------------------------------------------- #
def score_breakdown_bar(guide: Guide) -> go.Figure:
    labels = ["On-target", "GC", "PAM", "Complexity", "Seq quality",
              "Distance", "Off-target safety", "Structure safety"]
    values = [
        guide.scores.on_target,
        guide.scores.gc_content,
        guide.scores.pam,
        guide.scores.complexity,
        guide.scores.sequence_quality,
        guide.scores.distance_to_target,
        1.0 - guide.off_target.risk_score,
        1.0 - guide.scores.secondary_structure_penalty,
    ]
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=_POS))
    fig.update_layout(title=f"Score breakdown -- {guide.guide_id}",
                      xaxis=dict(range=[0, 1], title="score (0-1)"),
                      height=380, margin=dict(l=120, r=20, t=50, b=40))
    return fig


def score_radar(guide: Guide) -> go.Figure:
    cats = ["On-target", "Knockout", "Functional", "Off-target safety",
            "GC", "Context"]
    vals = [
        guide.scores.on_target,
        guide.outcome.knockout_prob,
        guide.outcome.functional_disruption_score,
        1.0 - guide.off_target.risk_score,
        guide.scores.gc_content,
        min(1.0, guide.context.multiplier),
    ]
    cats += [cats[0]]
    vals += [vals[0]]
    fig = go.Figure(go.Scatterpolar(r=vals, theta=cats, fill="toself",
                                    line_color=_ACCENT, name=guide.guide_id))
    fig.update_layout(title=f"Profile -- {guide.guide_id}",
                      polar=dict(radialaxis=dict(range=[0, 1])), height=380)
    return fig


def final_contribution_bar(guide: Guide) -> go.Figure:
    """Signed contributions to the final multi-objective score."""
    items = sorted(guide.final_breakdown.items(), key=lambda kv: kv[1])
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    colors = [_NEG if v < 0 else _POS for v in vals]
    fig = go.Figure(go.Bar(x=vals, y=labels, orientation="h", marker_color=colors))
    fig.update_layout(title=f"Final-score contributions -- {guide.guide_id}",
                      xaxis_title="contribution (signed)",
                      height=360, margin=dict(l=120, r=20, t=50, b=40))
    return fig


# B. Predicted editing outcome ------------------------------------------------ #
def outcome_pie(guide: Guide) -> go.Figure:
    o = guide.outcome
    labels = ["Frameshift", "In-frame indel", "No edit"]
    values = [o.frameshift_prob, o.in_frame_indel_prob, o.no_edit_prob]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
    fig.update_layout(title=f"Predicted edit outcome -- {guide.guide_id}", height=360)
    return fig


def outcome_probability_bar(guide: Guide) -> go.Figure:
    o = guide.outcome
    labels = ["Knockout", "Frameshift", "Exon disruption",
              "In-frame indel", "Functional disruption"]
    values = [o.knockout_prob, o.frameshift_prob, o.exon_disruption_prob,
              o.in_frame_indel_prob, o.functional_disruption_score]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=_ACCENT))
    fig.update_layout(title=f"Outcome probabilities -- {guide.guide_id}",
                      yaxis=dict(range=[0, 1]), height=360)
    return fig


# C. Genomic position --------------------------------------------------------- #
def genomic_track(guide: Guide, neighbours: List[Guide], seq_length: int,
                  target_center: int) -> go.Figure:
    fig = go.Figure()
    # baseline
    fig.add_shape(type="line", x0=0, x1=seq_length, y0=0, y1=0,
                  line=dict(color="#888", width=2))
    # target marker
    fig.add_vline(x=target_center, line=dict(color=_ACCENT, dash="dash"),
                  annotation_text="target")
    # neighbour guides
    for g in neighbours:
        color = _POS if g.strand in ("+", getattr(g.strand, "value", "+")) else _NEG
        y = 0.3 if str(getattr(g.strand, "value", g.strand)) == "+" else -0.3
        fig.add_trace(go.Scatter(
            x=[g.position, g.end], y=[y, y], mode="lines",
            line=dict(color=color, width=6 if g.guide_id == guide.guide_id else 2),
            opacity=1.0 if g.guide_id == guide.guide_id else 0.4,
            name=g.guide_id, hovertext=f"{g.guide_id} {g.sequence} ({g.pam})",
        ))
        fig.add_trace(go.Scatter(x=[g.cut_site], y=[y], mode="markers",
                                 marker=dict(color=color, size=8, symbol="x"),
                                 showlegend=False, hovertext=f"cut@{g.cut_site}"))
    fig.update_layout(title=f"Genomic context -- {guide.guide_id}",
                      xaxis_title="position (bp)", yaxis=dict(showticklabels=False,
                      range=[-1, 1], title="strand"), height=320)
    return fig


# D. Off-target dashboard ----------------------------------------------------- #
def mismatch_distribution_bar(guide: Guide) -> go.Figure:
    bins = guide.off_target.mismatch_distribution
    x = [b.mismatches for b in bins]
    y = [b.count for b in bins]
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=_NEG))
    fig.update_layout(title=f"Predicted off-target mismatch distribution -- {guide.guide_id}",
                      xaxis_title="# mismatches", yaxis_title="predicted hits", height=320)
    return fig


# E. Context sensitivity ------------------------------------------------------ #
def context_sensitivity_line(guide_id: str, scenarios: List[dict]) -> go.Figure:
    """scenarios: [{'label': 'neuron', 'final_score': 0.7, 'rank': 3}, ...]"""
    x = [s["label"] for s in scenarios]
    y = [s["final_score"] for s in scenarios]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers",
                               line=dict(color=_ACCENT), name="final score"))
    fig.update_layout(title=f"Context sensitivity -- {guide_id}",
                      yaxis=dict(range=[0, 1], title="final score"),
                      xaxis_title="scenario", height=340)
    return fig


# F. Guide comparison --------------------------------------------------------- #
def comparison_grouped_bar(guides: List[Guide]) -> go.Figure:
    metrics = [
        ("Final", lambda g: g.final_score),
        ("Knockout", lambda g: g.outcome.knockout_prob),
        ("On-target", lambda g: g.scores.on_target),
        ("Off-target risk", lambda g: g.off_target.risk_score),
        ("Functional", lambda g: g.outcome.functional_disruption_score),
    ]
    fig = go.Figure()
    for name, fn in metrics:
        fig.add_trace(go.Bar(name=name, x=[g.guide_id for g in guides],
                             y=[fn(g) for g in guides]))
    fig.update_layout(title="Guide comparison", barmode="group",
                      yaxis=dict(range=[0, 1]), height=400)
    return fig


# Experiment outcome prediction ---------------------------------------------- #
def ko_distribution_hist(result: dict) -> go.Figure:
    """Distribution of predicted knockout rate across simulated replicate dishes."""
    ko = result["knockout_rate"]
    fig = go.Figure(go.Histogram(x=result["ko_distribution"], nbinsx=25,
                                 marker_color=_POS, opacity=0.85))
    fig.add_vline(x=ko["mean"], line=dict(color=_ACCENT, width=2),
                  annotation_text=f"mean {ko['mean']:.0%}")
    fig.add_vrect(x0=ko["ci_low"], x1=ko["ci_high"], fillcolor=_ACCENT,
                  opacity=0.12, line_width=0, annotation_text="95% CI")
    fig.update_layout(title=f"Predicted knockout rate across replicates — {result['guide_id']}",
                      xaxis=dict(title="biallelic knockout fraction", tickformat=".0%"),
                      yaxis_title="replicate dishes", height=360)
    return fig


def genotype_bar(result: dict) -> go.Figure:
    g = result["genotypes"]
    labels = ["Wild-type", "Heterozygous", "Biallelic KO"]
    vals = [g["wild_type"], g["heterozygous"], g["biallelic_ko"]]
    colors = [_NEG, "#C9892F", _POS]
    fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=colors,
                           text=[f"{v:.0%}" for v in vals], textposition="auto"))
    fig.update_layout(title=f"Predicted genotype distribution — {result['guide_id']}",
                      yaxis=dict(range=[0, 1], tickformat=".0%"), height=340)
    return fig


def indel_spectrum_bar(result: dict) -> go.Figure:
    sp = result["indel_spectrum"]
    colors = [_POS if s > 0 else _NEG if s < 0 else "#888" for s in sp["sizes"]]
    fig = go.Figure(go.Bar(x=sp["sizes"], y=sp["fraction"], marker_color=colors))
    fig.update_layout(title=f"Predicted indel spectrum (edited alleles) — {result['guide_id']}",
                      xaxis_title="indel size (bp, + = insertion)",
                      yaxis_title="fraction of edits", height=340)
    return fig


def experiment_comparison_bar(rows: list) -> go.Figure:
    """Predicted KO rate with CI error bars across several guides (best vs worst)."""
    x = [r["guide_id"] for r in rows]
    y = [r["ko_mean"] for r in rows]
    err_plus = [r["ko_ci_high"] - r["ko_mean"] for r in rows]
    err_minus = [r["ko_mean"] - r["ko_ci_low"] for r in rows]
    fig = go.Figure(go.Bar(
        x=x, y=y, marker_color=_POS,
        error_y=dict(type="data", symmetric=False, array=err_plus, arrayminus=err_minus),
    ))
    fig.update_layout(title="Predicted knockout rate (95% CI) by guide",
                      yaxis=dict(range=[0, 1], tickformat=".0%", title="biallelic KO"),
                      height=360)
    return fig


# H. Experiment simulation --------------------------------------------------- #
def simulation_comparison_bar(results: List[dict]) -> go.Figure:
    """Compare best-guide knockout / functional / off-target safety across scenarios."""
    x = [r["label"] for r in results]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Best knockout", x=x,
                         y=[r.get("best_knockout", 0) for r in results], marker_color=_POS))
    fig.add_trace(go.Bar(name="Best functional", x=x,
                         y=[r.get("best_functional", 0) for r in results], marker_color=_ACCENT))
    fig.add_trace(go.Bar(name="Off-target safety", x=x,
                         y=[1.0 - r.get("best_off_target", 0) for r in results], marker_color="#A569BD"))
    fig.update_layout(title="Experiment simulation -- predicted outcome by scenario",
                      barmode="group", yaxis=dict(range=[0, 1], title="probability / score"),
                      xaxis_title="scenario", height=420)
    return fig


def simulation_objective_line(results: List[dict]) -> go.Figure:
    """Optimized-set objective and set-mean knockout across scenarios."""
    x = [r["label"] for r in results]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r.get("set_mean_knockout", 0) for r in results],
                             mode="lines+markers", name="set mean knockout",
                             line=dict(color=_ACCENT)))
    fig.update_layout(title="Optimized-set mean knockout by scenario",
                      yaxis=dict(range=[0, 1], title="mean knockout prob"),
                      xaxis_title="scenario", height=340)
    return fig


def comparison_radar(guides: List[Guide]) -> go.Figure:
    cats = ["On-target", "Knockout", "Functional", "Off-target safety", "Quality"]
    fig = go.Figure()
    for g in guides:
        vals = [g.scores.on_target, g.outcome.knockout_prob,
                g.outcome.functional_disruption_score,
                1.0 - g.off_target.risk_score, g.scores.sequence_quality]
        fig.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]],
                                      fill="toself", name=g.guide_id, opacity=0.5))
    fig.update_layout(title="Guide comparison (radar)",
                      polar=dict(radialaxis=dict(range=[0, 1])), height=420)
    return fig
