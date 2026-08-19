"""
Formula explanation layer (formula-upgrade brief, Part 6).

Turns the numeric Precision-Score breakdown and the guide-set optimization into
plain-English, auditable explanations:

  * ``explain_precision(guide)`` — why a guide's Precision Score is high or low, which
    variables helped, which hurt, what data was missing, what assumptions were made and
    what should be validated experimentally.
  * ``explain_set(guides, comparison)`` — why the optimized set was chosen, why some
    individually-strong guides were excluded, what tradeoff the optimizer made, whether
    the set is safer / more diverse / more outcome-focused / more confident, and what the
    quantum-inspired optimizer actually contributed.

Everything is derived from structured facts already attached to the guides (no new
science, no clinical claims), so the output is deterministic and auditable. A future
version can route the same structured dict through an LLM for richer prose.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from qguide.app.schemas import Guide
from qguide.core import optimization as opt

_VALIDATE = {
    "on_target": "measure on-target editing efficiency (amplicon/indel sequencing)",
    "off_target_severity": "run genome-wide off-target profiling (GUIDE-seq / CIRCLE-seq)",
    "severe_coding_offtargets": "verify the flagged coding off-target loci empirically",
    "exon_importance": "confirm exon rank/constitutiveness against the real gene model",
    "domain_disruption": "check the cut position against annotated protein domains",
    "transcript_coverage": "confirm isoform coverage for your target transcript(s)",
    "variant_conflict": "screen the guide site for common variants in your cell line",
    "knockout": "confirm functional knockout (protein-level assay / phenotype)",
    "repair_quality": "sequence the repair-outcome distribution at the cut site",
}


# --------------------------------------------------------------------------- #
# Per-guide precision explanation                                              #
# --------------------------------------------------------------------------- #
def explain_precision(guide: Guide, top_k: int = 4) -> Dict[str, object]:
    p = guide.precision
    comps = p.components
    pos = [c for c in comps if c.group == "positive" and c.available]
    pen = [c for c in comps if c.group == "penalty" and c.available and c.contribution < -1e-9]

    helped = sorted(pos, key=lambda c: c.contribution, reverse=True)[:top_k]
    hurt = sorted(pen, key=lambda c: c.contribution)[:top_k]

    missing = [{"key": c.key, "label": c.label} for c in comps if not c.available]
    proxy_or_prov = [c for c in comps if c.available and c.source in ("proxy", "provisional")]

    assumptions = [
        "On-target, outcome and repair signals are interpretable heuristics (V1), "
        "not models trained on wet-lab data.",
        "Off-target risk & severity are heuristic (no genome alignment / CFD).",
    ]
    if proxy_or_prov:
        assumptions.append("Proxy/provisional components in this score: "
                           + ", ".join(c.label for c in proxy_or_prov) + ".")
    if missing:
        assumptions.append("Unavailable components abstained (not fabricated) and only "
                           "raised uncertainty: " + ", ".join(m["label"] for m in missing) + ".")

    validate: List[str] = []
    for c in hurt + helped:
        tip = _VALIDATE.get(c.key)
        if tip and tip not in validate:
            validate.append(tip)
    if not validate:
        validate.append("measure on-target editing efficiency (amplicon/indel sequencing)")

    text = _precision_prose(guide, helped, hurt, missing)
    return {
        "guide_id": guide.guide_id,
        "score": p.score,
        "confidence": p.confidence_label,
        "data_completeness": p.data_completeness,
        "why_high": [f"{c.label} ({c.contribution:+.3f})" for c in helped],
        "why_low": [f"{c.label} ({c.contribution:+.3f})" for c in hurt],
        "helped": [c.key for c in helped],
        "hurt": [c.key for c in hurt],
        "missing_data": missing,
        "assumptions": assumptions,
        "validate": validate,
        "text": text,
    }


def _precision_prose(guide, helped, hurt, missing) -> str:
    p = guide.precision
    parts = [f"{guide.guide_id} has a QGuide Precision Score of {p.score:.2f} "
             f"({p.confidence_label} confidence; {p.data_completeness:.0%} of components "
             f"had data)."]
    if helped:
        parts.append(" It scored well mainly because of "
                     + ", ".join(c.label.lower() for c in helped) + ".")
    if hurt:
        parts.append(" It was pulled down most by "
                     + ", ".join(c.label.lower() for c in hurt) + ".")
    if missing:
        parts.append(f" {len(missing)} biological component(s) had no data source and "
                     "abstained (raising uncertainty rather than being guessed): "
                     + ", ".join(m["label"].lower() for m in missing[:4])
                     + ("…" if len(missing) > 4 else "") + ".")
    parts.append(" All values are computational predictions and require experimental "
                 "validation.")
    return "".join(parts)


def explain_precisions(guides: List[Guide]) -> List[Dict[str, object]]:
    return [explain_precision(g) for g in guides]


# --------------------------------------------------------------------------- #
# Per-set explanation                                                          #
# --------------------------------------------------------------------------- #
def explain_set(guides: List[Guide], comparison: Dict[str, object],
                preset: str = "balanced",
                weights: Optional[opt.QuboWeights] = None) -> Dict[str, object]:
    """Explain an optimized guide set given a comparison report (from
    ``quantum_comparison_report.compare_selection_strategies``)."""
    w = weights or opt.get_weights(comparison.get("preset", preset))
    by_id = {g.guide_id: g for g in guides}
    sets = comparison.get("sets", {})
    optimized = sets.get("classical_optimized", {}).get("selected", [])
    topn = sets.get("top_n_individual", {}).get("selected", [])
    opt_rep = sets.get("classical_optimized", {})
    topn_rep = sets.get("top_n_individual", {})

    # Why some individually-strong guides were excluded.
    excluded = [gid for gid in topn if gid not in set(optimized)]
    exclusions: Dict[str, str] = {}
    for gid in excluded:
        g = by_id.get(gid)
        if not g:
            continue
        # find the selected guide it is most redundant with
        best_sid, best_red = None, 0.0
        for sid in optimized:
            r = opt.redundancy_ij(g, by_id[sid], w)
            if r > best_red:
                best_red, best_sid = r, sid
        if best_sid and best_red > 0.3:
            exclusions[gid] = (f"individually strong but redundant with selected {best_sid} "
                               f"(redundancy {best_red:.2f}) — adding it would not diversify "
                               "the set")
        elif g.off_target.risk_score > 0.4:
            exclusions[gid] = (f"individually strong but carries elevated off-target risk "
                               f"({g.off_target.risk_score:.2f}) the set-objective penalised")
        else:
            exclusions[gid] = ("did not improve the combined set objective beyond the "
                               "chosen guides")

    # What did the optimizer prioritise? (biggest metric gain vs Top-N)
    character = _set_character(opt_rep, topn_rep)

    verdict = comparison.get("verdict", {})
    quantum_note = _extract_quantum_note(verdict)

    text = _set_prose(optimized, topn, excluded, character, opt_rep, topn_rep, quantum_note)
    return {
        "selected": optimized,
        "top_n_individual": topn,
        "excluded_strong_guides": exclusions,
        "character": character,
        "tradeoff": {
            "combined_outcome_delta": round(opt_rep.get("combined_outcome", 0)
                                            - topn_rep.get("combined_outcome", 0), 4),
            "off_target_burden_delta": round(opt_rep.get("off_target_burden", 0)
                                             - topn_rep.get("off_target_burden", 0), 4),
            "diversity_delta": round(opt_rep.get("diversity", 0)
                                     - topn_rep.get("diversity", 0), 4),
            "uncertainty_delta": round(opt_rep.get("uncertainty", 0)
                                       - topn_rep.get("uncertainty", 0), 4),
        },
        "quantum_contribution": quantum_note,
        "text": text,
    }


def _set_character(opt_rep, topn_rep) -> str:
    """Which dimension did set-optimization most improve vs the naive Top-N?"""
    gains = {
        "safer (lower off-target burden)": topn_rep.get("off_target_burden", 0)
        - opt_rep.get("off_target_burden", 0),
        "more diverse (better coverage)": opt_rep.get("diversity", 0)
        - topn_rep.get("diversity", 0),
        "more outcome-focused": opt_rep.get("combined_outcome", 0)
        - topn_rep.get("combined_outcome", 0),
        "more confident (lower uncertainty)": topn_rep.get("uncertainty", 0)
        - opt_rep.get("uncertainty", 0),
    }
    best = max(gains.items(), key=lambda kv: kv[1])
    if best[1] <= 1e-9:
        return "equivalent to the Top-N (no redundancy to resolve)"
    return best[0]


def _extract_quantum_note(verdict: Dict[str, object]) -> str:
    if not verdict:
        return "No quantum comparison available."
    if verdict.get("quantum_inspired_meaningful_improvement"):
        return ("The quantum-inspired sampler found a lower-energy set than classical "
                "annealing on the same QUBO.")
    if verdict.get("classical_equals_quantum"):
        return ("The quantum-inspired sampler solved the SAME QUBO and returned the SAME "
                "set as classical — at this scale it is a search strategy, not better "
                "biology.")
    return ("The quantum-inspired backend was not exercised (not installed) — it fell "
            "back to the classical solver.")


def _set_prose(optimized, topn, excluded, character, opt_rep, topn_rep, quantum_note) -> str:
    parts = [f"The optimizer selected {', '.join(optimized)}"]
    if set(optimized) == set(topn):
        parts.append(" — the same guides as the naive Top-N, because there was no "
                     "redundancy or shared failure mode to resolve.")
    else:
        parts.append(f" instead of the Top-N-by-individual-score ({', '.join(topn)}).")
        if excluded:
            parts.append(f" It dropped {', '.join(excluded)} despite strong individual "
                         "scores to avoid redundancy / shared risk.")
        parts.append(f" The resulting set is {character}: combined outcome "
                     f"{opt_rep.get('combined_outcome', 0):.2f} vs "
                     f"{topn_rep.get('combined_outcome', 0):.2f}, off-target burden "
                     f"{opt_rep.get('off_target_burden', 0):.2f} vs "
                     f"{topn_rep.get('off_target_burden', 0):.2f}, diversity "
                     f"{opt_rep.get('diversity', 0):.2f} vs "
                     f"{topn_rep.get('diversity', 0):.2f}.")
    parts.append(" " + quantum_note)
    parts.append(" Computational recommendation — validate experimentally before use.")
    return "".join(parts)
