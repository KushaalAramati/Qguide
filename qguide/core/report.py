"""
Stage 6 -- Scientific report generator.

Turns a `DesignResponse` into a structured, self-documenting report dict: the user's
inputs and assumptions, the candidate guides with their component scores, the selected
guide set with per-guide reasoning, off-target and confidence limitations, and an
explicit experimental-validation note. It makes NO clinical/therapeutic claims and
uses model-based / predicted / requires-validation language throughout.

Returned as a plain JSON-serialisable dict so it can be rendered in the UI, exported,
or turned into a PDF later without coupling to any format.
"""
from __future__ import annotations

from typing import Dict, List

from qguide.app.schemas import DesignResponse
from qguide.core.explainability import assumptions


def build_report(resp: DesignResponse, top_n: int = 10) -> Dict[str, object]:
    req = resp.request
    guides = resp.guides
    by_id = {g.guide_id: g for g in guides}
    sel_ids = resp.optimized_set.selected_guide_ids

    def outcome_val(x):
        return getattr(x, "value", x)

    inputs = {
        "project": req.gene_name,
        "organism": req.organism,
        "cas_enzyme": req.cas_enzyme,
        "desired_outcome": outcome_val(req.desired_outcome),
        "risk_tolerance": getattr(req, "risk_tolerance", "balanced"),
        "cell_type": req.cell_type,
        "delivery_method": req.delivery_method,
        "temperature_c": req.temperature,
        "guide_set_size": req.set_size,
        "optimizer_mode": resp.optimized_set.mode,
        "sequence_length_bp": len(req.sequence.replace("\n", "")),
    }

    candidate_rows = []
    for i, g in enumerate(guides[:top_n], start=1):
        e = g.ensemble
        candidate_rows.append({
            "rank": i, "guide_id": g.guide_id, "sequence": g.sequence, "pam": g.pam,
            "position": g.position, "strand": getattr(g.strand, "value", g.strand),
            "gc_percent": round(g.gc_content * 100, 1),
            "components": {
                "on_target": e.on_target_score, "off_target_safety": e.off_target_score,
                "specificity": e.specificity_score, "desired_outcome": e.desired_outcome_score,
                "repair_outcome": e.repair_outcome_score, "genomic_context": e.genomic_context_score,
                "cell_context": e.cell_context_score, "model_agreement": e.model_agreement_score,
                "uncertainty": e.uncertainty_score,
            },
            "final_qguide_score": e.final_qguide_score,
            "legacy_final_score": g.final_score,
            "confidence": e.confidence_label,
            "badges": e.badges,
            "provisional_components": e.provisional,
        })

    selected = []
    for gid in sel_ids:
        g = by_id.get(gid)
        if not g:
            continue
        selected.append({
            "guide_id": gid, "sequence": g.sequence,
            "final_qguide_score": g.ensemble.final_qguide_score,
            "confidence": g.ensemble.confidence_label,
            "explanation": g.explanation,
        })

    # Off-target limitations: whichever guides have genome_backed=False (all, for now)
    ot_warning = next((g.off_target.warning for g in guides if g.off_target.warning), "")
    high_risk = [g.guide_id for g in guides if g.off_target.risk_category
                 in ("high", getattr(g.off_target.risk_category, "value", ""))
                 or g.off_target.risk_score >= 0.55]

    confidence_limits: List[str] = []
    if not req.cell_type:
        confidence_limits.append("No cell type provided — cell-context effects are estimated "
                                 "and overall confidence is reduced.")
    if not req.delivery_method:
        confidence_limits.append("No delivery method provided — delivery efficiency is uncertain.")
    prov = sorted({c for g in guides for c in g.ensemble.provisional})
    if prov:
        confidence_limits.append("Provisional (placeholder) score components in use: "
                                 + ", ".join(prov) + ". These are heuristics pending real "
                                 "trained-model / genome-backed implementations.")

    return {
        "title": f"QGuide design report — {req.gene_name or 'untitled'}",
        "generated_note": "Computational, model-based predictions. Not clinical guidance.",
        "summary": resp.summary,
        "inputs": inputs,
        "assumptions": assumptions(),
        "candidate_guides": candidate_rows,
        "selected_set": selected,
        "optimization": {
            "mode": resp.optimized_set.mode,
            "method": resp.optimized_set.method,
            "top_n_by_individual_score": resp.optimized_set.top_n_individual,
            "comparison_note": resp.optimized_set.comparison_note,
            "tradeoffs": resp.optimized_set.tradeoffs,
        },
        "off_target_limitations": {
            "warning": ot_warning,
            "high_risk_guides": high_risk,
            "genome_backed": False,
        },
        "confidence_limitations": confidence_limits,
        "validation_note": ("All scores are model-based predictions and REQUIRE "
                            "experimental validation (e.g., on-target efficiency assays "
                            "and genome-wide off-target profiling such as GUIDE-seq / "
                            "CIRCLE-seq) before use."),
    }
