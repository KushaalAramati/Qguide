# 🧬 Q-Guide

**A context-aware, explainable, quantum-assisted guide RNA recommendation platform for CRISPR experiments.**

Q-Guide is *not* another guide-design calculator. Where most tools answer **"which guide cuts best?"**, Q-Guide answers:

> **"What biological outcome is most likely after editing, and which guide best achieves the user's intended objective?"**

It generates candidate guides, scores them biologically, **predicts the functional outcome of the edit**, folds in **experimental context**, uses **quantum-inspired optimization** to choose the best guide *or guide set*, and explains **every** recommendation like an expert scientist would.

---

## Table of contents
1. [Quick start](#quick-start)
2. [What Q-Guide does (the pipeline)](#what-q-guide-does-the-pipeline)
3. [Architecture](#architecture)
4. [How Q-Guide differs from CHOPCHOP](#how-q-guide-differs-from-chopchop)
5. [How Q-Guide differs from CRISPOR](#how-q-guide-differs-from-crispor)
6. [Why context-aware prediction matters](#why-context-aware-prediction-matters)
7. [Why biological outcome prediction matters](#why-biological-outcome-prediction-matters)
8. [Why explainability matters](#why-explainability-matters)
9. [How quantum-inspired optimization is used](#how-quantum-inspired-optimization-is-used)
10. [Project structure](#project-structure)
11. [Future roadmap](#future-roadmap)
12. [Disclaimer](#disclaimer)

---

## Quick start

```bash
# from the repository root (the folder that contains qguide/)
python -m venv .venv && . .venv/Scripts/activate    # Windows
# or:  source .venv/bin/activate                     # macOS / Linux

pip install -r qguide/requirements.txt

# 1) Run the test-suite
pytest

# 2) Launch the interactive UI
streamlit run qguide/frontend/streamlit_app.py

# 3) (Optional) Run the REST API
uvicorn qguide.app.main:app --reload
#    -> http://127.0.0.1:8000/docs
```

> **Note:** all imports are rooted at the `qguide` package, so commands are run from the
> directory that *contains* `qguide/` (this repository root).

---

## What Q-Guide does (the pipeline)

| Step | Module | What it produces |
|------|--------|------------------|
| 1. Guide generation | `core/guide_generator.py` | PAM scan on both strands → candidate guides (sequence, PAM, strand, position, GC, distance-to-target) |
| 2. Biological scoring | `core/scoring.py` | Modular components: GC, PAM, complexity, homopolymer, structure, distance, quality → on-target score |
| 3. Off-target analysis | `core/off_target.py` | Heuristic risk score, category, predicted count, mismatch distribution — rescaled by enzyme fidelity + organism (e.g. SpCas9-HF1 → lower risk) |
| 4. **Outcome prediction** | `core/outcome_prediction.py` | Frameshift / in-frame / no-edit / knockout / exon-disruption probabilities + functional-disruption score |
| 5. Context adjustment | `core/context_adjustment.py` | Efficiency factor from organism, cell type, Cas, delivery, temperature, expression (JSON rules) — feeds both ranking *and* predicted outcome |
| 6. Multi-objective scoring | `core/optimization.py` | Final 0–1 utility with full signed breakdown |
| 7. **Quantum-inspired optimization** | `core/optimization.py` | QUBO + simulated annealing → best single guide & best N-guide set |
| 8. Output | `app/schemas.py` | Ranked guides, optimized set, predictions, warnings, confidence |
| 9. Interactive analytics | `core/visualization.py` + `frontend/` | Per-guide dashboards (Plotly) |
| 9H. Experiment simulation | `core/pipeline.py::simulate_experiments` | Re-run the design across Cas enzymes / cell types / delivery / temperature / objective and compare predicted outcomes |
| 10. Explainability | `core/explainability.py` | Human-readable "why this guide" narratives |

---

## Architecture

```
            DesignRequest
                 │
   ┌─────────────▼──────────────────────────────────────────────┐
   │                    core/pipeline.py                          │
   │  generate → score → off-target → outcome → context →         │
   │            multi-objective → optimize → explain              │
   └──────┬─────────┬─────────┬─────────┬─────────┬───────┬───────┘
          │         │         │         │         │       │
   guide_generator scoring off_target outcome  context optimization
                                      _prediction _adjustment
                                                            │
                                            explainability  │  visualization
                 │                                          │
            DesignResponse  ◄── FastAPI (app/) ◄────────────┘
                 │
        Streamlit frontend / future React client
```

**Every module is independent and replaceable.** They communicate only through the
Pydantic data model in `app/schemas.py` — never by importing each other. Key extension
points are all interface- or registry-based:

- **Cas enzymes** — add a `CasProfile` to `CAS_PROFILES` (`guide_generator.py`).
- **Scoring components** — register a `(Guide) -> float` callable in `COMPONENTS` (`scoring.py`).
- **Off-target backend** — implement `OffTargetEngine.analyze` (e.g. Bowtie/BLAST/CRISPOR).
- **Outcome model** — implement `OutcomeModel.predict` (e.g. XGBoost/RF/transformer).
- **Context rules** — edit `config/context_weights.json` (no code change).
- **Optimizer** — implement `Optimizer.solve` (e.g. D-Wave / QAOA / Braket).

---

## How Q-Guide differs from CHOPCHOP

[CHOPCHOP](https://chopchop.cbu.uib.no/) is an excellent, fast web tool that **ranks guides by on-target efficiency and off-target counts** against a reference genome, with optional primer design. Its question is *"which sites are cuttable and reasonably specific?"*

Q-Guide differs in intent and output:

| | CHOPCHOP | Q-Guide |
|---|---|---|
| Primary question | Which guide cuts efficiently with few off-targets? | Which guide produces the **intended biological outcome**? |
| Outcome modelling | Efficiency proxy only | **Frameshift / KO / exon-disruption probabilities** as first-class outputs |
| Experimental context | Not modelled | Organism, cell type, delivery, temperature, expression re-weight the ranking |
| Selection | Per-guide ranking | **Multi-guide set optimization** (QUBO) for coverage + low redundancy |
| Explanation | Score table | **Natural-language rationale** per recommendation |
| Optimization | Sorting | **Quantum-inspired** combinatorial optimization framework |

Q-Guide is complementary: a production deployment would plug a CHOPCHOP-style genome
alignment in behind the `OffTargetEngine` interface and keep the outcome/context/optimization layers on top.

## How Q-Guide differs from CRISPOR

[CRISPOR](http://crispor.tefor.net/) is a rigorous specificity tool: it performs genome-wide
off-target enumeration (BWA), reports MIT/CFD specificity scores, and bundles many
published on-target efficiency models. Its strength is **accurate, genome-grounded
specificity and efficiency annotation**.

Q-Guide does **not** try to reproduce CRISPOR's genome-wide alignment in V1 (it uses a
heuristic off-target estimator, behind a swappable interface). Instead it adds the layers
CRISPOR does *not* focus on:

- **Functional-outcome prediction** — turning "this guide is efficient and specific" into
  "this guide has an 87% predicted knockout probability for *your* objective."
- **Context-awareness** — the same guide is re-ranked for stem cells vs neurons, 37 °C vs 30 °C, RNP vs lentivirus.
- **Multi-guide set optimization** — choosing a *combination* of guides that jointly maximise
  coverage and minimise redundancy/off-target, not just the single best line in a table.
- **Explainability** — an expert-style narrative for every choice and rejection.

The intended relationship: **use CRISPOR-grade specificity as an input** (drop it in behind
`OffTargetEngine`) and let Q-Guide do outcome reasoning, context adaptation, set optimization,
and explanation on top.

---

## Why context-aware prediction matters

A guide is never used "in the abstract" — it is delivered into a **specific cell type, organism,
and condition**. Editing efficiency and the *consequences* of an edit vary widely:

- **Cell state** — actively dividing stem cells / HEK293 edit far more efficiently than
  post-mitotic neurons; the "best" guide can flip between them.
- **Delivery** — transient **RNP** gives a sharp, low-off-target editing window; **lentivirus**
  gives sustained high expression with integration risk. The optimal guide differs.
- **Temperature** — some Cas enzymes and organisms (e.g. zebrafish, plants) edit at non-37 °C;
  efficiency falls off away from the enzyme's optimum.
- **Expression level** — abundance of Cas/sgRNA shifts the editing-vs-no-edit balance.

Q-Guide encodes these as **transparent JSON weighting rules** and exposes a **context-sensitivity
dashboard** so a scientist can see *Guide A wins in stem cells, Guide B wins in neurons* — instead
of a single context-blind number.

## Why biological outcome prediction matters

Cutting is a means, not the goal. A guide that cuts efficiently but produces a clean **in-frame**
indel may leave a **functional protein** — a failed knockout. What actually matters:

- **Frameshift vs in-frame** — only ~2⁄3 of NHEJ indels are frameshifting; the rest may preserve function.
- **Knockout probability** — the real endpoint for a loss-of-function screen.
- **Exon / domain disruption** — hitting a critical exon matters more than raw efficiency.
- **No-edit probability** — a guide can be "high scoring" yet rarely edit in the chosen context.

Q-Guide makes these the **primary ranking signal**, so recommendations are optimised for the
experiment's *biological objective*, not a cutting proxy.

## Why explainability matters

CRISPR experiments are expensive and slow. A scientist deciding between guides needs to **trust and
audit** the recommendation, not accept a black-box rank. For every guide Q-Guide answers:

1. Why was this guide selected? 2. Why above the others? 3. What raised its score?
4. What lowered it? 5. When would another guide win? 6. What assumptions were made?

> *"gRNA_045 was selected because it achieved the highest predicted knockout probability (87%)
> while maintaining low off-target risk (9%). Although gRNA_012 had slightly higher on-target
> efficiency, its elevated off-target risk and lower exon-disruption score reduced its final ranking."*

Explanations are **deterministic and template-driven** in V1 (auditable), with a clear path to
LLM-generated prose over the same structured facts.

---

## How quantum-inspired optimization is used

Choosing the best **set** of guides is a combinatorial problem: maximise editing success,
knockout probability, target coverage and context compatibility while minimising off-target
risk, redundancy and overlap. Q-Guide frames this as a **QUBO** (Quadratic Unconstrained
Binary Optimization):

```
minimise  xᵀ Q x      where  xᵢ ∈ {0,1}  selects guide i
```

- **Diagonal (linear) terms** reward each guide's multi-objective utility and encode the
  **set-size constraint** `P·(Σxᵢ − k)²`.
- **Off-diagonal (quadratic) terms** penalise **redundant pairs** — positional overlap,
  sequence similarity, and cut sites within 10 bp.

QUBO is the **native input format for quantum annealers** (D-Wave) and gate-model solvers
(QAOA via Qiskit, or Amazon Braket). **V1 solves the identical QUBO with classical simulated
annealing**, so swapping in a quantum backend is a drop-in `Optimizer` implementation — the
formulation, scoring, and explanations are unchanged. This gives a working product today and a
clean upgrade path to genuine quantum/hybrid optimization at scale (many loci × many guides).

---

## Project structure

```
qguide/
  app/
    main.py            FastAPI app entrypoint
    schemas.py         Pydantic data model + API contract (the shared interface)
    routes.py          REST endpoints (/design, /sensitivity, /enzymes, ...)
  core/
    guide_generator.py Step 1 — PAM scan, both strands, Cas registry
    scoring.py         Step 2 — modular biological scoring components
    off_target.py      Step 3 — heuristic off-target engine (swappable)
    outcome_prediction.py Step 4 — functional-outcome model (swappable)
    context_adjustment.py Step 5 — JSON-driven context re-weighting
    optimization.py    Steps 6 & 7 — multi-objective scoring + QUBO/annealing
    explainability.py  Step 10 — natural-language rationale
    visualization.py   Step 9 — Plotly figure builders
    pipeline.py        Orchestrator (generate → … → explain)
  config/
    context_weights.json  Editable context rules
  examples/
    example_sequence.txt
  tests/
    test_generation.py test_scoring.py test_prediction.py test_optimization.py
  frontend/
    streamlit_app.py   9-page UI (incl. Experiment Simulation) + 7-tab guide analytics
  requirements.txt
  README.md
```

---

## Future roadmap

**Off-target (genome-grounded specificity)**
- Plug Bowtie/BWA/BLAST or a CRISPOR-style aligner behind `OffTargetEngine`; real CFD/MIT scores.

**Outcome models (data-driven)**
- Replace the rule-based model with XGBoost / Random Forest, then Lindel/inDelphi-style indel
  prediction, and ultimately transformer genomic models — all behind `OutcomeModel`.

**Quantum optimization** — see the concrete plan in [docs/QUANTUM_INTEGRATION.md](docs/QUANTUM_INTEGRATION.md)
- The QUBO already exports to the canonical SDK format via `QUBO.to_qubo_dict()`. Drop-in `Optimizer`s
  for D-Wave Ocean (`dimod`/`neal` → `DWaveSampler`), Qiskit QAOA (Aer → IBM Quantum), and Amazon
  Braket consume it unchanged. Scale target: genome-wide, many-locus guide-set design via hybrid solvers.

**Cas systems & edit types**
- SaCas9, Cas12a (already in the registry), base editors and prime editors with edit-type-specific
  outcome models.

**Experiment simulation**
- The **Experiment Simulation** page is live: it re-runs the full pipeline across a chosen axis
  (Cas enzyme · cell type · delivery · temperature · objective) and compares predicted outcomes,
  via `pipeline.simulate_experiments` / the `/simulate` API. Next: full multi-axis combinatorial
  grids (Cas × condition × objective) and guide-combination co-editing simulation.

**Frontend**
- React migration consuming the existing FastAPI layer; the data model and Plotly figures already
  serialise to JSON, so the science is reused unchanged.

**Persistence & collaboration**
- Design history database, shareable reports, project workspaces.

---

## Disclaimer

Q-Guide V1 is a **research prototype**. Its biological scores, off-target estimates, and outcome
predictions come from **interpretable heuristics and rule-based models**, not wet-lab measurements
or genome-wide alignment. **Do not use V1 outputs for clinical or therapeutic decisions.** It is a
framework demonstrating context-aware, outcome-focused, explainable, optimization-driven guide
recommendation — with clearly marked upgrade paths to production-grade models.
