# Q-Guide — Guide-Set Selection & Quantum Optimization: Pseudocode

Reflects the real algorithm in `qguide/core/optimization.py` (Steps 6 & 7 of the
Q-Guide pipeline) plus the QAOA quantum solver added in `qguide/core/optimizers_quantum.py`.
Nothing here is a stand-in — it is the actual control flow, written language-agnostically
so it can be checked against either file line-by-line.

---

## 0. Inputs

```
guides[]        // candidate CRISPR guide RNAs for one target locus, each already
                 // carrying upstream scores: on_target, off_target.risk_score,
                 // outcome.knockout_prob, outcome.functional_disruption_score,
                 // sequence_quality, secondary_structure_penalty, gc_content,
                 // context.multiplier, ensemble.{specificity,uncertainty,...}
set_size  = N    // how many guides to select as the final set
preset           // one of 7 named weight profiles, e.g. "balanced",
                 //   "therapeutic_safety", "max_knockout", ...
backend          // "classical" | "quantum_inspired" | "quantum_hardware" | "qaoa"
```

---

## 1. STEP 6 — Per-guide utility score (classical, unchanged by quantum step)

```
function compute_final_score(guide):
    gc_penalty      = clamp01( |guide.gc_content - 0.5| / 0.5 * guide.context.gc_multiplier )
    context_compat  = clamp01( guide.context.multiplier )

    weighted_sum =   0.25 * guide.on_target
                   + 0.25 * guide.knockout_prob
                   + 0.20 * guide.functional_disruption_score
                   + 0.10 * context_compat
                   + 0.10 * guide.sequence_quality
                   - 0.30 * guide.off_target.risk_score
                   - 0.10 * guide.secondary_structure_penalty
                   - 0.10 * gc_penalty

    final_score = clamp01( weighted_sum / sum(positive_weights) )   // renormalize to 0..1
    return final_score, per_term_breakdown

for guide in guides:
    guide.final_score, guide.breakdown = compute_final_score(guide)
sort guides by final_score descending
```

This ranks guides individually. It is **not** the answer to "which *set* of N guides is
best" — redundant guides (overlapping cut sites, near-duplicate sequences, shared
off-target liabilities) can dominate a naive top-N. That combinatorial problem is Step 7.

---

## 2. STEP 7a — Build the QUBO (the bridge from biology to an optimization problem)

```
function quality_i(guide, weights):
    // reward term: blend of on-target, desired-outcome, knockout, specificity,
    // repair-outcome, functional-disruption, cross-model-agreement — each weighted
    return clamp01( weighted_average(guide's positive signals, weights.q_*) )

function risk_i(guide, weights):
    // penalty term: blend of off-target risk, prediction uncertainty, risky context
    return clamp01( weighted_average(guide's negative signals, weights.r_*) )

function redundancy_ij(guide_a, guide_b, weights):
    pos_overlap  = overlap(a.span, b.span) / span_length          // 0..1
    seq_identity = fraction_of_matching_bases(a.sequence, b.sequence)
    cut_near     = 1 if |a.cut_site - b.cut_site| < 10bp else 0
    shared_OT    = jaccard( a's predicted off-target annotation classes,
                             b's predicted off-target annotation classes )
    return clamp01( weighted_average([pos_overlap, seq_identity, cut_near, shared_OT],
                                       weights.d_*) )

function build_qubo(guides, set_size = k, weights):
    n = len(guides)
    P = weights.cardinality_penalty          // lambda enforcing "pick exactly k"
    Q = empty map (i, j) -> coefficient

    for i in 0..n-1:
        qi = quality_i(guides[i], weights)
        ri = risk_i(guides[i], weights)
        // diagonal: reward good guides (negative energy), penalize risk,
        // plus the diagonal contribution of the (sum x - k)^2 cardinality term
        Q[i, i] = -quality_scale * qi + risk_scale * ri + P * (1 - 2k)

        for j in i+1..n-1:
            red  = redundancy_ij(guides[i], guides[j], weights)
            pair = redundancy_penalty * red - diversity_bonus * (1 - red)
            // off-diagonal: penalize redundant pairs, reward diverse pairs,
            // plus the cross-term contribution of the cardinality constraint
            Q[i, j] = pair + 2 * P

    return QUBO(Q, guide_ids = [g.id for g in guides], set_size = k)

// Full objective this encodes (equivalent closed form):
//   E(x) = - sum_i quality_i * x_i
//          + sum_i risk_i * x_i
//          + sum_{i<j} redundancy_ij * x_i * x_j
//          + lambda * (sum_i x_i - k)^2         // ties everything to "exactly k selected"
//   x_i in {0, 1},  minimize E(x)
```

The minimum-energy bitstring `x*` is the best guide **set** — this single QUBO is
solver-agnostic; every backend below consumes exactly the same `Q`.

---

## 3. STEP 7b — Solve the QUBO: three interchangeable backends

### 3a. Classical — simulated annealing (baseline, always available)

```
function simulated_annealing_solve(qubo):
    x = greedy_init(qubo)                 // seed with k lowest-diagonal-energy guides
    best = x; best_energy = qubo.energy(x)
    for step in 0..num_steps:
        temp = anneal_schedule(step)                  // exponential cool-down
        i = random_index()
        x[i] = flip(x[i])                              // propose a bit flip
        new_energy = qubo.energy(x)
        delta = new_energy - current_energy
        if delta < 0 or random() < exp(-delta / temp):  // Metropolis acceptance
            accept move; update best if improved
        else:
            revert move
    return best, best_energy, num_steps
```

### 3b. Quantum-inspired — D-Wave `dimod` / classical annealing sampler (already wired)

```
function dwave_solve(qubo):
    bqm = dimod.BinaryQuadraticModel.from_qubo(qubo.to_qubo_dict())
    sampler = use_hardware ? DWaveSampler (real QPU, needs Leap token)
                            : SimulatedAnnealingSampler (classical stand-in, offline)
    result = sampler.sample(bqm, num_reads = 200)
    x = decode(result.first.sample, qubo.guide_ids)
    return x, result.first.energy, num_reads
```

### 3c. Quantum — QAOA on a real gate-model circuit, run on a simulator  ← the new file

This is the genuinely "quantum" path: an actual parameterized quantum circuit is built
and executed (on `AerSimulator` today; on IBM Quantum hardware later, same circuit).

```
function qubo_to_ising(qubo):
    // Standard substitution for binary QUBO -> spin Ising:  x_i = (1 - z_i) / 2,  z_i in {-1,+1}
    offset = 0
    h = zeros(n)          // linear (single-qubit Z) coefficients
    J = empty map          // quadratic (two-qubit ZZ) coefficients
    for (i, j), Qij in qubo.entries():
        if i == j:
            offset += Qij / 2
            h[i]   -= Qij / 2
        else:
            offset += Qij / 4
            h[i]   -= Qij / 4
            h[j]   -= Qij / 4
            J[i,j] += Qij / 4
    return h, J, offset

function build_cost_hamiltonian(h, J):
    // Cost Hamiltonian H_C = sum_i h_i Z_i + sum_ij J_ij Z_i Z_j
    // (one Pauli term per qubit / coupled qubit-pair; identical structure to the QUBO graph)
    return PauliSumOperator(h, J)

function qaoa_circuit(H_cost, reps = p):
    // Alternate cost-unitary and mixer-unitary layers, p times, from |+>^n
    // start:      |+>^n  (equal superposition, via H on every qubit)
    // per layer l: apply exp(-i * gamma_l * H_cost)      (problem-encoded phase)
    //              apply exp(-i * beta_l  * H_mixer)     (H_mixer = sum_i X_i, drives exploration)
    // parameters:  gamma_1..p, beta_1..p   (2p classical parameters to optimize)
    return parameterized_circuit

function qaoa_solve(qubo, reps = 2, shots = 4096, max_iter = 100):
    h, J, offset = qubo_to_ising(qubo)
    H_cost = build_cost_hamiltonian(h, J)
    circuit = qaoa_circuit(H_cost, reps)

    function expected_energy(params):                  // objective for the CLASSICAL outer loop
        bind circuit's gamma/beta to params
        estimate <psi(params)| H_cost |psi(params)>     // via Estimator primitive on simulator
        return estimated_energy

    best_params = classical_optimizer.minimize(expected_energy, start = random(2*reps))
                  // e.g. COBYLA / SPSA — a classical optimizer drives the quantum circuit's
                  // parameters; this is the "hybrid" part of QAOA

    final_circuit = bind(circuit, best_params) + measure_all
    counts = run_on_simulator(final_circuit, shots)     // sample the optimized state
    best_bitstring = most_frequent(counts)
    x = decode(best_bitstring, qubo.guide_ids)           // z -> x via x_i = (1 - z_i) / 2
    energy = qubo.energy(x)
    return x, energy, shots
```

### 3d. Selecting a backend (drop-in, same call site everywhere)

```
function make_optimizer_for_mode(mode):
    match mode:
        "classical":         return SimulatedAnnealingOptimizer()
        "quantum_inspired":  return DimodQUBOOptimizer()          // dimod/neal, offline
        "quantum_hardware":  return DimodQUBOOptimizer(use_hardware=true, token=...)
        "qaoa":              return QAOAOptimizer(reps=2)          // new: gate-model, Aer today
```

All four return the identical `(bitstring, energy, iterations)` triple, so nothing
downstream (explainability, comparison, UI, API) needs to know which backend ran.

---

## 4. STEP 7c — Turn the winning bitstring into an explainable result

```
function optimize_guide_set(guides, set_size, optimizer, preset):
    weights   = PRESETS[preset]
    qubo      = build_qubo(guides, set_size, weights)
    x, energy, iters = optimizer.solve(qubo)
    selected  = [guides[i].id for i where x[i] == 1]

    top_n     = top set_size guides by final_score alone (naive baseline)
    rejected  = explain_each_near_miss(guides, selected)   // "redundant with X", "off-target risk", ...
    tradeoffs = summarize(selected)                          // mean knockout%, mean off-target%, cut-site spread
    metrics   = set_level_metrics(selected)                  // expected_outcome, off_target_burden,
                                                               // diversity, uncertainty (all 0..1)

    return {
        selected, energy, method: optimizer.method, iterations: iters,
        top_n, rejected, tradeoffs, metrics,
        comparison_note: "optimized set vs naive top-N — same / lower redundancy, trade-off explained"
    }
```

---

## 5. Validation strategy (why this is safe to trust before hardware)

```
for a small instance (n <= ~18 guides, so brute force is tractable):
    ground_truth = brute_force_min_energy(qubo)            // try every valid k-subset
    assert simulated_annealing_solve(qubo).energy ~= ground_truth
    assert dwave_solve(qubo).energy               ~= ground_truth
    assert qaoa_solve(qubo).energy                ~= ground_truth   (approximate — QAOA is heuristic)
// all three solvers consume the SAME qubo, so any disagreement in the *set chosen*
// is a solver-quality question, never a biology question — the scientific honesty
// invariant this whole design is built around.
```

**Honesty note carried over from the codebase:** the quantum step only *searches* the
combination space defined by `quality_i` / `risk_i` / `redundancy_ij`. Those per-guide
biological scores come from classical heuristics upstream (Step 6 and earlier) — QAOA,
D-Wave, and simulated annealing all optimize the *same* objective, so switching solvers
changes speed/scalability, not biological accuracy.
