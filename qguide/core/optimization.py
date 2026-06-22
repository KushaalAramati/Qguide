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

    minimise   x^T Q x
    where x_i in {0,1} marks whether guide i is selected.

The Q matrix encodes:
  * linear terms  -> reward each guide's utility (negative on the diagonal)
  * quadratic terms -> penalise redundancy: overlapping / nearby / sequence-similar
                       guide pairs, and over/under-selection vs the target set size.

V1 solves the QUBO with **simulated annealing** (a classical stand-in for quantum
annealing). The `Optimizer` interface means a `DWaveOptimizer`, `QAOAOptimizer`
(Qiskit), or `BraketOptimizer` can be dropped in later -- they consume the same Q
matrix and return the same selection.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

from qguide.app.schemas import Guide, OptimizationResult

# --------------------------------------------------------------------------- #
# Step 6 -- Multi-objective per-guide utility                                   #
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
    # GC imbalance penalty, tuned by the organism's GC tolerance (gc_multiplier<1
    # => more tolerant of skewed GC, e.g. AT-rich genomes).
    gc_balance_pen = min(1.0, (abs(guide.gc_content - 0.5) / 0.5) * guide.context.gc_multiplier)
    context_compat = min(1.0, guide.context.multiplier)     # >1 clipped to 1 for the term

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
    # NB: the context efficiency factor is already baked into the outcome
    # probabilities (knockout/functional) upstream, so we do NOT re-multiply here
    # -- that would double-count context. The small `context` term above remains as
    # an explicit compatibility signal.
    pos_mass = sum(w for w in FINAL_WEIGHTS.values() if w > 0)
    final = max(0.0, min(1.0, raw / pos_mass))
    return round(final, 4), {k: round(v, 4) for k, v in contributions.items()}


def _confidence(guide: Guide) -> float:
    """Confidence shrinks when penalties / off-target risk / no-edit are high."""
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
        """Export as the canonical {(var_i, var_j): bias} mapping that quantum /
        annealing SDKs consume directly -- e.g.
        `dimod.BinaryQuadraticModel.from_qubo(qubo.to_qubo_dict())` (D-Wave),
        Qiskit's `QuadraticProgram`, or Amazon Braket. Variables are labelled by
        guide_id so a returned bitstring maps straight back to guides.

        This is the dependency-free seam for the quantum integration plan
        (see docs/QUANTUM_INTEGRATION.md): no quantum package is needed to produce
        it, and no Q-Guide code changes when a quantum `Optimizer` consumes it.
        """
        ids = self.guide_ids
        return {(ids[i], ids[j]): coeff
                for (i, j), coeff in self.linear_quadratic.items()}


def _similarity(a: Guide, b: Guide) -> float:
    """Redundancy proxy: positional overlap + spacer Hamming similarity."""
    # positional overlap
    overlap = max(0, min(a.end, b.end) - max(a.position, b.position))
    span = max(a.end - a.position, 1)
    pos_sim = overlap / span
    # sequence similarity (only if equal length)
    seq_sim = 0.0
    if len(a.sequence) == len(b.sequence) and a.sequence:
        same = sum(1 for x, y in zip(a.sequence, b.sequence) if x == y)
        seq_sim = same / len(a.sequence)
    # nearby cut sites are redundant for coverage
    near = 1.0 if abs(a.cut_site - b.cut_site) < 10 else 0.0
    return min(1.0, 0.5 * pos_sim + 0.3 * seq_sim + 0.2 * near)


def build_qubo(
    guides: List[Guide],
    set_size: int,
    reward_scale: float = 1.0,
    redundancy_penalty: float = 0.8,
    cardinality_penalty: float = 1.5,
) -> QUBO:
    """Construct a QUBO whose minimum-energy bitstring is the best guide set.

    Diagonal (linear) terms reward utility *and* encode the cardinality constraint
    (penalise deviating from `set_size` selections). Off-diagonal terms penalise
    selecting redundant pairs.
    """
    n = len(guides)
    Q: Dict[Tuple[int, int], float] = {}

    # Cardinality constraint  P * (sum x_i - k)^2  expands to:
    #   P * x_i*(1 - 2k)   on the diagonal   +   2P * x_i x_j  off-diagonal
    P = cardinality_penalty
    k = set_size
    for i in range(n):
        # linear: reward (negative -> lowers energy) + cardinality diagonal
        reward = -reward_scale * guides[i].final_score
        Q[(i, i)] = reward + P * (1 - 2 * k)
        for j in range(i + 1, n):
            sim = _similarity(guides[i], guides[j])
            Q[(i, j)] = redundancy_penalty * sim + 2 * P

    return QUBO(linear_quadratic=Q, guide_ids=[g.guide_id for g in guides], set_size=set_size)


# --------------------------------------------------------------------------- #
# Optimizer interface + classical (simulated annealing) implementation         #
# --------------------------------------------------------------------------- #
class Optimizer(Protocol):
    method: str
    def solve(self, qubo: QUBO) -> Tuple[List[int], float, int]: ...


class SimulatedAnnealingOptimizer:
    """Deterministic simulated annealing over the QUBO bitstring.

    Determinism (seeded LCG) keeps tests reproducible; quality is fine for the
    tens-to-hundreds of candidate guides a single locus produces.
    """

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

        # Greedy warm start: top-k by final reward heuristic from the diagonal.
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
    """Quantum-annealing-style optimizer via D-Wave's `dimod` data model.

    Consumes the QUBO through `QUBO.to_qubo_dict()` and samples it with
    `dwave.samplers.SimulatedAnnealingSampler` (the real Ocean software stack on a
    classical sampler). Moving to *actual* quantum hardware is a one-line sampler
    swap -- `EmbeddingComposite(DWaveSampler(token=...))` -- with no other change,
    because the QUBO and the returned bitstring are identical.

    See docs/QUANTUM_INTEGRATION.md. Requires `dimod` + `dwave-samplers`; if they
    are not installed, `quantum_available()` returns False and the UI/factory falls
    back to classical simulated annealing.
    """

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

        best = sampleset.first.sample                       # {guide_id: 0/1}
        x = [int(best[gid]) for gid in qubo.guide_ids]
        return x, float(sampleset.first.energy), self.num_reads


def quantum_available() -> bool:
    """True iff the D-Wave (dimod) optimizer can be constructed."""
    try:
        import dimod  # noqa: F401
        from dwave.samplers import SimulatedAnnealingSampler  # noqa: F401
        return True
    except Exception:
        return False


# Backend registry consumed by the pipeline / UI. "sa" is always available.
def available_backends() -> Dict[str, str]:
    backends = {"sa": "Simulated Annealing (classical)"}
    if quantum_available():
        backends["dwave"] = "D-Wave (dimod / quantum annealing)"
    return backends


def make_optimizer(backend: str = "sa") -> "Optimizer":
    """Construct an optimizer by backend key, falling back to classical SA."""
    if backend == "dwave" and quantum_available():
        return DimodQUBOOptimizer()
    return SimulatedAnnealingOptimizer()


DEFAULT_OPTIMIZER: Optimizer = SimulatedAnnealingOptimizer()


def optimize_guide_set(
    guides: List[Guide],
    set_size: int = 3,
    optimizer: Optimizer = DEFAULT_OPTIMIZER,
) -> OptimizationResult:
    """Select the best N-guide set and explain the choice/rejections (Steps 7 & G)."""
    if not guides:
        return OptimizationResult(
            selected_guide_ids=[], objective_value=0.0,
            method=optimizer.method, iterations=0,
        )

    set_size = max(1, min(set_size, len(guides)))
    qubo = build_qubo(guides, set_size)
    x, energy, iters = optimizer.solve(qubo)

    selected = [qubo.guide_ids[i] for i, bit in enumerate(x) if bit]
    by_id = {g.guide_id: g for g in guides}
    selected.sort(key=lambda gid: by_id[gid].final_score, reverse=True)

    rejected = _explain_rejections(guides, selected, set_size)
    tradeoffs = _tradeoffs(guides, selected)

    return OptimizationResult(
        selected_guide_ids=selected,
        objective_value=round(-energy, 4),     # report as "higher is better"
        method=optimizer.method,
        iterations=iters,
        rejected_explanations=rejected,
        tradeoffs=tradeoffs,
    )


def best_single_guide(guides: List[Guide]) -> Optional[str]:
    if not guides:
        return None
    return max(guides, key=lambda g: g.final_score).guide_id


def _explain_rejections(guides, selected, set_size) -> Dict[str, str]:
    by_id = {g.guide_id: g for g in guides}
    sel_set = set(selected)
    out: Dict[str, str] = {}
    # explain the top few near-miss guides
    near = [g for g in guides if g.guide_id not in sel_set][:5]
    for g in near:
        reasons = []
        # redundancy against any selected guide?
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
