"""
Pipeline orchestrator.

Wires the independent core modules into the Step 1 -> Step 8 flow and returns a
fully-populated `DesignResponse`. This is the *only* place that knows the module
ordering; each module remains independently testable and replaceable.

    generate -> score -> off-target -> outcome -> context
             -> multi-objective final score -> optimize -> explain
"""
from __future__ import annotations

import copy
from typing import Dict, List, Optional

from qguide.app.schemas import (
    DesignRequest,
    DesignResponse,
    Guide,
)
from qguide.core import (
    context_adjustment,
    ensemble,
    explainability,
    guide_generator,
    off_target,
    optimization,
    outcome_prediction,
    scoring,
)


def run_design(request: DesignRequest) -> DesignResponse:
    outcome_value = (
        request.desired_outcome
        if isinstance(request.desired_outcome, str)
        else request.desired_outcome.value
    )

    # Step 1 -- generation
    guides: List[Guide] = guide_generator.generate_guides(
        sequence=request.sequence,
        cas_enzyme=request.cas_enzyme,
        pam=request.pam,
        guide_length=request.guide_length,
        target_region=request.target_region,
        max_guides=request.max_guides,
    )

    warnings: List[str] = []
    if not guides:
        return DesignResponse(
            request=request, guides=[], best_single_guide_id=None,
            optimized_set=optimization.optimize_guide_set([], request.set_size),
            warnings=["No PAM sites found for the given sequence / enzyme."],
            summary="No candidate guides were found.",
        )

    # Steps 2-5. Context (Step 5) is computed before outcome prediction (Step 4)
    # so its efficiency factor can modulate predicted editing -- a neuron / cold /
    # low-expression context lowers knockout probability, not just the ranking.
    scoring.score_guides(guides)
    off_target.analyze_off_targets(guides)
    context_adjustment.apply_context_to_guides(guides, request)
    efficiency = guides[0].context.multiplier if guides else 1.0
    outcome_prediction.predict_outcomes(
        guides, desired_outcome=outcome_value, efficiency=efficiency
    )

    # Step 6 -- multi-objective final score (also sorts best-first)
    optimization.compute_final_scores(guides)

    # Step 6b -- ensemble scoring layer: the spec's named components + goal-weighted
    # final_qguide_score (additive; the legacy final_score still drives ordering for
    # now). Switching the primary ranking to ensemble.final_qguide_score is a one-line
    # change once the UI consumes it.
    ensemble.score_guides(guides, request)

    # Step 7 -- optimization. Three honest modes (classical / quantum_inspired /
    # quantum_hardware); all solve the SAME QUBO. Legacy optimizer_backend still
    # maps to a mode for backward compatibility.
    req_mode = getattr(request, "optimizer_mode", None)
    if not req_mode:
        req_mode = "quantum_inspired" if getattr(request, "optimizer_backend", "sa") == "dwave" else "classical"
    optimizer, resolved_mode, mode_notes = optimization.make_optimizer_for_mode(req_mode)
    opt_result = optimization.optimize_guide_set(
        guides, set_size=request.set_size, optimizer=optimizer,
        mode=resolved_mode, extra_notes=mode_notes)
    best_single = optimization.best_single_guide(guides)

    # Step 10 -- explanations
    explainability.explain_all(guides, selected_ids=opt_result.selected_guide_ids)
    summary = explainability.summarize_run(request, guides, opt_result.selected_guide_ids)

    return DesignResponse(
        request=request,
        guides=guides,
        best_single_guide_id=best_single,
        optimized_set=opt_result,
        warnings=warnings,
        summary=summary,
    )


# --------------------------------------------------------------------------- #
# Step 9E -- context sensitivity analysis                                       #
# --------------------------------------------------------------------------- #
def context_sensitivity(
    base_request: DesignRequest,
    guide_id: str,
    scenarios: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    """Re-run the pipeline under alternative contexts and track ONE guide.

    `scenarios` is a list of dicts of request-field overrides, e.g.
    [{"label": "neuron", "cell_type": "neuron"},
     {"label": "stem cell", "cell_type": "stem_cell"}].
    Returns per-scenario {label, final_score, rank, knockout_prob}.
    """
    results = []
    for sc in scenarios:
        label = str(sc.get("label", "scenario"))
        overrides = {k: v for k, v in sc.items() if k != "label"}
        if hasattr(base_request, "model_copy"):
            req = base_request.model_copy(update=overrides)
        else:
            req = copy.deepcopy(base_request)
            for k, v in overrides.items():
                setattr(req, k, v)
        resp = run_design(req)
        match = next((g for g in resp.guides if g.guide_id == guide_id), None)
        if match is None:
            # guide_id is positional; if generation is identical it should exist
            results.append({"label": label, "final_score": 0.0, "rank": None,
                            "knockout_prob": 0.0})
            continue
        rank = next((i + 1 for i, g in enumerate(resp.guides)
                     if g.guide_id == guide_id), None)
        results.append({
            "label": label,
            "final_score": match.final_score,
            "rank": rank,
            "knockout_prob": match.outcome.knockout_prob,
        })
    return results


# --------------------------------------------------------------------------- #
# Step 9H -- Experiment simulation                                              #
# --------------------------------------------------------------------------- #
# Built-in sweeps: each maps an axis name to a list of (label, field-overrides).
SIMULATION_AXES: Dict[str, List[Dict[str, object]]] = {
    "cas_enzyme": [
        {"label": "SpCas9", "cas_enzyme": "SpCas9"},
        {"label": "SpCas9-HF1", "cas_enzyme": "SpCas9-HF1"},
        {"label": "eSpCas9", "cas_enzyme": "eSpCas9"},
        {"label": "SaCas9", "cas_enzyme": "SaCas9"},
        {"label": "Cas12a", "cas_enzyme": "Cas12a"},
    ],
    "cell_type": [
        {"label": "stem cell", "cell_type": "stem_cell"},
        {"label": "neuron", "cell_type": "neuron"},
        {"label": "HEK293", "cell_type": "hek293"},
        {"label": "primary T", "cell_type": "primary_t"},
        {"label": "cancer line", "cell_type": "cancer_line"},
    ],
    "delivery_method": [
        {"label": "RNP", "delivery_method": "rnp"},
        {"label": "plasmid", "delivery_method": "plasmid"},
        {"label": "lentivirus", "delivery_method": "lentivirus"},
        {"label": "AAV", "delivery_method": "aav"},
        {"label": "electroporation", "delivery_method": "electroporation"},
    ],
    "temperature": [
        {"label": "30 C", "temperature": 30.0},
        {"label": "34 C", "temperature": 34.0},
        {"label": "37 C", "temperature": 37.0},
        {"label": "39 C", "temperature": 39.0},
    ],
    "desired_outcome": [
        {"label": "knockout", "desired_outcome": "knockout"},
        {"label": "gene disruption", "desired_outcome": "gene_disruption"},
        {"label": "exon targeting", "desired_outcome": "exon_targeting"},
        {"label": "deletion", "desired_outcome": "deletion"},
    ],
}


def _apply_overrides(base_request: DesignRequest, overrides: Dict[str, object]) -> DesignRequest:
    if hasattr(base_request, "model_copy"):
        return base_request.model_copy(update=overrides)
    req = copy.deepcopy(base_request)
    for k, v in overrides.items():
        setattr(req, k, v)
    return req


def simulate_experiments(
    base_request: DesignRequest,
    scenarios: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    """Run the full design pipeline under each scenario and summarise the outcome.

    `scenarios` is a list of dicts: a "label" plus any `DesignRequest` field
    overrides (cas_enzyme, cell_type, delivery_method, temperature,
    desired_outcome, set_size, ...). Returns one comparative summary per scenario
    -- the experiment-level analogue of `context_sensitivity` (which tracks a
    single guide). This powers the Experiment Simulation Panel (Step 9H).
    """
    results: List[Dict[str, object]] = []
    for sc in scenarios:
        label = str(sc.get("label", "scenario"))
        overrides = {k: v for k, v in sc.items() if k != "label"}
        req = _apply_overrides(base_request, overrides)
        resp = run_design(req)

        if not resp.guides:
            results.append({
                "label": label, "n_guides": 0, "best_guide": None,
                "best_final": 0.0, "best_knockout": 0.0, "best_off_target": 0.0,
                "best_functional": 0.0, "set_ids": [], "set_mean_knockout": 0.0,
                "objective": 0.0, **overrides,
            })
            continue

        best = resp.guides[0]
        set_ids = resp.optimized_set.selected_guide_ids
        by_id = {g.guide_id: g for g in resp.guides}
        set_ko = [by_id[s].outcome.knockout_prob for s in set_ids if s in by_id]
        results.append({
            "label": label,
            "n_guides": len(resp.guides),
            "best_guide": best.guide_id,
            "best_final": round(best.final_score, 4),
            "best_knockout": round(best.outcome.knockout_prob, 4),
            "best_off_target": round(best.off_target.risk_score, 4),
            "best_functional": round(best.outcome.functional_disruption_score, 4),
            "set_ids": set_ids,
            "set_mean_knockout": round(sum(set_ko) / len(set_ko), 4) if set_ko else 0.0,
            "objective": resp.optimized_set.objective_value,
            **overrides,
        })
    return results


def simulate_axis(base_request: DesignRequest, axis: str) -> List[Dict[str, object]]:
    """Convenience wrapper: sweep a single named axis from `SIMULATION_AXES`."""
    if axis not in SIMULATION_AXES:
        raise ValueError(f"Unknown simulation axis '{axis}'. "
                         f"Choose from {list(SIMULATION_AXES)}.")
    return simulate_experiments(base_request, SIMULATION_AXES[axis])
