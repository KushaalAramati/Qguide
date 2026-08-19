"""
QGuide Precision Score (formula-upgrade brief, Part 1 + Part 7).

A single 0..1 score per guide, assembled from many NAMED, reweightable components and
returned WITH its full breakdown so the UI can show raw value -> weight -> weighted
contribution -> final score for every term.

Design rules (all enforced here):
  * Positive components raise the score; penalty components lower it.
  * A component whose data is UNAVAILABLE abstains: it is dropped from the weighted
    mean (its weight is renormalised away) and instead lowers ``data_completeness`` and
    raises ``uncertainty``. QGuide never invents a number for missing annotation.
  * Every component carries an honest ``source`` (real | heuristic | proxy |
    provisional | unknown) so nothing heuristic is disguised as validated.
  * Weights are fully configurable and preset-driven (``config/precision_weights.json``).

SCIENTIFIC HONESTY: the biological signals themselves come from classical
bioinformatics / interpretable heuristics upstream. This layer only *combines and
explains* them — it makes no new biological claim and no clinical claim.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from qguide.app.schemas import (
    BiologicalContext,
    DesignRequest,
    Guide,
    PrecisionComponent,
    PrecisionScore,
)
from qguide.core import off_target as ot_mod

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "precision_weights.json",
)

# Human labels for the transparency UI.
_LABELS = {
    "on_target": "On-target cutting efficiency",
    "pam": "PAM strength",
    "gc_balance": "GC balance",
    "sequence_quality": "Guide sequence quality",
    "desired_outcome": "Desired-outcome probability",
    "knockout": "Predicted knockout probability",
    "frameshift": "Predicted frameshift probability",
    "repair_quality": "Repair-outcome quality",
    "functional_disruption": "Functional disruption probability",
    "exon_importance": "Exon importance",
    "transcript_coverage": "Transcript-isoform coverage",
    "domain_disruption": "Protein-domain disruption",
    "conservation": "Conservation relevance",
    "cell_compat": "Cell-type compatibility",
    "delivery_compat": "Delivery-method compatibility",
    "model_agreement": "Model agreement",
    "evidence_strength": "Evidence strength",
    "off_target_severity": "Off-target severity",
    "severe_coding_offtargets": "Severe coding off-targets",
    "regulatory_offtargets": "Promoter/enhancer off-targets",
    "essential_gene_offtargets": "Essential-gene off-targets",
    "mismatch_tolerant_risk": "Mismatch-tolerant binding risk",
    "gc_extremes": "Extreme GC content",
    "repetitive_risk": "Repetitive-sequence risk",
    "variant_conflict": "SNP/variant conflict",
    "uncertain_cell_context": "Uncertain cell-type context",
    "model_disagreement": "Model disagreement",
    "no_genome_index": "No genome index (off-target)",
    "no_repair_model_support": "No trained repair model",
}


# --------------------------------------------------------------------------- #
# Weights + presets (config-driven; code holds a safe fallback)                 #
# --------------------------------------------------------------------------- #
@dataclass
class PrecisionWeights:
    positive: Dict[str, float] = field(default_factory=dict)
    penalty: Dict[str, float] = field(default_factory=dict)


_FALLBACK = {
    "positive": {
        "on_target": 1.0, "pam": 0.4, "gc_balance": 0.4, "sequence_quality": 0.6,
        "desired_outcome": 1.0, "knockout": 0.9, "frameshift": 0.6, "repair_quality": 0.7,
        "functional_disruption": 0.8, "exon_importance": 0.7, "transcript_coverage": 0.6,
        "domain_disruption": 0.7, "conservation": 0.4, "cell_compat": 0.5,
        "delivery_compat": 0.4, "model_agreement": 0.6, "evidence_strength": 0.5,
    },
    "penalty": {
        "off_target_severity": 1.2, "severe_coding_offtargets": 1.0,
        "regulatory_offtargets": 0.6, "essential_gene_offtargets": 1.0,
        "mismatch_tolerant_risk": 0.6, "gc_extremes": 0.4, "repetitive_risk": 0.4,
        "variant_conflict": 0.6, "uncertain_cell_context": 0.4, "model_disagreement": 0.5,
        "no_genome_index": 0.5, "no_repair_model_support": 0.3,
    },
}


@lru_cache(maxsize=1)
def _load_config(path: str = _CONFIG_PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"default": _FALLBACK, "presets": {"balanced": {}}}


def get_weights(preset: str = "balanced") -> PrecisionWeights:
    """Return the (config-driven) weights for a preset. Unknown preset -> balanced."""
    cfg = _load_config()
    base = cfg.get("default", _FALLBACK)
    pos = dict(base.get("positive", {}))
    pen = dict(base.get("penalty", {}))
    override = cfg.get("presets", {}).get(preset)
    if override is None and preset != "balanced":
        override = cfg.get("presets", {}).get("balanced", {})
    if override:
        pos.update(override.get("positive", {}))
        pen.update(override.get("penalty", {}))
    return PrecisionWeights(positive=pos, penalty=pen)


def preset_names() -> List[str]:
    return list(_load_config().get("presets", {}).keys())


# --------------------------------------------------------------------------- #
# Component extraction. Each returns (raw|None, source, note).                   #
# raw is always "higher = stronger effect" in the component's own direction     #
# (positive terms: higher=better; penalty terms: higher=worse).                 #
# None => the component abstains (unknown data).                                 #
# --------------------------------------------------------------------------- #
def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _positive_components(g: Guide, req: DesignRequest) -> Dict[str, Tuple[Optional[float], str, str]]:
    e = g.ensemble
    bc: BiologicalContext = g.bio_context
    out: Dict[str, Tuple[Optional[float], str, str]] = {}

    out["on_target"] = (g.scores.on_target, "heuristic", "QGuide composite on-target heuristic.")
    out["pam"] = (g.scores.pam, "heuristic", "PAM-strength heuristic.")
    out["gc_balance"] = (g.scores.gc_content, "heuristic", "Triangular GC preference (peak 50%).")
    out["sequence_quality"] = (g.scores.sequence_quality, "heuristic", "Clean-spacer composite.")
    out["desired_outcome"] = (
        (e.desired_outcome_score if e else g.outcome.functional_disruption_score),
        "heuristic", "Goal-specific desired-outcome model.")
    out["knockout"] = (g.outcome.knockout_prob, "heuristic", "Rule-based NHEJ knockout probability.")
    out["frameshift"] = (g.outcome.frameshift_prob, "heuristic", "Predicted frameshift fraction.")
    out["repair_quality"] = (
        (e.repair_outcome_score if e else g.outcome.frameshift_prob),
        "heuristic", "Repair-outcome quality proxy.")
    out["functional_disruption"] = (g.outcome.functional_disruption_score, "heuristic",
                                    "Composite functional-disruption score.")

    # Biological-context components (proxy or unknown).
    out["exon_importance"] = _bc_term(bc, "exon_importance")
    out["transcript_coverage"] = _bc_term(bc, "transcript_coverage")
    out["domain_disruption"] = _bc_term(bc, "domain_disruption")
    out["conservation"] = _bc_term(bc, "conservation")
    out["cell_compat"] = _bc_term(bc, "cell_context_confidence")

    # Delivery-method compatibility: only if a delivery method was actually provided.
    if getattr(req, "delivery_method", None):
        dm = g.context.applied.get("delivery_method", 1.0) if g.context else 1.0
        out["delivery_compat"] = (_clamp(dm), "real", "Delivery-method efficiency multiplier.")
    else:
        out["delivery_compat"] = (None, "unknown", "No delivery method provided.")

    out["model_agreement"] = (
        (e.model_agreement_score if e else None), "heuristic",
        "Cross-model agreement over available on-target models.")
    out["evidence_strength"] = _evidence_strength(g)
    return out


def _penalty_components(g: Guide, req: DesignRequest) -> Dict[str, Tuple[Optional[float], str, str]]:
    e = g.ensemble
    bc: BiologicalContext = g.bio_context
    sev = getattr(g.off_target, "severity", None)
    out: Dict[str, Tuple[Optional[float], str, str]] = {}

    out["off_target_severity"] = (
        (sev.severity_score if sev else g.off_target.risk_score),
        "provisional", "Location/seed/CFD-weighted off-target severity (heuristic hits).")
    if sev is not None:
        out["severe_coding_offtargets"] = (_clamp(sev.coding_hits / 3.0), "provisional",
                                           f"{sev.coding_hits} coding-exon off-target hit(s).")
        out["regulatory_offtargets"] = (_clamp(sev.regulatory_hits / 3.0), "provisional",
                                        f"{sev.regulatory_hits} promoter/enhancer hit(s).")
        if sev.essential_gene_hits is None:
            out["essential_gene_offtargets"] = (None, "unknown",
                                                "No essential/disease gene database configured.")
        else:
            out["essential_gene_offtargets"] = (_clamp(sev.essential_gene_hits / 2.0), "real",
                                                f"{sev.essential_gene_hits} essential-gene hit(s).")
    else:
        for k in ("severe_coding_offtargets", "regulatory_offtargets", "essential_gene_offtargets"):
            out[k] = (None, "unknown", "No off-target severity profile available.")

    out["mismatch_tolerant_risk"] = (g.off_target.risk_score, "heuristic",
                                     "Aggregate promiscuity / mismatch-tolerant binding risk.")
    out["gc_extremes"] = (_gc_extreme(g.gc_content), "real", "Distance of GC% from the safe band.")
    out["repetitive_risk"] = (_repetitive_risk(g.sequence), "heuristic",
                              "Low-complexity / tandem-repeat content of the spacer.")
    out["variant_conflict"] = _bc_term(bc, "variant_conflict_risk")

    cell_conf = bc.cell_context_confidence if bc else None
    if cell_conf is None:
        out["uncertain_cell_context"] = (None, "unknown", "Cell-context confidence unavailable.")
    else:
        out["uncertain_cell_context"] = (_clamp(1.0 - cell_conf), "real",
                                         "1 - cell-context confidence.")

    if e and e.model_agreement_score is not None:
        out["model_disagreement"] = (_clamp(1.0 - e.model_agreement_score), "heuristic",
                                     "1 - cross-model agreement.")
    else:
        out["model_disagreement"] = (None, "unknown", "Model agreement unavailable.")

    out["no_genome_index"] = (0.0 if g.off_target.genome_backed else 1.0, "real",
                              "Off-target search is heuristic (no genome alignment).")
    out["no_repair_model_support"] = _repair_support_penalty(g)
    return out


def _bc_term(bc: BiologicalContext, field_name: str) -> Tuple[Optional[float], str, str]:
    val = getattr(bc, field_name, None) if bc else None
    src = (bc.sources.get(field_name, "unknown") if bc else "unknown")
    if val is None:
        return (None, "unknown", f"{field_name} unavailable (abstains, lowers confidence).")
    return (_clamp(val), src, f"{field_name} from {src} source.")


def _evidence_strength(g: Guide) -> Tuple[Optional[float], str, str]:
    e = g.ensemble
    if not e or not e.model_scores:
        return (0.5, "heuristic", "No per-model breakdown; default evidence weight.")
    total = len(e.model_scores)
    have = sum(1 for m in e.model_scores if m.available and m.score is not None)
    return (_clamp(have / total) if total else 0.0, "real",
            f"{have}/{total} named models produced a score.")


def _gc_extreme(gc: float) -> float:
    dev = abs(gc - 0.5)
    return _clamp((dev - 0.2) / 0.25)          # 0 within 30-70% GC, ramps beyond


def _repetitive_risk(seq: str) -> float:
    rep = ot_mod._repetitive_motifs(seq)
    lowc = ot_mod._low_complexity(seq)
    return _clamp(0.5 * rep + 0.5 * lowc)


def _repair_support_penalty(g: Guide) -> Tuple[float, str, str]:
    e = g.ensemble
    repair = [m for m in (e.model_scores if e else []) if m.task == "repair"]
    if any(m.kind == "real" and m.available for m in repair):
        return (0.0, "real", "A trained repair model is installed.")
    if any(m.available and m.score is not None for m in repair):
        return (0.5, "real", "Only a heuristic repair model is available (no trained model).")
    return (1.0, "real", "No repair-outcome model available.")


# --------------------------------------------------------------------------- #
# Assembly                                                                      #
# --------------------------------------------------------------------------- #
def compute_precision(g: Guide, request: DesignRequest,
                      weights: Optional[PrecisionWeights] = None,
                      preset: str = "balanced") -> PrecisionScore:
    w = weights or get_weights(preset)
    pos = _positive_components(g, request)
    pen = _penalty_components(g, request)

    components: List[PrecisionComponent] = []
    pos_sum = pos_mass = 0.0
    pen_sum = pen_mass = 0.0
    missing: List[str] = []
    provisional: List[str] = []
    n_defined = 0
    n_available = 0

    for key, (raw, source, note) in pos.items():
        weight = float(w.positive.get(key, 0.0))
        n_defined += 1
        if raw is None:
            components.append(PrecisionComponent(
                key=key, label=_LABELS.get(key, key), group="positive", raw=None,
                weight=weight, contribution=0.0, available=False, source="unknown", note=note))
            missing.append(key)
            continue
        n_available += 1
        contrib = weight * raw
        pos_sum += contrib
        pos_mass += weight
        if source in ("proxy", "provisional"):
            provisional.append(key)
        components.append(PrecisionComponent(
            key=key, label=_LABELS.get(key, key), group="positive", raw=round(raw, 4),
            weight=weight, contribution=round(contrib, 4), available=True,
            source=source, note=note))

    for key, (raw, source, note) in pen.items():
        weight = float(w.penalty.get(key, 0.0))
        n_defined += 1
        if raw is None:
            components.append(PrecisionComponent(
                key=key, label=_LABELS.get(key, key), group="penalty", raw=None,
                weight=weight, contribution=0.0, available=False, source="unknown", note=note))
            missing.append(key)
            continue
        n_available += 1
        contrib = weight * raw
        pen_sum += contrib
        pen_mass += weight
        if source in ("proxy", "provisional"):
            provisional.append(key)
        components.append(PrecisionComponent(
            key=key, label=_LABELS.get(key, key), group="penalty", raw=round(raw, 4),
            weight=weight, contribution=round(-contrib, 4), available=True,
            source=source, note=note))

    # Score: positives minus penalties, normalised by the available positive mass, in 0..1.
    score = _clamp((pos_sum - pen_sum) / max(pos_mass, 1e-9))

    data_completeness = (n_available / n_defined) if n_defined else 0.0
    base_unc = g.ensemble.uncertainty_score if (g.ensemble and g.ensemble.uncertainty_score) else 0.3
    uncertainty = _clamp(0.5 * base_unc + 0.5 * (1.0 - data_completeness))
    conf = "high" if uncertainty < 0.25 else "low" if uncertainty > 0.55 else "medium"

    rationale = _rationale(g, score, conf, components, missing, data_completeness)

    return PrecisionScore(
        score=round(score, 4),
        confidence_label=conf,
        uncertainty=round(uncertainty, 4),
        data_completeness=round(data_completeness, 4),
        positive_mass=round(pos_mass, 4),
        penalty_mass=round(pen_mass, 4),
        components=components,
        missing=missing,
        provisional=provisional,
        preset=preset,
        rationale=rationale,
    )


def _rationale(g, score, conf, components, missing, completeness) -> str:
    pos = [c for c in components if c.group == "positive" and c.available]
    pen = [c for c in components if c.group == "penalty" and c.available]
    top_pos = sorted(pos, key=lambda c: c.contribution, reverse=True)[:2]
    top_pen = sorted(pen, key=lambda c: c.contribution)[:2]  # most negative first
    parts = [f"{g.guide_id} Precision Score {score:.2f} ({conf} confidence, "
             f"{completeness:.0%} of components had data)."]
    if top_pos:
        parts.append(" Lifted most by " + ", ".join(c.label.lower() for c in top_pos) + ".")
    strong_pen = [c for c in top_pen if c.contribution < -1e-6]
    if strong_pen:
        parts.append(" Held back most by " + ", ".join(c.label.lower() for c in strong_pen) + ".")
    if missing:
        parts.append(f" {len(missing)} component(s) had no data and abstained "
                     f"(raising uncertainty, not fabricated): {', '.join(missing[:4])}"
                     + ("…" if len(missing) > 4 else "") + ".")
    parts.append(" Computational prediction — requires experimental validation.")
    return "".join(parts)


def compute_precision_scores(guides: List[Guide], request: DesignRequest,
                             weights: Optional[PrecisionWeights] = None,
                             preset: str = "balanced") -> List[Guide]:
    w = weights or get_weights(preset)
    for g in guides:
        g.precision = compute_precision(g, request, w, preset)
    return guides
