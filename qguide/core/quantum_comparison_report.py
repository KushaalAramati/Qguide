"""
Classical Top-N vs Quantum-Inspired Optimized Set — comparison report
(formula-upgrade brief, Part 5).

Answers, honestly and with numbers, the question "does the quantum-inspired optimizer
actually help, or is it just re-ranking?" It builds ONE QUBO from the upgraded weights
and evaluates three selection strategies on identical inputs:

  1. **Top-N individual**  — the naive baseline: the N guides with the best individual
     score, ignoring how they combine.
  2. **Classical-optimized** — simulated annealing over the QUBO (set-aware).
  3. **Quantum-inspired**   — the same QUBO handed to the D-Wave `dimod` sampler when
     installed; otherwise it HONESTLY falls back to classical and the report says so.

For each set it reports selected guides, per-guide scores, combined outcome, off-target
burden + severity, diversity, redundancy, uncertainty and the QUBO energy, then issues a
verdict on whether quantum-inspired optimization gave a MEANINGFUL improvement.

Honesty rule enforced in the verdict text: classical and quantum-inspired solve the SAME
QUBO. At experiment scale (tens of candidates) that QUBO is easy, so the two usually
converge to the same set — the quantum layer is a search strategy, not better biology.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from qguide.app.schemas import DesignRequest, Guide
from qguide.core import optimization as opt


def _set_report(ids: List[str], by_id: Dict[str, Guide], w, qubo) -> Dict[str, object]:
    gs = [by_id[i] for i in ids if i in by_id]
    if not gs:
        return {"selected": [], "guides": []}
    n = len(gs)
    mean = lambda f: sum(f(g) for g in gs) / n

    def unc(g: Guide) -> float:
        if g.ensemble and g.ensemble.uncertainty_score is not None:
            return g.ensemble.uncertainty_score
        return g.precision.uncertainty if g.precision else 0.0

    def severity(g: Guide) -> float:
        s = getattr(g.off_target, "severity", None)
        return s.severity_score if s else 0.0

    pairs_red = [opt.redundancy_ij(gs[i], gs[j], w)
                 for i in range(n) for j in range(i + 1, n)]
    pairs_syn = [opt.synergy_ij(gs[i], gs[j], w)
                 for i in range(n) for j in range(i + 1, n)]
    redundancy = sum(pairs_red) / len(pairs_red) if pairs_red else 0.0
    synergy = sum(pairs_syn) / len(pairs_syn) if pairs_syn else 1.0

    # QUBO energy for this exact selection (lower is better).
    idx = {gid: k for k, gid in enumerate(qubo.guide_ids)}
    x = [0] * len(qubo.guide_ids)
    for i in ids:
        if i in idx:
            x[idx[i]] = 1
    energy = qubo.energy(x)

    return {
        "selected": ids,
        "guides": [{
            "guide_id": g.guide_id,
            "precision_score": round(g.precision.score, 4) if g.precision else None,
            "legacy_final_score": round(g.final_score, 4),
            "quality_i": round(opt.quality_i(g, w), 4),
            "risk_i": round(opt.risk_i(g, w), 4),
            "off_target_risk": round(g.off_target.risk_score, 4),
            "off_target_severity": round(severity(g), 4),
            "uncertainty": round(unc(g), 4),
            "knockout_prob": round(g.outcome.knockout_prob, 4),
        } for g in gs],
        "combined_outcome": round(mean(lambda g: opt.quality_i(g, w)), 4),
        "mean_precision": round(mean(lambda g: g.precision.score if g.precision else 0.0), 4),
        "off_target_burden": round(mean(lambda g: g.off_target.risk_score), 4),
        "off_target_severity_burden": round(mean(severity), 4),
        "diversity": round(max(0.0, 1.0 - redundancy), 4),
        "redundancy": round(redundancy, 4),
        "synergy": round(synergy, 4),
        "uncertainty": round(mean(unc), 4),
        "objective_energy": round(energy, 4),
    }


def _explain_set(label: str, rep: Dict[str, object]) -> str:
    if not rep.get("selected"):
        return f"{label}: no guides selected."
    return (f"{label} selected {', '.join(rep['selected'])}: combined outcome "
            f"{rep['combined_outcome']:.2f}, off-target burden {rep['off_target_burden']:.2f} "
            f"(severity {rep['off_target_severity_burden']:.2f}), diversity {rep['diversity']:.2f}, "
            f"mean uncertainty {rep['uncertainty']:.2f}.")


def compare_selection_strategies(
    guides: List[Guide],
    request: Optional[DesignRequest] = None,
    set_size: int = 3,
    preset: str = "balanced",
    weights: Optional[opt.QuboWeights] = None,
) -> Dict[str, object]:
    """Build one QUBO and compare Top-N / classical / quantum-inspired selections."""
    if not guides:
        return {"error": "no guides", "sets": {}}

    w = weights or opt.get_weights(preset)
    set_size = max(1, min(set_size, len(guides)))
    by_id = {g.guide_id: g for g in guides}
    qubo = opt.build_qubo(guides, set_size, w)

    # 1) Top-N by individual (legacy) score.
    top_n = [g.guide_id for g in sorted(guides, key=lambda g: g.final_score, reverse=True)[:set_size]]

    # 2) Classical (built-in simulated annealing).
    sa = opt.SimulatedAnnealingOptimizer()
    xc, ec, _ = sa.solve(qubo)
    classical = [qubo.guide_ids[i] for i, b in enumerate(xc) if b]

    # 3) Quantum-inspired (dimod sampler) with an HONEST fallback to classical.
    q_optimizer, resolved_mode, notes = opt.make_optimizer_for_mode("quantum_inspired")
    xq, eq, q_iters = q_optimizer.solve(qubo)
    quantum = [qubo.guide_ids[i] for i, b in enumerate(xq) if b]
    quantum_backend_available = opt.quantum_available()

    reports = {
        "top_n_individual": _set_report(top_n, by_id, w, qubo),
        "classical_optimized": _set_report(classical, by_id, w, qubo),
        "quantum_inspired_optimized": _set_report(quantum, by_id, w, qubo),
    }

    verdict = _verdict(reports, resolved_mode, quantum_backend_available, notes)

    return {
        "preset": preset,
        "set_size": set_size,
        "n_candidates": len(guides),
        "solver_method": {"classical": sa.method,
                          "quantum_inspired": getattr(q_optimizer, "method", "unknown"),
                          "quantum_mode_resolved": resolved_mode},
        "quantum_backend_installed": quantum_backend_available,
        "notes": notes,
        "sets": reports,
        "explanations": {k: _explain_set(k.replace("_", " ").title(), v)
                         for k, v in reports.items()},
        "verdict": verdict,
    }


def _verdict(reports, resolved_mode, backend_available, notes) -> Dict[str, object]:
    topn = reports["top_n_individual"]
    classical = reports["classical_optimized"]
    quantum = reports["quantum_inspired_optimized"]

    same_cq = set(classical["selected"]) == set(quantum["selected"])
    opt_vs_topn_off = round(classical["off_target_burden"] - topn["off_target_burden"], 4)
    opt_vs_topn_div = round(classical["diversity"] - topn["diversity"], 4)
    energy_gap = round(quantum["objective_energy"] - classical["objective_energy"], 6)

    # Did SET-optimization beat the naive top-N at all?
    optimization_helps = (set(classical["selected"]) != set(topn["selected"])) and (
        opt_vs_topn_off < -1e-9 or opt_vs_topn_div > 1e-9)

    if not backend_available or resolved_mode != "quantum_inspired":
        quantum_meaningful = False
        q_text = ("The quantum-inspired backend (D-Wave `dimod`) is NOT installed, so the "
                  "'quantum-inspired' run fell back to the classical solver — the two "
                  "columns are identical by construction. Install `dimod` + `dwave-samplers` "
                  "to exercise the real quantum-inspired sampler on the same QUBO.")
    elif same_cq and abs(energy_gap) < 1e-6:
        quantum_meaningful = False
        q_text = ("Classical and quantum-inspired solve the SAME QUBO and converged to the "
                  "SAME set at this scale — expected, because a pick-N-of-tens QUBO is easy. "
                  "The quantum-inspired layer is a search strategy here, not better biology.")
    elif energy_gap < -1e-6:
        quantum_meaningful = True
        q_text = (f"Quantum-inspired found a LOWER-energy set (Δenergy {energy_gap:+.4f}) than "
                  "classical annealing on the same QUBO — a genuine (if small-scale) search win.")
    else:
        quantum_meaningful = False
        q_text = (f"Quantum-inspired did not beat classical (Δenergy {energy_gap:+.4f} ≥ 0). "
                  "Classical annealing already reached the optimum for this QUBO.")

    if optimization_helps:
        opt_text = (f"Set-optimization beat the naive Top-N: off-target burden "
                    f"{'down' if opt_vs_topn_off < 0 else 'up'} by {abs(opt_vs_topn_off):.2f} "
                    f"and diversity {'up' if opt_vs_topn_div > 0 else 'down'} by "
                    f"{abs(opt_vs_topn_div):.2f} — it traded a little individual score for a "
                    "better-combined set.")
    else:
        opt_text = ("Set-optimization returned the same guides as the naive Top-N here (no "
                    "redundancy or shared failure mode to resolve in this candidate pool).")

    return {
        "set_optimization_beats_topn": optimization_helps,
        "quantum_inspired_meaningful_improvement": quantum_meaningful,
        "classical_equals_quantum": same_cq,
        "energy_gap_quantum_minus_classical": energy_gap,
        "topn_vs_optimized_offtarget_delta": opt_vs_topn_off,
        "topn_vs_optimized_diversity_delta": opt_vs_topn_div,
        "text": opt_text + " " + q_text,
    }
