"""
Stage 6 -- Benchmark / comparison module.

A plug-in structure for comparing QGuide's outcome-first ranking against other
ranking philosophies. The built-in strategies EMULATE THE EMPHASIS of common tools
(efficiency-first, specificity-first, etc.) so the UI has something to show and so we
can explain *why* QGuide's ordering differs.

IMPORTANT / HONESTY: these baselines are NOT the real CHOPCHOP / CRISPOR / GuideScan
outputs. Those require genome alignment and each tool's published models. Real
integrations plug in here by adding a `RankingStrategy` that calls the actual tool
(or its scores). Everything returned is marked `provisional`.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from qguide.app.schemas import Guide

RankKey = Callable[[Guide], float]


def _off_risk(g: Guide) -> float:
    return g.off_target.risk_score


# Each strategy is a sort key (higher = better). They emphasise different things.
STRATEGIES: Dict[str, RankKey] = {
    # efficiency-first with a light off-target-count penalty (CHOPCHOP-like emphasis)
    "chopchop_like": lambda g: g.scores.on_target - 0.02 * g.off_target.potential_off_target_count,
    # specificity-weighted efficiency (CRISPOR-like emphasis)
    "crispor_like": lambda g: 0.5 * g.scores.on_target + 0.5 * (1.0 - _off_risk(g)),
    # specificity-first (GuideScan-like emphasis)
    "guidescan_like": lambda g: 1.0 - _off_risk(g),
    # QGuide's ensemble, outcome-first ranking
    "qguide_outcome": lambda g: g.ensemble.final_qguide_score,
}

LABELS = {
    "chopchop_like": "CHOPCHOP-style (efficiency-first)",
    "crispor_like": "CRISPOR-style (specificity-weighted)",
    "guidescan_like": "GuideScan-style (specificity-first)",
    "qguide_outcome": "QGuide (outcome-first ensemble)",
}


def _rank(guides: List[Guide], key: RankKey) -> List[str]:
    return [g.guide_id for g in sorted(guides, key=key, reverse=True)]


def _spearman(a: List[str], b: List[str]) -> float:
    """Spearman rank correlation between two orderings of the same ids."""
    ra = {gid: i for i, gid in enumerate(a)}
    rb = {gid: i for i, gid in enumerate(b)}
    ids = [i for i in a if i in rb]
    n = len(ids)
    if n < 2:
        return 1.0
    d2 = sum((ra[i] - rb[i]) ** 2 for i in ids)
    return round(1.0 - (6.0 * d2) / (n * (n * n - 1)), 4)


def benchmark(guides: List[Guide], top_k: int = 5) -> Dict[str, object]:
    if not guides:
        return {"provisional": True, "rankings": {}, "comparison": {}, "why_differs": []}

    rankings = {name: _rank(guides, key) for name, key in STRATEGIES.items()}
    ref = rankings["qguide_outcome"]
    ref_top = set(ref[:top_k])

    comparison = {}
    for name, order in rankings.items():
        overlap = len(ref_top & set(order[:top_k])) / max(1, top_k)
        comparison[name] = {
            "label": LABELS[name],
            "top_guide": order[0],
            "top_k_overlap_with_qguide": round(overlap, 3),
            "spearman_vs_qguide": _spearman(ref, order),
        }

    why: List[str] = []
    by_id = {g.guide_id: g for g in guides}
    qtop = ref[0]
    for name in ("chopchop_like", "crispor_like", "guidescan_like"):
        other_top = rankings[name][0]
        if other_top != qtop:
            og, qg = by_id[other_top], by_id[qtop]
            reason = []
            if og.off_target.risk_score > qg.off_target.risk_score + 0.03:
                reason.append("off-target safety")
            if qg.outcome.knockout_prob > og.outcome.knockout_prob + 0.03:
                reason.append("predicted outcome (knockout probability)")
            if qg.ensemble.uncertainty_score < og.ensemble.uncertainty_score - 0.03:
                reason.append("lower uncertainty")
            why.append(
                f"{LABELS[name]} ranks {other_top} first; QGuide ranks {qtop} first, "
                f"mainly due to {', '.join(reason) or 'the combined ensemble weighting'}.")

    return {
        "provisional": True,
        "note": ("Baselines emulate the EMPHASIS of CHOPCHOP/CRISPOR/GuideScan for "
                 "illustration — they are NOT those tools' real outputs, which require "
                 "genome alignment and each tool's published models. Plug real tools in "
                 "via a RankingStrategy."),
        "top_k": top_k,
        "rankings": rankings,
        "comparison": comparison,
        "why_differs": why,
    }
