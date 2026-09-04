# QGuide — Before vs Now (Formula & QUBO Upgrade)

A complete, user-facing list of what changed. Everything is **additive** — no existing
feature, score, or API field was removed or renamed. Backend: **145 tests pass** (was 82,
2 of which were skipped without the quantum backend). Frontend: **Next.js build passes**.

---

## 1. Individual guide score

| | Before | Now |
|---|---|---|
| Scores per guide | `final_score` (legacy, ranks) + `final_qguide_score` (ensemble) | **+ `QGuide Precision Score`** — one transparent 0–1 number from ~29 named components |
| Transparency | Ensemble component bars | Full **raw → weight → weighted-contribution → source** breakdown per component |
| Missing data | Implicit | Explicit **abstention**: unavailable components are dropped and raise `uncertainty` / lower `data_completeness` — never fabricated |
| Presets | — (individual score had no presets) | **9 presets**: Balanced, Max Knockout, Max Specificity, Max Confidence, Low Off-Target Risk, Broad Coverage, Screening Library, Therapeutic Safety, Experimental Discovery |
| Config | Weights hardcoded | `qguide/config/precision_weights.json` (editable, no code change) |

## 2. Biological variables (things most tools don't combine)

| Variable | Before | Now |
|---|---|---|
| Exon importance | absent | positional **proxy** (labeled), abstains if no target |
| Protein-domain disruption | absent | interface present; **unknown** until a domain source is wired |
| Transcript-isoform coverage | absent | interface present; **unknown** until isoform models exist |
| Conservation | absent | interface present; **unknown** |
| Variant/SNP conflict | absent | interface present; **unknown** until a variant DB is wired |
| Chromatin accessibility | absent | interface present; **unknown** |
| Cell-context confidence | folded into a multiplier | explicit **real** signal (higher with a cell type, low without) |
| Experimental practicality | partial (homopolymer/structure penalties) | explicit practicality risk (GC extremes + repeats + structure) |

New module: `qguide/core/biological_context.py` (`NullAnnotationProvider`,
`PositionalProxyAnnotationProvider`). Honest by construction — no gene model means
"unknown", not a guessed number.

## 3. Off-target analysis

| | Before | Now |
|---|---|---|
| Signal | `risk_score` + synthetic per-hit list | **+ biological `severity`** aggregation |
| Severity model | none | location-weighted (coding > regulatory > intron > intergenic), **seed-mismatch aware** (a seed mismatch disarms a hit), CFD-weighted |
| Counts surfaced | mismatch bins | coding-hit / regulatory-hit / high-severity / seed-mismatch counts |
| Essential/disease genes | — | reported as **unknown** (no gene DB) rather than zero |
| Reproducibility | per-process `hash()` → results varied across runs | **deterministic** hash → identical results across runs/machines/deploys (bug fixed) |

## 4. QUBO / quantum-inspired optimizer

| | Before | Now |
|---|---|---|
| Reward `quality_i` | on-target, outcome, knockout, specificity, repair, functional, agreement | **+ Precision Score, exon importance, transcript coverage** (availability-weighted) |
| Penalty `risk_i` | off-target, uncertainty, context risk | **+ severity, missing-data risk, variant conflict, practicality** |
| Pairwise penalty | position, sequence, cut-proximity, shared off-target | **+ correlated-uncertainty, isoform** (placeholder) |
| Pairwise reward | `diversity_bonus·(1−redundancy)` | **explicit `synergy_ij`**: region/exon/domain diversity, efficiency↔specificity balance, uncertainty & off-target **decorrelation** |
| Weights | 14 sub-weights | **31 sub-weights**, all in `QuboWeights`, 7 solver presets |
| Reproducibility | nondeterministic annotations leaked into QUBO | deterministic |

## 5. Classical vs quantum-inspired comparison

| | Before | Now |
|---|---|---|
| Comparison | Top-N vs optimized deltas on the run | **Full 3-way report**: Top-N individual vs classical vs quantum-inspired |
| Metrics | outcome + off-target deltas | outcome, off-target burden **+ severity**, diversity, redundancy, uncertainty, QUBO energy per set |
| Verdict | — | honest verdict: *does set-optimization beat Top-N?* and *is the quantum layer meaningful?* (at experiment scale, classical == quantum-inspired — stated plainly) |

New module: `qguide/core/quantum_comparison_report.py`.

## 6. Explanations

| | Before | Now |
|---|---|---|
| Per-guide | ranking prose | **+ Precision explanation**: why high/low, which variables helped/hurt, what data was missing, what to validate |
| Per-set | tradeoff notes | **+ set explanation**: why chosen, why strong individuals were excluded (with the redundant partner named), safer/diverse/outcome/confident characterization, what quantum-inspired contributed |

New module: `qguide/core/formula_explainer.py`.

## 7. API (FastAPI)

| Endpoint | Before | Now |
|---|---|---|
| `POST /design`, `POST /run` | returned guides | **now also serialize** `precision`, `bio_context`, and `off_target.severity` per guide |
| `GET /precision/presets` | — | **new** — the 9 Precision presets + weights |
| `POST /optimizer/compare` | — | **new** — Top-N vs classical vs quantum-inspired + set explanation (free) |
| `POST /precision/explain` | — | **new** — formula-level explanation of a guide's Precision Score |
| `GET /optimizer/presets`, `/optimizer/modes` | present | unchanged (still there) |

## 8. Frontend (Next.js)

| | Before | Now |
|---|---|---|
| Ensemble page table | ensemble columns + confidence | **+ Precision column** |
| Selected-guide panels | Ensemble breakdown + weights | **+ QGuide Precision Score panel** (positive drivers, penalties, abstained components, rationale), **Off-target severity panel**, **Biological-context panel** |
| API client | run/auth/projects | **+ `design`, `precisionPresets`, `optimizerCompare`, `precisionExplain`** |

## 9. Tests

Added: `test_precision_score.py`, `test_biological_context.py`, `test_offtarget_severity.py`,
`test_qubo_upgrade.py`, `test_quantum_comparison.py`, `test_formula_explainer.py`,
`test_edge_cases_upgrade.py`, `test_api_formula_endpoints.py`. Total **82 → 145** passing.

## 10. What did NOT change (safety)

No API field removed or renamed; existing scores (`final_score`, `final_qguide_score`,
ensemble, off-target risk) still computed and ordered exactly as before; auth/credits/
projects/folders/admin untouched; honesty posture unchanged (heuristics stay flagged,
no clinical claims, no trained models are pretended into existence).

---

## Files changed

**New (backend):** `qguide/core/biological_context.py`, `qguide/core/precision_score.py`,
`qguide/core/quantum_comparison_report.py`, `qguide/core/formula_explainer.py`,
`qguide/config/precision_weights.json`.
**Modified (backend):** `qguide/app/schemas.py`, `qguide/app/routes.py`,
`qguide/core/off_target.py`, `qguide/core/optimization.py`, `qguide/core/pipeline.py`.
**New (tests):** 8 files (see §9).
**Modified (frontend):** `web/components/Ensemble.tsx`,
`web/app/project/[id]/ensemble/page.tsx`, `web/lib/api.ts`.
**Docs:** `docs/QGuide_Formula_Upgrade.md`, `docs/CHANGELOG_Before_After.md`.
