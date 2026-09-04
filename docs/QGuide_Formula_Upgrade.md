# QGuide — Formula & QUBO Upgrade

_Additive upgrade to the scoring, biological-variable, and QUBO-optimization layers.
No app rewrite: every change is a new module or an additive extension behind the
existing swappable interfaces, and the full test suite (121 tests) is green._

> **Scientific claim (unchanged and enforced in code):** classical bioinformatics and
> interpretable heuristics estimate biological guide quality; **quantum-inspired
> optimization only searches the combination space** for the best guide *set* under
> biological constraints. Nothing here is trained on wet-lab data or is clinically
> validated, and unavailable data is never fabricated.

---

## 1. Summary of formula changes

| Area | Before | After |
|---|---|---|
| Individual score | Two scores: legacy `final_score` (ranks) + `final_qguide_score` (ensemble) | Adds a third, richer **QGuide Precision Score** — one transparent 0..1 number from ~29 named, reweightable components with a full breakdown, honest abstention, and a data-completeness/uncertainty model |
| Biological variables | Sequence + heuristic off-target + rule-based outcome only | Adds an **annotation interface** for exon importance, protein-domain disruption, transcript-isoform coverage, conservation, variant/SNP conflict, chromatin accessibility, cell-context confidence — populated where defensible, **abstained (unknown) otherwise** |
| Off-target | Single `risk_score` + synthetic hits | Adds a biological **severity** aggregation (location/seed/CFD-weighted; coding/regulatory/essential counts) distinct from raw risk |
| QUBO reward/penalty | 7 reward + 3 penalty + 4 redundancy sub-weights | +3 reward, +4 penalty, +2 redundancy, and a new **pairwise synergy reward** (6 sub-weights); reward now folds in the Precision Score and biological variables |
| Set comparison | Top-N vs optimized deltas | Full **Top-N vs classical vs quantum-inspired** report with an honest "is the quantum layer meaningful?" verdict |
| Explanation | Per-guide ranking prose | Adds a **formula explainer**: per-guide (why high/low, missing data, what to validate) and per-set (why excluded, tradeoff, quantum contribution) |
| Reproducibility | `hash()` on guide IDs → per-process nondeterminism | Deterministic hash → identical results across runs/machines/deploys |

New modules: `precision_score.py`, `biological_context.py`, `quantum_comparison_report.py`,
`formula_explainer.py`, config `config/precision_weights.json`. Extended:
`off_target.py`, `optimization.py`, `pipeline.py`, `app/schemas.py`.

---

## 2. New variables added

**Positive (raise the score):** on-target efficiency, PAM strength, GC balance, sequence
quality, desired-outcome probability, knockout probability, frameshift probability,
repair-outcome quality, functional-disruption probability, **exon importance**,
**transcript-isoform coverage**, **protein-domain disruption**, **conservation
relevance**, **cell-type compatibility**, **delivery-method compatibility**, model
agreement, **evidence strength**.

**Penalty (lower the score):** off-target **severity**, **severe coding off-targets**,
**promoter/enhancer off-targets**, **essential-gene off-targets**, mismatch-tolerant
binding risk, extreme GC, repetitive-sequence risk, **SNP/variant conflict**, **uncertain
cell context**, model disagreement, **no genome index**, **no trained repair model**.

Bold items are new. Critically, the repo has no gene model / variant DB / chromatin
track, so `transcript_coverage`, `domain_disruption`, `conservation`, `variant_conflict`
and `essential_gene_offtargets` **abstain by default** — they are dropped from the
weighted mean and instead raise uncertainty. `exon_importance` and
`cell_context_confidence` are honestly derivable (a positional proxy and a real
model-coverage signal respectively) and are populated with a `source` label.

---

## 3. The QGuide Precision Score (`precision_score.py`)

A single 0..1 score assembled as, conceptually:

```
Precision = clamp( ( Σ w_pos·value_pos  −  Σ w_pen·value_pen ) / Σ w_pos_available )
```

over **available** components only. Every component records `raw → weight → weighted
contribution → available → source (real|heuristic|proxy|provisional|unknown)`, so the UI
can show exactly how the number was built. Missing components abstain (never guessed) and
lower `data_completeness`, which raises `uncertainty` and the confidence label. Weights
live in `config/precision_weights.json` with **9 presets**: Balanced, Max Knockout, Max
Specificity, Max Confidence, Low Off-Target Risk, Broad Coverage, Screening Library,
Therapeutic Safety, Experimental Discovery.

---

## 4. Outcome-specific behaviour

The Precision Score inherits goal-specific behaviour from the existing outcome modes
(knockout / precise / base / prime / CRISPRi-a / screen) via `desired_outcome` and
`repair_quality`, and layers the presets on top. Knockout-style presets up-weight
frameshift/functional-disruption/exon terms; specificity/therapeutic presets up-weight
off-target severity, essential-gene and variant penalties; broad-coverage up-weights
transcript coverage and pairwise region/exon diversity; screening up-weights model
agreement, practicality and diversity. (Base/prime/CRISPRi-a remain flagged provisional
until dedicated models are wired in — unchanged, honest.)

---

## 5. The upgraded QUBO (`optimization.py`)

Per guide `i`, binary `x_i ∈ {0,1}`:

```
E(x) = Σ_i [ −quality_i + risk_i ] x_i
     + Σ_{i<j} [ redundancy_penalty·redundancy_ij − diversity_bonus·synergy_ij ] x_i x_j
     + λ · (Σ_i x_i − N)^2
```

- **quality_i** now blends on-target, desired-outcome, knockout, specificity, repair,
  functional, model-agreement, **the Precision Score, exon importance and transcript
  coverage** — availability-weighted (abstained terms renormalise away).
- **risk_i** now blends off-target risk, **severity**, uncertainty, context risk,
  **missing-data risk, variant conflict and practicality**.
- **redundancy_ij** adds **correlated-uncertainty** and an **isoform** placeholder.
- **synergy_ij** is new: rewards region/exon/domain diversity, an efficiency↔specificity
  balance, and uncertainty/off-target **decorrelation** — the "pick a complementary team,
  not the same player twice" term.

All weights are in a `QuboWeights` dataclass with 7 solver presets; the three modes
(classical / quantum-inspired / quantum-hardware) consume the identical QUBO.

---

## 6. How quantum-inspired optimization uses the scores

The biological scores (`quality_i`, `risk_i`, `redundancy_ij`, `synergy_ij`) are computed
entirely by classical heuristics/ML upstream and baked into the QUBO coefficients. The
quantum-inspired sampler (D-Wave `dimod`) and the QAOA circuit (Qiskit Aer, in
`optimizers_quantum.py`) only **search the bitstring space** for the minimum-energy set.
They never touch biology. This separation is stated in the comparison report's verdict.

---

## 7. Old vs new scoring

- **Old:** one utility number ranks guides; the ensemble adds components but the deeper
  biological variables and a genuine severity model are absent; the QUBO reward is a
  single blended score with a `(1−redundancy)` diversity term.
- **New:** a fully itemised Precision Score with honest abstention; biological variables
  behind a real interface; a location/seed-weighted severity; a QUBO whose reward folds
  in those variables and adds an explicit pairwise **synergy** reward. Presets now shift
  the *biology being optimised*, not just the ranking.

---

## 8. Classical Top-N vs quantum-inspired (`quantum_comparison_report.py`)

`compare_selection_strategies()` builds one QUBO and evaluates Top-N-individual,
classical-optimized and quantum-inspired sets, reporting per set: selected guides,
per-guide scores, combined outcome, off-target burden + severity, diversity, redundancy,
uncertainty and QUBO energy — plus a verdict. **Observed at experiment scale (tens of
candidates, pick 3): set-optimization beats the naive Top-N (higher diversity / lower
combined risk), while classical and quantum-inspired solve the same easy QUBO and usually
return the same set.** The report says this plainly rather than overselling the quantum
layer; the QUBO's value would grow at library scale (thousands of guides).

---

## 9. Limitations & placeholders (unchanged honesty posture)

- No trained ML models (Azimuth/RuleSet2-3/CRISPRon/DeepSpCas9, inDelphi/Lindel/FORECasT,
  CFD/MIT) — they still abstain behind the model registry.
- No genome alignment → off-target hits and severity are heuristic/synthetic (flagged
  `provisional`, `no_genome_index` penalty fires).
- `transcript_coverage`, `domain_disruption`, `conservation`, `variant_conflict`,
  `essential_gene_offtargets` are **unknown** until a gene model / dbSNP / conservation
  track is configured; `exon_importance` is a **positional proxy**, not true exon-rank.
- Quantum-inspired ≈ classical at current scale by design.

---

## 10. Next steps for real model integration

1. Drop a code-only **Doench Rule Set 2** on-target adapter into the model registry →
   real cross-model agreement + evidence strength immediately light up.
2. Wire a real **GencodeAnnotationProvider / dbSNPVariantProvider** behind
   `biological_context.AnnotationProvider` → exon/domain/transcript/variant components
   stop abstaining and the Precision Score sharpens automatically.
3. Implement `GenomeAlignmentOffTargetEngine` (BWA/Bowtie + CFD) → real severity,
   `no_genome_index` penalty clears.
4. Add inDelphi/Lindel behind `OutcomeMode` → `no_repair_model_support` penalty clears.
5. Benchmark the Precision Score and the optimized-set vs Top-N against a public dataset
   before any accuracy claim.
6. Frontend: a **Formula Breakdown** page — all data is already emitted on
   `guide.precision`, `guide.bio_context` and `off_target.severity` in the `/run`
   response, so the page is a rendering task, not a backend one.
