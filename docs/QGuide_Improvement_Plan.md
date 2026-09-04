# QGuide — Improvement Plan (grounded in the current codebase)

_Stage 1 deliverable: repository inspection + gap analysis + staged plan. No app code
changed in this pass. Principle: **reuse and improve the existing architecture; do not
rewrite.** The codebase is already a modular, honestly-flagged heuristic pipeline with
swappable interfaces — most of the brief is "expose / complete / normalize", not "build
from zero"._

## 1. Current architecture (what actually exists)

**Backend science — `qguide/core/`** (all interpretable heuristics, clearly flagged; no
trained ML yet, no genome alignment):
- `guide_generator.py` PAM scan + geometry · `scoring.py` 7 component sub-scores
  (GC, PAM, complexity, homopolymer, structure, distance, quality) via a `COMPONENTS`
  registry · `off_target.py` heuristic risk + per-hit report + **`GenomeAlignmentOffTargetEngine`
  stub** (honest "not available") · `outcome_prediction.py` rule-based NHEJ priors ·
  `context_adjustment.py` config multipliers · `ensemble.py` named-component
  `final_qguide_score` + confidence/uncertainty · `outcome_modes.py` registry
  (knockout/precise/base/prime/regulation/screen; edit modes flagged provisional) ·
  `optimization.py` **real QUBO + 3 solvers** · `pipeline.py` orchestrator ·
  `benchmark.py`, `report.py`, `explainability.py`.
- **Swappable interfaces already present**: `OffTargetEngine`, `OutcomeMode`,
  `ScoreComponent`, `Optimizer`, `OutcomeModel` protocols. New models drop in with zero
  pipeline change — this is the key lever for Part 1/2.

**Ensemble (Part 1) — already produces** per guide: `on_target_score, off_target_score,
specificity_score, desired_outcome_score, repair_outcome_score, genomic_context_score,
cell_context_score, model_agreement_score, uncertainty_score, final_qguide_score`, plus
`weights`, `contributions` (signed per-term), `provisional[]`, `confidence_label`,
`goal_profile`, `badges`. Goal profiles (6) × risk-tolerance scaling exist. UI shows an
`EnsemblePanel`.
- **Missing**: no named external models (Azimuth/RuleSet2-3/CRISPRon/DeepSpCas9/CFD/MIT/
  inDelphi/Lindel/FORECasT) — `model_agreement` is a pstdev proxy over 4 internal signals,
  not real cross-model agreement. No per-model adapter registry, no agree/disagree view.

**QUBO (Part 2) — `optimization.py` already has** `min x^T Q x`, x_i∈{0,1}: reward
`-reward_scale·final_score`, redundancy `redundancy_penalty·similarity(i,j)` (position +
Hamming + cut proximity), cardinality `P·(Σx_i−k)^2`. Modes: `classical` (built-in SA),
`quantum_inspired` (dimod SimulatedAnnealingSampler), `quantum_hardware` (DWave + Leap
token, honest fallback). QUBO export to dict. `top_n_individual` vs set comparison +
`tradeoffs`, `expected_outcome_delta`, `off_target_delta` exist.
- **Missing vs brief**: reward is a single `final_score`, not the explicit
  `quality_i` / `risk_i` decomposition; no configurable weight API; no presets
  (Balanced / Max-KO / Max-specificity / Min-uncertainty / Broad-coverage / Therapeutic /
  Screening); no exon-coverage or shared-off-target redundancy terms (no genome data).

**Backend app/data — `qguide/app/`**: FastAPI, JWT HS256 (7-day), PBKDF2-HMAC-SHA256,
signup/login/`/me`, `/run` (charges 5 credits + saves project), `/design`, `/report`,
`/benchmark`, `/sensitivity`, `/simulate`, `/predict-experiment`, `/optimizer/modes`,
`/enzymes`, `/admin/users`, `/admin/credits`. SQLite local / Postgres prod, hand-rolled
`_migrate()` (no Alembic). Models: **User, Transaction, Project** (projects = request/
response JSON blobs). Credits + ledger + packages exist; **dev-mode billing** (price passed
from client, no provider).
- **Missing**: forgot/reset/change-password, logout/sessions, email; folders, rename/
  duplicate/move/archive/soft-delete, search/favorites/recent; normalized entities
  (GuideCandidate, ModelScore, OffTargetHit, GuideSet, OptimizationRun, BillingRecord,
  AnalysisRun, Report, SimulationResult, AdminAuditLog); async jobs/status; RBAC beyond
  ADMIN_EMAILS; pre-run cost estimate endpoint.

**Frontend — `web/`** (Next 14, Tailwind, purple theme tokens: `ink, muted, bg, surface,
border, brand, good, warn, bad`): `/login` (combined signin+signup), `/new` wizard,
`/project/[id]` (5 tabs: Rankings, Best Set, Outcome, Compare, 3D), `/project/[id]/visualize`
(collapsible 3D dashboard + `CrisprSimulation3D` scan→PAM→R-loop→cut→break→replace),
`/account`, `/buy`, `/admin`. Components: `Shell` (sidebar), `ui`, `Charts`, `Ensemble`,
`Dna`, `viz/*`.
- **Missing**: dashboard landing page; forgot/reset-password pages; account sub-sections
  (security/usage split); folder file-explorer sidebar (search/recent/favorites/archived);
  distinct "Basic Results" and "Simulation" pages; job-status UI.

**Tests** (~77, pytest): auth/credits/projects/admin, scoring, ensemble, optimization/QUBO/
solvers, generation, prediction, simulation, stages 4-6. **Missing**: password-reset,
folders/move, normalized-model, cost-estimate, async-status, frontend/integration tests.

## 2. Status matrix (brief Part -> state -> primary gap)

| Part | State | Primary gap to close |
|---|---|---|
| 1 Ensemble breakdown | **Partial (strong)** | Named-model adapter registry + agree/disagree + limitations UI; honest provisional labels |
| 2 QUBO all-variables | **Partial (strong)** | Explicit quality_i/risk_i/redundancy_ij, configurable weights API, 7 presets, richer compare |
| 3 Auth/account | **Partial** | forgot/reset/change password, logout, account sub-pages |
| 4 Credits/billing | **Partial** | pre-run cost estimate, billing records, usage-by-project, labeled dev-mode |
| 5 Projects/folders | **Missing (mostly)** | folders + soft-delete/archive + rename/dup/move + search/favorites/recent |
| 6 Workspace pages | **Partial (strong)** | split Basic Results + Simulation pages; persistent project nav; outcome-mode adaptivity |
| 7 UI/design | **Partial** | consistent research-grade theme, sidebar file-explorer, top bar |
| 8 Dashboard | **Missing** | landing dashboard with overview cards + charts |
| 9 Admin | **Partial (strong)** | health/model-availability/audit-log/RBAC additions |
| 10 Data model | **Partial** | normalize entities incrementally (keep JSON blob as source-of-truth initially) |
| 11 Background jobs | **Missing** | job status states + async for long ops (off-target/library) |
| 12 Scientific honesty | **Partial (strong)** | surface source (real/heuristic/provisional/experimental) everywhere + global disclaimer |
| 13 Order | — | followed below |
| 14 Testing | **Partial** | add tests per new feature |

## 3. Proposed staged plan (each stage independently shippable, additive, tested)

**Stage A — Ensemble Breakdown + model-adapter architecture (Part 1, 12).** Add
`qguide/core/models/` with an `OnTargetModel`/`OutcomeModelAdapter` registry and honest
adapters: real code-only **Doench Rule Set 2** first (validated, no data files), others as
labeled `provisional` adapters behind the interface. Compute real `model_agreement` /
disagreement from adapters present. Extend `EnsembleScore` with `model_scores[]` +
`sources`. Build a rich **Ensemble Breakdown** panel (per-model score, weight, agree/
disagree, confidence, limitations, plain-English "why the score changed"). _Backend ready;
highest visible value; low risk._

**Stage B — QUBO variables, weights, presets, comparison (Part 2).** Refactor
`optimization.py` to expose explicit `quality_i`, `risk_i`, `redundancy_ij`, `lambda·(Σx-N)^2`
with a configurable `QuboWeights` dataclass + 7 named presets; add `/optimizer/presets`
and thread weights through `/run`. Enrich Best-Guide-Set + Compare UI (expected outcome,
off-target burden, diversity, uncertainty, classical vs quantum-inspired). Keep the honesty
banner: classical/ML = biology, quantum-inspired = combination search.

**Stage C — Auth completion + Dashboard + Account sections (Parts 3, 8).** Add change/
forgot/reset-password (token-based; dev-mode email stub clearly labeled), logout; a landing
`/dashboard` with overview cards + charts; account sub-tabs (profile/security/credits/
billing/usage).

**Stage D — Projects, folders, soft-delete (Parts 5, 7).** Add `Folder` + project
`folder_id`, `archived_at`, `deleted_at`, `favorite`; endpoints for rename/duplicate/move/
archive/restore/soft-delete; file-explorer sidebar with search/recent/favorites/archived.

**Stage E — Credits estimate + billing records + labeled dev-mode (Part 4).** `/credits/
estimate` (cost preview + confirm), `BillingRecord`, usage-by-project/operation.

**Stage F — Data-model normalization + background jobs + admin/health (Parts 10, 11, 9).**
Introduce normalized tables incrementally (guides/off-targets/optimization-runs/audit-log)
while keeping the JSON blob as compatibility source; add job-status states + async for the
genuinely long ops; extend admin (model/optimizer availability, audit log, RBAC).

**Stage G — Split workspace pages + Simulation/Basic-Results + tests + docs (Parts 6, 14, 15).**

## 4. Recommended starting point
**Stage A (Ensemble Breakdown + Rule Set 2 adapter).** It is the product's stated
differentiator (explainable, outcome-first), the backend already emits every component, the
model-adapter interface already exists, and it ships real scientific value (a validated
on-target model) without touching auth/billing/data-model risk.
