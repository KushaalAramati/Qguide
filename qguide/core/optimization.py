"""
Steps 6 & 7 -- Multi-objective scoring and quantum-inspired optimization.

Multi-objective scoring (Step 6)
--------------------------------
`compute_final_scores` folds the positive factors (on-target efficiency, knockout
probability, functional disruption, context compatibility, guide quality) and the
negative factors (off-target risk, structure penalties, poor GC balance) into a
single 0..1 utility per guide, storing the full breakdown for transparency.

Quantum-inspired optimization (Step 7)
--------------------------------------
Selecting the best N-guide *set* is framed as a QUBO:

    minimise   E(x) = - sum_i quality_i x_i           (reward good guides)
                       + sum_i risk_i x_i               (penalise risky guides)
                       + sum_ij redundancy_ij x_i x_j   (penalise redundant pairs)
                       + lambda * (sum_i x_i - N)^2      (pick exactly N)

    where x_i in {0,1} marks whether guide i is selected.

SCIENTIFIC HONESTY: the per-guide *biological* scores (quality_i, risk_i) come from
classical bioinformatics / ML heuristics upstream. The QUBO / annealer only SEARCHES
the combination space -- it does not predict biology. All weights are configurable and
seven named presets are provided. The three solver modes (classical / quantum_inspired /
quantum_hardware) all consume the SAME QUBO.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Protocol, Tuple

from qguide.app.schemas import Guide, OptimizationResult

# --------------------------------------------------------------------------- #
# Step 6 -- Multi-objective per-guide utility (unchanged; used for ranking)     #
# --------------------------------------------------------------------------- #
FINAL_WEIGHTS = {
    # positive
    "on_target": 0.25,
    "knockout": 0.25,
    "functional": 0.20,
    "context": 0.10,
    "quality": 0.10,
    # negative
    "off_target": -0.30,
    "structure": -0.10,
    "gc_balance": -0.10,
}


def compute_final_score(guide: Guide) -> Tuple[float, Dict[str, float]]:
    """Return (final_score in 0..1, contribution breakdown)."""
    gc_balance_pen = min(1.0, (abs(guide.gc_content - 0.5) / 0.5) * guide.context.gc_multiplier)
    context_compat = min(1.0, guide.context.multiplier)

    contributions = {
        "on_target": FINAL_WEIGHTS["on_target"] * guide.scores.on_target,
        "knockout": FINAL_WEIGHTS["knockout"] * guide.outcome.knockout_prob,
        "functional": FINAL_WEIGHTS["functional"] * guide.outcome.functional_disruption_score,
        "context": FINAL_WEIGHTS["context"] * context_compat,
        "quality": FINAL_WEIGHTS["quality"] * guide.scores.sequence_quality,
        "off_target": FINAL_WEIGHTS["off_target"] * guide.off_target.risk_score,
        "structure": FINAL_WEIGHTS["structure"] * guide.scores.secondary_structure_penalty,
        "gc_balance": FINAL_WEIGHTS["gc_balance"] * gc_balance_pen,
    }
    raw = sum(contributions.values())
    pos_mass = sum(w for w in FINAL_WEIGHTS.values() if w > 0)
    final = max(0.0, min(1.0, raw / pos_mass))
    return round(final, 4), {k: round(v, 4) for k, v in contributions.items()}


def _confidence(guide: Guide) -> float:
    penalty = (
        guide.off_target.risk_score
        + guide.scores.secondary_structure_penalty
        + guide.scores.homopolymer_penalty
        + guide.outcome.no_edit_prob
    ) / 4.0
    return round(max(0.05, min(0.99, 1.0 - 0.7 * penalty)), 3)


def compute_final_scores(guides: List[Guide]) -> List[Guide]:
    for g in guides:
        g.final_score, g.final_breakdown = compute_final_score(g)
        g.confidence = _confidence(g)
    guides.sort(key=lambda g: g.final_score, reverse=True)
    return guides


# --------------------------------------------------------------------------- #
# QUBO weights + presets                                                        #
# --------------------------------------------------------------------------- #
@dataclass
class QuboWeights:
    """Every QUBO term weight, fully configurable. Presets below tune these."""
    # --- quality_i sub-weights (reward) ---
    q_on_target: float = 1.0
    q_desired_outcome: float = 1.0
    q_knockout: float = 1.0
    q_specificity: float = 0.9
    q_repair: float = 0.7
    q_functional: float = 0.7
    q_model_agreement: float = 0.5
    # --- risk_i sub-weights (penalty) ---
    r_off_target: float = 1.2
    r_uncertainty: float = 0.8
    r_context_risk: float = 0.4
    # --- redundancy_ij sub-weights (pairwise penalty) ---
    d_position: float = 0.5
    d_sequence: float = 0.3
    d_cut_proximity: float = 0.2
    d_shared_offtarget: float = 0.3
    # --- top-level scales ---
    quality_scale: float = 1.0
    risk_scale: float = 1.0
    redundancy_penalty: float = 0.8
    diversity_bonus: float = 0.0      # reward selecting diverse (low-redundancy) pairs
    cardinality_penalty: float = 1.5  # lambda on (sum x - N)^2


# Seven named presets (the product brief's optimization profiles).
PRESETS: Dict[str, QuboWeights] = {
    "balanced": QuboWeights(),
    "max_knockout": QuboWeights(
        q_knockout=1.6, q_functional=1.1, q_desired_outcome=1.3,
        q_specificity=0.6, r_off_target=1.0),
    "max_specificity": QuboWeights(
        q_specificity=1.6, r_off_target=1.8, q_on_target=1.1,
        d_shared_offtarget=0.6),
    "min_uncertainty": QuboWeights(
        r_uncertainty=1.8, q_model_agreement=1.1, q_specificity=1.0,
        r_off_target=1.1),
    "broad_coverage": QuboWeights(
        redundancy_penalty=1.6, diversity_bonus=0.5, d_position=0.7,
        d_cut_proximity=0.4),
    "therapeutic_safety": QuboWeights(
        r_off_target=2.0, r_uncertainty=1.4, q_specificity=1.4,
        d_shared_offtarget=0.6, cardinality_penalty=1.8),
    "screening_library": QuboWeights(
        q_model_agreement=1.2, redundancy_penalty=1.3, diversity_bonus=0.4,
        q_on_target=1.2, r_uncertainty=1.0),
}

PRESET_INFO: Dict[str, str] = {
    "balanced": "Even weighting across activity, specificity, outcome and diversity.",
    "max_knockout": "Maximise predicted knockout / functional disruption probability.",
    "max_specificity": "Prioritise specificity and heavily penalise off-target risk.",
    "min_uncertainty": "Prefer high-confidence guides; penalise uncertainty, reward model agreement.",
    "broad_coverage": "Spread guides across the target region (reward diversity, penalise redundancy).",
    "therapeutic_safety": "Conservative safety-first profile: strong off-target + uncertainty penalties.",
    "screening_library": "Screening libraries: consistency, model agreement and broad coverage.",
}

DEFAULT_WEIGHTS = PRESETS["balanced"]


def get_weights(preset: str) -> QuboWeights:
    return PRESETS.get(preset, DEFAULT_WEIGHTS)


# --------------------------------------------------------------------------- #
# Per-guide quality_i / risk_i (from the already-computed biological scores)     #
# --------------------------------------------------------------------------- #
def quality_i(g: Guide, w: QuboWeights) -> float:
    """Reward term: weighted blend of the positive biological signals (0..1)."""
    e = g.ensemble
    on_t = e.on_target_score if e else g.scores.on_target
    desired = e.desired_outcome_score if e else 0.0
    spec = e.specificity_score if e else max(0.0, 1.0 - g.off_target.risk_score)
    repair = e.repair_outcome_score if e else 0.0
    agree = e.model_agreement_score if e else 0.0
    terms = (
        w.q_on_target * on_t
        + w.q_desired_outcome * desired
        + w.q_knockout * g.outcome.knockout_prob
        + w.q_specificity * spec
        + w.q_repair * repair
        + w.q_functional * g.outcome.functional_disruption_score
        + w.q_model_agreement * agree
    )
    mass = (w.q_on_target + w.q_desired_outcome + w.q_knockout + w.q_specificity
            + w.q_repair + w.q_functional + w.q_model_agreement)
    return max(0.0, min(1.0, terms / max(mass, 1e-9)))


def risk_i(g: Guide, w: QuboWeights) -> float:
    """Penalty term: weighted blend of off-target risk, uncertainty, risky context (0..1)."""
    e = g.ensemble
    off = g.off_target.risk_score
    unc = e.uncertainty_score if e else 0.0
    ctx_risk = max(0.0, 1.0 - min(1.0, g.context.multiplier))
    terms = w.r_off_target * off + w.r_uncertainty * unc + w.r_context_risk * ctx_risk
    mass = w.r_off_target + w.r_uncertainty + w.r_context_risk
    return max(0.0, min(1.0, terms / max(mass, 1e-9)))


# --------------------------------------------------------------------------- #
# Step 7 -- QUBO construction                                                   #
# --------------------------------------------------------------------------- #
@dataclass
class QUBO:
    """Q matrix as a dict of {(i, j): coefficient}, i <= j."""
    linear_quadratic: Dict[Tuple[int, int], float]
    guide_ids: List[str]
    set_size: int

    def energy(self, x: List[int]) -> float:
        e = 0.0
        for (i, j), q in self.linear_quadratic.items():
            e += q * x[i] * x[j]
        return e

    def to_qubo_dict(self) -> Dict[Tuple[str, str], float]:
        """Export as the labelled {(var_i, var_j): bias} mapping quantum / annealing
        SDKs consume directly (dimod / Qiskit / Braket). Dependency-free seam."""
        ids = self.guide_ids
        return {(ids[i], ids[j]): coeff
                for (i, j), coeff in self.linear_quadratic.items()}


def _similarity(a: Guide, b: Guide) -> float:
    """Base redundancy proxy: positional overlap + spacer Hamming + cut proximity."""
    overlap = max(0, min(a.end, b.end) - max(a.position, b.position))
    span = max(a.end - a.position, 1)
    pos_sim = overlap / span
    seq_sim = 0.0
    if len(a.sequence) == len(b.sequence) and a.sequence:
        same = sum(1 for x, y in zip(a.sequence, b.sequence) if x == y)
        seq_sim = same / len(a.sequence)
    near = 1.0 if abs(a.cut_site - b.cut_site) < 10 else 0.0
    return min(1.0, 0.5 * pos_sim + 0.3 * seq_sim + 0.2 * near)


def _shared_offtarget(a: Guide, b: Guide) -> float:
    """Jaccard overlap of the two guides' predicted off-target annotation classes.

    Heuristic proxy for 'shared failure modes' (real shared-locus overlap needs a
    genome index). Uses the annotation labels on each guide's predicted hits.
    """
    aa = {h.annotation for h in getattr(a.off_target, "hits", []) if getattr(h, "annotation", None)}
    bb = {h.annotation for h in getattr(b.off_target, "hits", []) if getattr(h, "annotation", None)}
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def redundancy_ij(a: Guide, b: Guide, w: QuboWeights) -> float:
    """Full pairwise redundancy: position, sequence, cut proximity, shared off-targets."""
    overlap = max(0, min(a.end, b.end) - max(a.position, b.position))
    span = max(a.end - a.position, 1)
    pos_sim = overlap / span
    seq_sim = 0.0
    if len(a.sequence) == len(b.sequence) and a.sequence:
        seq_sim = sum(1 for x, y in zip(a.sequence, b.sequence) if x == y) / len(a.sequence)
    near = 1.0 if abs(a.cut_site - b.cut_site) < 10 else 0.0
    shared = _shared_offtarget(a, b)
    val = (w.d_position * pos_sim + w.d_sequence * seq_sim
           + w.d_cut_proximity * near + w.d_shared_offtarget * shared)
    mass = w.d_position + w.d_sequence + w.d_cut_proximity + w.d_shared_offtarget
    return max(0.0, min(1.0, val / max(mass, 1e-9)))


def build_qubo(
    guides: List[Guide],
    set_size: int,
    weights: Optional[QuboWeights] = None,
) -> QUBO:
    """Construct the QUBO whose minimum-energy bitstring is the best guide set.

    Diagonal terms: -quality_i (reward) + risk_i (penalty) + cardinality diagonal.
    Off-diagonal terms: redundancy_ij (penalty) - diversity reward + cardinality.
    """
    w = weights or DEFAULT_WEIGHTS
    n = len(guides)
    Q: Dict[Tuple[int, int], float] = {}
    P = w.cardinality_penalty
    k = set_size
    for i in range(n):
        qi = quality_i(guides[i], w)
        ri = risk_i(guides[i], w)
        # reward (negative -> lowers energy) + risk penalty + cardinality diagonal
        Q[(i, i)] = (-w.quality_scale * qi) + (w.risk_scale * ri) + P * (1 - 2 * k)
        for j in range(i + 1, n):
            red = redundancy_ij(guides[i], guides[j], w)
            pair = w.redundancy_penalty * red - w.diversity_bonus * (1.0 - red)
            Q[(i, j)] = pair + 2 * P

    return QUBO(linear_quadratic=Q, guide_ids=[g.guide_id for g in guides], set_size=set_size)


# --------------------------------------------------------------------------- #
# Optimizer interface + classical (simulated annealing) implementation         #
# --------------------------------------------------------------------------- #
class Optimizer(Protocol):
    method: str
    def solve(self, qubo: QUBO) -> Tuple[List[int], float, int]: ...


class SimulatedAnnealingOptimizer:
    """Deterministic simulated annealing over the QUBO bitstring."""

    method = "simulated_annealing_v1"

    def __init__(self, steps: int = 4000, t_start: float = 2.0, t_end: float = 0.01, seed: int = 12345):
        self.steps = steps
        self.t_start = t_start
        self.t_end = t_end
        self.seed = seed

    def _rng(self):
        state = self.seed & 0x7FFFFFFF
        while True:
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            yield state / 0x7FFFFFFF

    def solve(self, qubo: QUBO) -> Tuple[List[int], float, int]:
        n = len(qubo.guide_ids)
        if n == 0:
            return [], 0.0, 0
        rng = self._rng()

        diag = sorted(range(n), key=lambda i: qubo.linear_quadratic.get((i, i), 0.0))
        x = [0] * n
        for i in diag[:qubo.set_size]:
            x[i] = 1

        best = x[:]
        best_e = qubo.energy(x)
        cur_e = best_e

        for step in range(self.steps):
            frac = step / max(1, self.steps - 1)
            temp = self.t_start * (self.t_end / self.t_start) ** frac
            flip = int(next(rng) * n) % n
            x[flip] ^= 1
            new_e = qubo.energy(x)
            delta = new_e - cur_e
            if delta < 0 or next(rng) < math.exp(-delta / max(temp, 1e-9)):
                cur_e = new_e
                if new_e < best_e:
                    best_e, best = new_e, x[:]
            else:
                x[flip] ^= 1  # revert
        return best, best_e, self.steps


class DimodQUBOOptimizer:
    """Quantum-annealing-style optimizer via D-Wave's `dimod` data model."""

    method = "dwave_dimod_neal_v1"

    def __init__(self, num_reads: int = 200, use_hardware: bool = False, token: Optional[str] = None):
        self.num_reads = num_reads
        self.use_hardware = use_hardware
        self.token = token

    def solve(self, qubo: QUBO) -> Tuple[List[int], float, int]:
        import dimod  # local import: optional dependency

        n = len(qubo.guide_ids)
        if n == 0:
            return [], 0.0, 0

        bqm = dimod.BinaryQuadraticModel.from_qubo(qubo.to_qubo_dict())
        if self.use_hardware:  # pragma: no cover - needs a Leap token + network
            from dwave.system import DWaveSampler, EmbeddingComposite
            sampler = EmbeddingComposite(DWaveSampler(token=self.token))
            sampleset = sampler.sample(bqm, num_reads=self.num_reads)
        else:
            from dwave.samplers import SimulatedAnnealingSampler
            sampler = SimulatedAnnealingSampler()
            sampleset = sampler.sample(bqm, num_reads=self.num_reads)

        best = sampleset.first.sample
        x = [int(best[gid]) for gid in qubo.guide_ids]
        return x, float(sampleset.first.energy), self.num_reads


def quantum_available() -> bool:
    try:
        import dimod  # noqa: F401
        from dwave.samplers import SimulatedAnnealingSampler  # noqa: F401
        return True
    except Exception:
        return False


def available_backends() -> Dict[str, str]:
    backends = {"sa": "Simulated Annealing (classical)"}
    if quantum_available():
        backends["dwave"] = "D-Wave (dimod / quantum annealing)"
    return backends


def make_optimizer(backend: str = "sa") -> "Optimizer":
    if backend == "dwave" and quantum_available():
        return DimodQUBOOptimizer()
    return SimulatedAnnealingOptimizer()


OPTIMIZER_MODES = {
    "classical": "Classical (simulated annealing)",
    "quantum_inspired": "Quantum-inspired (QUBO via D-Wave Ocean, classical sampler)",
    "quantum_hardware": "Quantum hardware (D-Wave QPU — experimental, needs Leap token)",
}


def make_optimizer_for_mode(mode: str, token: Optional[str] = None) -> Tuple["Optimizer", str, List[str]]:
    notes: List[str] = []
    if mode == "quantum_hardware":
        if quantum_available() and token:
            return DimodQUBOOptimizer(use_hardware=True, token=token), "quantum_hardware", notes
        notes.append("Quantum hardware requested but no D-Wave Leap token/backend is "
                     "configured — fell back to quantum-inspired/classical.")
        mode = "quantum_inspired"
    if mode == "quantum_inspired":
        if quantum_available():
            return DimodQUBOOptimizer(), "quantum_inspired", notes
        notes.append("Quantum-inspired backend (dimod) not installed — using classical.")
        mode = "classical"
    return SimulatedAnnealingOptimizer(), "classical", notes


DEFAULT_OPTIMIZER: Optimizer = SimulatedAnnealingOptimizer()


def _set_metrics(selected: List[str], by_id: Dict[str, Guide], w: QuboWeights) -> Dict[str, float]:
    """Aggregate metrics for the chosen set (all 0..1, higher diversity = more spread)."""
    if not selected:
        return {"expected_outcome": 0.0, "off_target_burden": 0.0,
                "diversity": 0.0, "uncertainty": 0.0}
    gs = [by_id[s] for s in selected]
    exp = sum(quality_i(g, w) for g in gs) / len(gs)
    burden = sum(g.off_target.risk_score for g in gs) / len(gs)
    unc = sum((g.ensemble.uncertainty_score if g.ensemble else 0.0) for g in gs) / len(gs)
    if len(gs) > 1:
        pairs = [redundancy_ij(gs[i], gs[j], w)
                 for i in range(len(gs)) for j in range(i + 1, len(gs))]
        diversity = 1.0 - (sum(pairs) / len(pairs))
    else:
        diversity = 1.0
    return {"expected_outcome": round(exp, 4), "off_target_burden": round(burden, 4),
            "diversity": round(max(0.0, diversity), 4), "uncertainty": round(unc, 4)}


def optimize_guide_set(
    guides: List[Guide],
    set_size: int = 3,
    optimizer: Optimizer = DEFAULT_OPTIMIZER,
    mode: str = "classical",
    extra_notes: Optional[List[str]] = None,
    weights: Optional[QuboWeights] = None,
    preset: str = "balanced",
) -> OptimizationResult:
    """Select the best N-guide set and explain the choice/rejections, with a
    Top-N-by-individual-score vs optimized-set comparison and aggregate set metrics."""
    w = weights or get_weights(preset)
    if not guides:
        return OptimizationResult(
            selected_guide_ids=[], objective_value=0.0,
            method=optimizer.method, mode=mode, iterations=0, preset=preset,
        )

    set_size = max(1, min(set_size, len(guides)))
    qubo = build_qubo(guides, set_size, w)
    x, energy, iters = optimizer.solve(qubo)

    selected = [qubo.guide_ids[i] for i, bit in enumerate(x) if bit]
    by_id = {g.guide_id: g for g in guides}
    selected.sort(key=lambda gid: by_id[gid].final_score, reverse=True)

    rejected = _explain_rejections(guides, selected, set_size)
    tradeoffs = _tradeoffs(guides, selected)

    top_n = [g.guide_id for g in sorted(guides, key=lambda g: g.final_score, reverse=True)[:set_size]]
    mean = lambda ids, f: (sum(f(by_id[i]) for i in ids) / len(ids)) if ids else 0.0
    out_delta = round(mean(selected, lambda g: g.final_score) - mean(top_n, lambda g: g.final_score), 4)
    off_delta = round(mean(selected, lambda g: g.off_target.risk_score)
                      - mean(top_n, lambda g: g.off_target.risk_score), 4)
    if set(selected) == set(top_n):
        note = "The optimized set matches the top-N by individual score (no redundancy to resolve)."
    else:
        note = (f"The optimized set differs from the naive top-N: mean off-target risk "
                f"{'lower' if off_delta < 0 else 'higher'} by {abs(off_delta):.2f} and mean "
                f"score {'lower' if out_delta < 0 else 'higher'} by {abs(out_delta):.2f} — "
                "trading a little individual score for lower redundancy / combined risk.")

    metrics = _set_metrics(selected, by_id, w)
    focus = list(dict.fromkeys(selected + top_n))
    quality_by = {gid: round(quality_i(by_id[gid], w), 4) for gid in focus}
    risk_by = {gid: round(risk_i(by_id[gid], w), 4) for gid in focus}

    return OptimizationResult(
        selected_guide_ids=selected,
        objective_value=round(-energy, 4),
        method=optimizer.method,
        mode=mode,
        iterations=iters,
        rejected_explanations=rejected,
        tradeoffs=tradeoffs + (extra_notes or []),
        top_n_individual=top_n,
        expected_outcome_delta=out_delta,
        off_target_delta=off_delta,
        comparison_note=note,
        preset=preset,
        weights={k: round(v, 4) for k, v in asdict(w).items()},
        set_expected_outcome=metrics["expected_outcome"],
        set_off_target_burden=metrics["off_target_burden"],
        set_diversity=metrics["diversity"],
        set_uncertainty=metrics["uncertainty"],
        quality_by_guide=quality_by,
        risk_by_guide=risk_by,
    )


def best_single_guide(guides: List[Guide]) -> Optional[str]:
    if not guides:
        return None
    return max(guides, key=lambda g: g.final_score).guide_id


def _explain_rejections(guides, selected, set_size) -> Dict[str, str]:
    by_id = {g.guide_id: g for g in guides}
    sel_set = set(selected)
    out: Dict[str, str] = {}
    near = [g for g in guides if g.guide_id not in sel_set][:5]
    for g in near:
        reasons = []
        for sid in selected:
            if _similarity(g, by_id[sid]) > 0.5:
                reasons.append(f"redundant with {sid} (overlapping/similar)")
                break
        if g.off_target.risk_score > 0.4:
            reasons.append(f"elevated off-target risk ({g.off_target.risk_score:.2f})")
        if g.final_score < (min((by_id[s].final_score for s in selected), default=0)):
            reasons.append(f"lower final score ({g.final_score:.2f})")
        if not reasons:
            reasons.append("did not improve the set objective beyond the chosen guides")
        out[g.guide_id] = "; ".join(reasons)
    return out


def _tradeoffs(guides, selected) -> List[str]:
    by_id = {g.guide_id: g for g in guides}
    msgs = []
    if selected:
        avg_off = sum(by_id[s].off_target.risk_score for s in selected) / len(selected)
        avg_ko = sum(by_id[s].outcome.knockout_prob for s in selected) / len(selected)
        msgs.append(f"Set mean knockout probability {avg_ko:.0%}, mean off-target risk {avg_off:.0%}.")
        cuts = sorted(by_id[s].cut_site for s in selected)
        if len(cuts) > 1:
            spread = cuts[-1] - cuts[0]
            msgs.append(f"Cut sites span {spread} bp -- chosen for target coverage and low redundancy.")
    return msgs
