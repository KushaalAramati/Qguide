"""
Step 10 -- Explainability layer.

Turns the numeric breakdowns attached to each guide into expert-sounding natural
language. Every recommendation answers:
  1. Why was this guide selected?
  2. Why was it ranked above others?
  3. What improved its score?
  4. What reduced its score?
  5. Under what conditions would another guide be preferred?
  6. What assumptions were made?

These are template-driven (deterministic, auditable) -- a future version can route
the same structured facts through an LLM for richer prose without changing callers.
"""
from __future__ import annotations

from typing import List, Optional

from qguide.app.schemas import DesignRequest, Guide


def _v(x) -> str:
    """Render an enum-or-str field as its plain value (handles str-subclass enums)."""
    return getattr(x, "value", x)

_ASSUMPTIONS = [
    "On-target and outcome scores come from interpretable rule-based models (V1), not wet-lab data.",
    "Off-target risk is a heuristic estimate (no genome-wide alignment was run).",
    "Indel/frameshift fractions follow published NHEJ priors, not locus-specific measurements.",
]


def _top_contributions(guide: Guide, positive: bool, k: int = 3) -> List[str]:
    items = [(name, v) for name, v in guide.final_breakdown.items()]
    items = [(n, v) for n, v in items if (v > 0) == positive]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    label = {
        "on_target": "on-target efficiency",
        "knockout": "knockout probability",
        "functional": "functional disruption",
        "context": "context compatibility",
        "quality": "sequence quality",
        "off_target": "off-target risk",
        "structure": "secondary-structure penalty",
        "gc_balance": "GC imbalance",
    }
    return [f"{label.get(n, n)} ({v:+.3f})" for n, v in items[:k]]


def explain_guide(
    guide: Guide,
    rank: int,
    runner_up: Optional[Guide] = None,
    selected_in_set: bool = False,
) -> str:
    o = guide.outcome
    parts = []

    headline = (
        f"{guide.guide_id} ranks #{rank} (final score {guide.final_score:.2f}, "
        f"confidence {guide.confidence:.0%})."
    )
    parts.append(headline)

    parts.append(
        f"It is predicted to achieve a {o.knockout_prob:.0%} knockout probability "
        f"with {o.frameshift_prob:.0%} frameshift and {o.no_edit_prob:.0%} no-edit outcomes, "
        f"at {_v(guide.off_target.risk_category)} "
        f"off-target risk ({guide.off_target.risk_score:.0%})."
    )

    ups = _top_contributions(guide, positive=True)
    downs = _top_contributions(guide, positive=False)
    if ups:
        parts.append("Strengths: " + ", ".join(ups) + ".")
    if downs:
        parts.append("Weaknesses: " + ", ".join(downs) + ".")

    if runner_up is not None and runner_up.guide_id != guide.guide_id:
        parts.append(_compare(guide, runner_up))

    parts.append(_conditional(guide))

    if selected_in_set:
        parts.append("Included in the optimized multi-guide set for coverage with low redundancy.")

    return " ".join(parts)


def _compare(guide: Guide, other: Guide) -> str:
    diffs = []
    if other.scores.on_target > guide.scores.on_target + 0.02:
        diffs.append(
            f"although {other.guide_id} had slightly higher on-target efficiency "
            f"({other.scores.on_target:.2f} vs {guide.scores.on_target:.2f})"
        )
    if other.off_target.risk_score > guide.off_target.risk_score:
        diffs.append(
            f"{other.guide_id}'s higher off-target risk "
            f"({other.off_target.risk_score:.0%} vs {guide.off_target.risk_score:.0%}) lowered its ranking"
        )
    if other.outcome.knockout_prob < guide.outcome.knockout_prob:
        diffs.append(
            f"and its lower knockout probability "
            f"({other.outcome.knockout_prob:.0%} vs {guide.outcome.knockout_prob:.0%}) was decisive"
        )
    if not diffs:
        return f"It edged out {other.guide_id} on the combined multi-objective score."
    return "Compared with " + other.guide_id + ": " + ", ".join(diffs) + "."


def _conditional(guide: Guide) -> str:
    """Step 10.5 -- when would a different guide win?"""
    if guide.off_target.risk_score > 0.3:
        return ("A lower-risk alternative would be preferred when specificity is paramount "
                "(e.g. therapeutic editing or a high-fidelity Cas variant).")
    if guide.scores.distance_to_target < 0.5:
        return ("A guide closer to the target centre would be preferred if precise "
                "positional disruption (e.g. a specific exon) is required.")
    return ("Another guide would be preferred under a different objective "
            "(e.g. precise deletion vs frameshift knockout) or experimental context.")


def explain_all(guides: List[Guide], selected_ids: Optional[List[str]] = None) -> List[Guide]:
    selected = set(selected_ids or [])
    for rank, g in enumerate(guides, start=1):
        runner_up = guides[rank] if rank < len(guides) else None
        g.explanation = explain_guide(
            g, rank, runner_up=runner_up, selected_in_set=g.guide_id in selected
        )
    return guides


def summarize_run(request: DesignRequest, guides: List[Guide], selected_ids: List[str]) -> str:
    if not guides:
        return "No candidate guides were found for the given sequence / PAM."
    best = guides[0]
    gene = request.gene_name or "the target"
    outcome = request.desired_outcome if isinstance(request.desired_outcome, str) else request.desired_outcome.value
    return (
        f"For {gene} ({outcome}, {request.cas_enzyme}/{best.pam}), Q-Guide evaluated "
        f"{len(guides)} candidate guides. Top recommendation: {best.guide_id} "
        f"(final {best.final_score:.2f}, knockout {best.outcome.knockout_prob:.0%}, "
        f"off-target {best.off_target.risk_score:.0%}). "
        f"Optimized {len(selected_ids)}-guide set: {', '.join(selected_ids)}. "
        f"Assumptions: {_ASSUMPTIONS[0]}"
    )


def assumptions() -> List[str]:
    return list(_ASSUMPTIONS)
