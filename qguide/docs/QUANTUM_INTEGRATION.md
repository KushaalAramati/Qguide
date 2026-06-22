# Quantum Optimization — Integration Plan

**Status:** planned, not yet implemented. V1 ships a classical solver; this document
is the concrete roadmap for swapping in real quantum / hybrid backends.

Q-Guide's multi-guide selection is already a **QUBO** solved through a pluggable
`Optimizer` interface, so adding a quantum backend is a *drop-in*, not a rewrite.
Nothing in generation, scoring, outcome prediction, context, explainability, or the
UI changes — only the object that consumes the QUBO.

---

## 1. Why it's already quantum-ready

The work is done in two places in [`core/optimization.py`](../core/optimization.py):

- **`build_qubo(guides, set_size, ...) -> QUBO`** — encodes guide selection as
  `minimise xᵀQx`, `xᵢ ∈ {0,1}`. Diagonal terms reward each guide's utility and
  encode the set-size constraint `P·(Σxᵢ − k)²`; off-diagonal terms penalise
  redundant pairs.
- **`Optimizer` protocol** — `solve(qubo) -> (bitstring, energy, iterations)`.
  Today the only implementation is `SimulatedAnnealingOptimizer`.

The dependency-free bridge is **`QUBO.to_qubo_dict()`**, which exports the problem
as the canonical `{(var_i, var_j): bias}` mapping that **every** quantum/annealing
SDK accepts, with variables labelled by `guide_id`. No quantum package is needed to
produce it; a quantum optimizer just consumes it.

```python
qubo = build_qubo(guides, set_size=3)
q = qubo.to_qubo_dict()          # {('gRNA_016','gRNA_016'): -0.77, ('gRNA_016','gRNA_038'): 0.4, ...}
```

---

## 2. Backend options

| Backend | Paradigm | Package(s) | Hardware? | Notes |
|---|---|---|---|---|
| **D-Wave Ocean** | Quantum annealing | `dwave-ocean-sdk` (incl. `dimod`, `neal`) | Leap account + token (free tier) | Closest fit — QUBO is native. Run `neal` (classical) offline first, swap sampler for hardware. |
| **Qiskit** | Gate model (QAOA) | `qiskit`, `qiskit-optimization`, `qiskit-aer` | IBM Quantum (free tier) | Run QAOA on the Aer simulator first, then real hardware. |
| **Amazon Braket** | Annealing + gate | `amazon-braket-sdk` | AWS account (paid) | Submit the same BQM/QUBO to managed devices/hybrid solvers. |

**Recommended first step: D-Wave via `dimod` + `neal`.** It is the real
quantum-annealing software stack on a classical sampler — so it runs offline today,
and moving to actual hardware is a one-line sampler swap with a free token.

---

## 3. Implementation sketches (drop-in `Optimizer`s)

These satisfy the existing `Optimizer` protocol. They are **sketches** — guarded
behind optional imports — not yet added to the codebase.

### 3a. D-Wave (dimod / neal → DWaveSampler)

```python
# core/optimizers_quantum.py  (planned)
class DimodQUBOOptimizer:
    method = "dwave_neal_v1"          # -> "dwave_advantage" on hardware

    def __init__(self, num_reads=200, use_hardware=False, token=None):
        self.num_reads, self.use_hardware, self.token = num_reads, use_hardware, token

    def solve(self, qubo):
        import dimod
        bqm = dimod.BinaryQuadraticModel.from_qubo(qubo.to_qubo_dict())
        if self.use_hardware:
            from dwave.system import DWaveSampler, EmbeddingComposite
            sampler = EmbeddingComposite(DWaveSampler(token=self.token))
        else:
            import neal
            sampler = neal.SimulatedAnnealingSampler()
        result = sampler.sample(bqm, num_reads=self.num_reads)
        best = result.first.sample                      # {guide_id: 0/1}
        x = [best[g] for g in qubo.guide_ids]
        return x, float(result.first.energy), self.num_reads
```

### 3b. Qiskit QAOA (Aer simulator → IBM hardware)

```python
class QAOAOptimizer:
    method = "qiskit_qaoa_v1"

    def solve(self, qubo):
        from qiskit_optimization import QuadraticProgram
        from qiskit_optimization.algorithms import MinimumEigenOptimizer
        from qiskit_algorithms import QAOA
        from qiskit_algorithms.optimizers import COBYLA
        from qiskit.primitives import Sampler
        qp = QuadraticProgram()
        for g in qubo.guide_ids:
            qp.binary_var(g)
        qp.minimize(quadratic=qubo.to_qubo_dict())
        meo = MinimumEigenOptimizer(QAOA(sampler=Sampler(), optimizer=COBYLA(), reps=2))
        res = meo.solve(qp)
        x = [int(round(v)) for v in res.x]
        return x, float(res.fval), 1
```

Both return the **same** `(bitstring, energy, iterations)` triple, so
`optimize_guide_set()` and all the explainability/UI code are unchanged.

---

## 4. Wiring it in

1. **New module** `core/optimizers_quantum.py` with the classes above (optional
   imports so the base install stays light).
2. **Selector** — `optimize_guide_set(..., optimizer=...)` already takes the
   optimizer; expose a `backend` arg (`"sa" | "dwave" | "qaoa"`) that constructs it.
3. **UI toggle** — a Settings/New-Project selectbox: "Optimization backend:
   Simulated Annealing (classical) · D-Wave (annealing) · Qiskit QAOA". Store the
   choice and pass it through `pipeline.run_design`.
4. **API** — add `backend` to `DesignRequest`; `/design` honours it.
5. **Token/secrets** — read D-Wave/IBM tokens from env vars; never commit them.

---

## 5. Dependencies (optional extras)

Keep the base install light; add an extras group:

```text
# requirements-quantum.txt  (planned)
dwave-ocean-sdk>=7        # dimod, neal, dwave-system
# or
qiskit>=1.0
qiskit-optimization>=0.6
qiskit-aer>=0.14
```

---

## 6. Validation & benchmarking

Because every backend consumes the identical QUBO, we can **compare them directly**:

- Run `SimulatedAnnealing`, `dimod/neal`, and `QAOA` on the same `build_qubo(...)`.
- Assert they agree on small instances (use `dimod.ExactSolver` for ground truth
  when `n ≤ ~18`).
- Track objective value, wall-clock, and (on hardware) embedding overhead.
- Surface a "backend comparison" panel: same guides, three optimizers, one chart.

---

## 7. Scope, limits, realism

- **Problem size.** A single locus yields tens–hundreds of candidate guides; current
  QAOA/annealer sizes handle this. Genome-wide, many-locus design is where quantum
  scaling becomes interesting — and where hybrid solvers (Leap hybrid, Braket hybrid)
  are the practical target.
- **Embedding.** Real annealers need minor-embedding; `EmbeddingComposite` handles it
  but adds overhead/noise. Dense Q (many redundancy penalties) embeds less easily.
- **Cost/quotas.** Hardware time is metered; default to simulators, gate hardware
  behind explicit opt-in + token.
- **Honesty.** Quantum will not change V1's *biological* accuracy — it optimises the
  same model's QUBO. Its value is scaling and exact-optimum search, not better biology.

---

## 8. Milestones

1. **M1 (offline, no account):** add `DimodQUBOOptimizer` (neal) + backend selector +
   benchmark vs SA on the same QUBO. ✅ runnable today once `dwave-ocean-sdk` is installed.
2. **M2 (free hardware):** D-Wave Leap token → `DWaveSampler`; QAOA on Aer → IBM Quantum.
3. **M3 (scale):** hybrid solvers for multi-locus / genome-wide guide-set design.
4. **M4:** backend-comparison panel in the UI and `/design?backend=` in the API.
