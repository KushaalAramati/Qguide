"""
Ensemble scoring layer (Stage 2).

This is the transparent, multi-component QGuide score. Instead of one opaque number,
each guide gets a set of named component scores (all 0..1) and a `final_qguide_score`
that is a *visible* weighted combination of them. The weights depend on the user's
GOAL (knockout / precise edit / base edit / CRISPRi-a / screening) and RISK TOLERANCE,
so "what matters" changes with intent:

    final_qguide_score = (
          w_on_target        * on_target_score
        + w_desired_outcome  * desired_outcome_score
        + w_specificity      * specificity_score
        + w_repair           * repair_outcome_score
        + w_genomic_context  * genomic_context_score
        + w_cell_context     * cell_context_score
        + w_model_agreement  * model_agreement_score
        - w_off_target       * off_target_risk
        - w_uncertainty      * uncertainty_score
    ) / positive_weight_mass     # clamped to 0..1

SCIENTIFIC HONESTY: several components are heuristic/placeholder right now and are
returned in `provisional` so the UI can flag them. They map cleanly onto real models
later (Azimuth/Rule Set 2/3, CRISPRon, inDelphi/Lindel, CFD/MIT off-target, gene-
structure annotation) through the existing scoring/off-target/outcome interfaces.
"""
from __future__ import annotations

from statistics import pstdev
from typing import Dict, List

from qguide.app.schemas import DesignRequest, EnsembleScore, Guide
from qguide.core import outcome_modes

# --------------------------------------------------------------------------- #
# Goal weight profiles                                                          #
# --------------------------------------------------------------------------- #
# Map a DesiredOutcome value -> a base "goal" used to pick a weight profile.
_OUTCOME_TO_GOAL = {
    "knockout": "knockout",
    "gene_disruption": "knockout",
    "exon_targeting": "knockout",
    "deletion": "knockout",
    "precise_edit": "precise_edit",
    "base_edit": "base_edit",
    "prime_edit": "prime_edit",
    "crispri": "regulation",
    "crispra": "regulation",
    "screen": "screen",
    "custom": "knockout",
}

# Each profile weights the positive components; off_target and uncertainty are the
# two penalty weights. They don't need to sum to 1 (the final score is normalised by
# the positive mass). Comments give the rationale.
WEIGHT_PROFILES: Dict[str, Dict[str, float]] = {
    "knockout": {        # prioritise frameshift / functional disruption
        "on_target": 0.22, "desired_outcome": 0.26, "specificity": 0.14,
        "repair": 0.12, "genomic_context": 0.10, "cell_context": 0.06,
        "model_agreement": 0.10, "off_target": 0.30, "uncertainty": 0.12,
    },
    "precise_edit": {    # HDR / prime: efficiency + specificity matter most
        "on_target": 0.26, "desired_outcome": 0.20, "specificity": 0.20,
        "repair": 0.10, "genomic_context": 0.08, "cell_context": 0.06,
        "model_agreement": 0.10, "off_target": 0.32, "uncertainty": 0.14,
    },
    "prime_edit": {      # prime editing (provisional): like precise, specificity-heavy
        "on_target": 0.24, "desired_outcome": 0.22, "specificity": 0.20,
        "repair": 0.10, "genomic_context": 0.08, "cell_context": 0.06,
        "model_agreement": 0.10, "off_target": 0.32, "uncertainty": 0.16,
    },
    "base_edit": {       # edit window position + bystander avoidance (provisional)
        "on_target": 0.20, "desired_outcome": 0.28, "specificity": 0.18,
        "repair": 0.06, "genomic_context": 0.10, "cell_context": 0.06,
        "model_agreement": 0.10, "off_target": 0.30, "uncertainty": 0.14,
    },
    "regulation": {      # CRISPRi/a: TSS proximity, specificity (provisional)
        "on_target": 0.18, "desired_outcome": 0.30, "specificity": 0.16,
        "repair": 0.04, "genomic_context": 0.16, "cell_context": 0.08,
        "model_agreement": 0.08, "off_target": 0.22, "uncertainty": 0.12,
    },
    "screen": {          # libraries: consistency, coverage, model agreement
        "on_target": 0.24, "desired_outcome": 0.18, "specificity": 0.16,
        "repair": 0.06, "genomic_context": 0.12, "cell_context": 0.06,
        "model_agreement": 0.18, "off_target": 0.20, "uncertainty": 0.16,
    },
}

# Risk tolerance scales the two penalty weights (off-target + uncertainty).
_RISK_SCALE = {"low": 1.6, "balanced": 1.0, "high": 0.6}


def goal_for(request: DesignRequest) -> str:
    outcome = getattr(request.desired_outcome, "value", request.desired_outcome)
    return _OUTCOME_TO_GOAL.get(str(outcome), "knockout")


def _weights(request: DesignRequest) -> Dict[str, float]:
    goal = goal_for(request)
    w = dict(WEIGHT_PROFILES.get(goal, WEIGHT_PROFILES["knockout"]))
    scale = _RISK_SCALE.get(str(getattr(request, "risk_tolerance", "balanced")), 1.0)
    w["off_target"] *= scale
    w["uncertainty"] *= scale
    return w


# --------------------------------------------------------------------------- #
# Component computation                                                         #
# --------------------------------------------------------------------------- #
def score_guide(guide: Guide, request: DesignRequest) -> EnsembleScore:
    goal = goal_for(request)
    mode = outcome_modes.get_mode(goal)
    w = _weights(request)
    provisional: List[str] = ["genomic_context_score", "model_agreement_score"]
    if mode.provisional:
        provisional.append("desired_outcome_score")

    risk = guide.off_target.risk_score
    on_target = guide.scores.on_target
    off_target_safety = 1.0 - risk
    # specificity: distinct from aggregate safety once real CFD lands; for now a
    # seed-complexity proxy combined with the heuristic risk.
    specificity = max(0.0, min(1.0, 0.5 * guide.scores.complexity + 0.5 * (1.0 - risk)))
    desired = max(0.0, min(1.0, mode.desired_outcome_score(guide)))
    repair = max(0.0, min(1.0, mode.repair_outcome_score(guide)))
    genomic_context = guide.scores.distance_to_target   # PROVISIONAL: needs exon/coding annotation
    has_cell = bool(getattr(request, "cell_type", None))
    cell_context = min(1.0, guide.context.multiplier)
    if not has_cell:
        provisional.append("cell_context_score")

    # model agreement: with one model we approximate it as the consistency of the
    # main positive signals (low spread => they "agree"). PROVISIONAL until an
    # actual ensemble of models exists.
    signals = [on_target, desired, off_target_safety, specificity]
    agreement = max(0.0, 1.0 - 2.0 * pstdev(signals))

    # uncertainty: rises with missing context, no-edit risk, structure/homopolymer
    # penalties, and the number of provisional components in play.
    unc = (
        (0.18 if not has_cell else 0.0)
        + (0.12 if not getattr(request, "delivery_method", None) else 0.0)
        + 0.30 * guide.outcome.no_edit_prob
        + 0.20 * guide.scores.secondary_structure_penalty
        + 0.10 * guide.scores.homopolymer_penalty
        + 0.05 * len(provisional)
    )
    uncertainty = max(0.0, min(1.0, unc))

    contributions = {
        "on_target": w["on_target"] * on_target,
        "desired_outcome": w["desired_outcome"] * desired,
        "specificity": w["specificity"] * specificity,
        "repair": w["repair"] * repair,
        "genomic_context": w["genomic_context"] * genomic_context,
        "cell_context": w["cell_context"] * cell_context,
        "model_agreement": w["model_agreement"] * agreement,
        "off_target": -w["off_target"] * risk,
        "uncertainty": -w["uncertainty"] * uncertainty,
    }
    pos_mass = (w["on_target"] + w["desired_outcome"] + w["specificity"] + w["repair"]
                + w["genomic_context"] + w["cell_context"] + w["model_agreement"])
    final = max(0.0, min(1.0, sum(contributions.values()) / max(pos_mass, 1e-9)))

    conf_label = "high" if uncertainty < 0.25 else "low" if uncertainty > 0.55 else "medium"

    return EnsembleScore(
        on_target_score=round(on_target, 4),
        off_target_score=round(off_target_safety, 4),
        specificity_score=round(specificity, 4),
        desired_outcome_score=round(desired, 4),
        repair_outcome_score=round(repair, 4),
        genomic_context_score=round(genomic_context, 4),
        cell_context_score=round(cell_context, 4),
        model_agreement_score=round(agreement, 4),
        uncertainty_score=round(uncertainty, 4),
        final_qguide_score=round(final, 4),
        weights={k: round(v, 4) for k, v in w.items()},
        contributions={k: round(v, 4) for k, v in contributions.items()},
        provisional=provisional,
        confidence_label=conf_label,
        goal_profile=f"{goal}_{getattr(request, 'risk_tolerance', 'balanced')}",
        badges=_badges(guide, mode, conf_label, risk, final),
    )


def _badges(guide: Guide, mode, conf: str, risk: float, final: float) -> List[str]:
    out = [f"{conf.title()} confidence"]
    if risk >= 0.4:
        out.append("High off-target concern")
    mb = mode.badge(guide, final)
    if mb:
        out.append(mb)
    return out


def score_guides(guides: List[Guide], request: DesignRequest) -> List[Guide]:
    for g in guides:
        g.ensemble = score_guide(g, request)
    return guides
