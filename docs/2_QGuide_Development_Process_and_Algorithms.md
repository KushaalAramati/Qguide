# Q-Guide — How We Built It & The Algorithms Behind the Calculations

**Author:** Kushaal Aramati
**Audience:** technical reviewers
**Purpose:** explain the development process and document every calculation the app does

> A note before I start: I designed all the scoring/prediction models in this version as
> **interpretable, rule-based models grounded in published CRISPR biology** — not models
> trained on wet-lab data. I'll give the actual formulas so anyone can check the logic.
> Where a model is a heuristic stand-in for something that should eventually be a trained
> model, I say so. I think that's the honest way to document a prototype.

---

## Part A — How the application came together

I built this in layers, getting each layer working before moving to the next.

**1. The scientific core first.** Before any web app, I wrote the pipeline as plain Python
modules and tested each one in isolation. The pipeline is a chain of independent stages:

```
generate guides → score → off-target → context → predict outcome
→ multi-objective score → optimize the set → explain
```

Keeping the stages independent (they only talk through a shared Pydantic data model, never
by importing each other) meant I could test and replace any one of them without breaking
the rest. I wired it to a quick Streamlit UI just to see results.

**2. Turned it into a real backend.** I rebuilt the data layer on SQLAlchemy (so it runs on
SQLite locally and PostgreSQL in production with no code change) and put a FastAPI REST API
on top: JWT login/signup, a credit-gated "run" endpoint, project storage, and admin
endpoints. Passwords are hashed with salted PBKDF2-HMAC-SHA256.

**3. Built the web frontend.** A Next.js + TypeScript + Tailwind app: login, account,
buy-credits, the new-project form, and the results dashboard. Charts are done with Recharts.

**4. Added the extras.** Admin panel, CSV export, the experiment-outcome simulator, and the
interactive 3D visualizers (React Three Fiber + Three.js).

**5. Deployed it.** Backend + Postgres on Render, frontend on Vercel, source on GitHub. I
wrote a test suite along the way (63 automated tests covering auth, credits, the admin
gating, and the pipeline) and ran it before each deploy.

The whole thing is structured so the *science* is swappable: there are clean interface
points (an `OffTargetEngine` interface, an `OutcomeModel` interface, a scoring-component
registry, and an `Optimizer` interface). That's deliberate — it's how a heuristic gets
replaced by a trained model later without touching the app.

---

## Part B — The algorithms, stage by stage

Notation: a candidate guide has a spacer sequence (e.g., 20 nt for SpCas9), a PAM, a
strand, and a genomic position. Most component scores are normalized to `[0, 1]`.

### B.1 Guide generation
- I expand the PAM (e.g., `NGG`) into a regular expression using the **IUPAC ambiguity
  codes** (`N → [ACGT]`, `R → [AG]`, etc.) and scan the sequence for matches.
- I scan **both strands** — the reverse strand is handled by reverse-complementing the
  sequence, scanning it, and mapping coordinates back to the forward frame.
- For each PAM hit, the protospacer is the adjacent window (upstream for Cas9-type 3′
  PAMs, downstream for Cas12a-type 5′ PAMs). Each enzyme is described by a small
  `CasProfile` (PAM, guide length, PAM side, cut offset) so adding enzymes is a one-line
  change.
- I record GC content, the approximate cut site, and the distance from the target center.

### B.2 Biological scoring (the on-target score)
Each component is a small function returning `[0, 1]`. The ones I implemented:

- **GC content score** — a triangular preference peaking at 50% GC:
  `gc_score = max(0, 1 − |GC − 0.5| / 0.5)`. (Extreme GC hurts folding/cutting.)
- **Complexity score** — the **Shannon entropy** of the spacer, normalized to its
  2-bit max: `H = −Σ p(b)·log₂ p(b)`, `complexity = min(1, H/2)`. Low-complexity spacers
  are penalized.
- **Homopolymer penalty** — penalizes long single-base runs, with an extra penalty for a
  poly-T tract (poly-T can prematurely terminate Pol-III transcription of the sgRNA).
- **Secondary-structure penalty** — a cheap proxy for self-folding: I count how many of
  the spacer's k-mers (k=4) have their reverse-complement also present, i.e., how much the
  spacer can base-pair with itself. (A production version would call ViennaRNA; this is a
  stand-in.)
- **Distance-to-target score** — exponential decay with distance from the target center:
  `exp(−distance / 50)`.
- **Sequence-quality score** — penalizes Ns, extreme GC, and long runs.

The composite **on-target score** is a weighted sum of the positive components minus the
penalty components, then clamped to `[0, 1]`. The weights are explicit constants (so the
contribution of each term is transparent), e.g., sequence quality 0.30, GC 0.20, PAM 0.20,
complexity 0.15, distance 0.15, minus structure/homopolymer penalties.

### B.3 Off-target analysis (heuristic, V1)
With no genome index available in this version, I estimate off-target risk from intrinsic
properties of the spacer that correlate with promiscuity:

- **Seed repetitiveness** — fraction of repeated dinucleotides in the PAM-proximal "seed"
  region (last ~10 nt), which dominates Cas9 specificity.
- **Low complexity** — `1 − normalized_entropy` (low-complexity guides hit more places).
- **Repetitive motifs** — longest tandem repeat of period 1–3.

These are blended (seed weighted highest at 0.45, complexity 0.35, repeats 0.20) into a
risk score in `[0, 1]`, bucketed into low/moderate/high, and used to synthesize a plausible
mismatch distribution for the dashboard. **This is the weakest part scientifically and the
first thing I'd replace** — see the future-plans document (real alignment + CFD score).

### B.4 Functional outcome prediction (rule-based, grounded in NHEJ biology)
This is the part I'm most interested in. For each guide I predict the probabilities of
frameshift / in-frame indel / no-edit / knockout / exon disruption.

- Probability that *any* edit happens scales with on-target efficiency **and** an
  experimental-context factor:
  `edit_prob = clamp((0.15 + 0.80·on_target) · efficiency, 0.02, 0.98)`,
  `no_edit = 1 − edit_prob`.
- Of the edits, the **frameshift fraction** starts from the published NHEJ prior (~2/3 of
  indels are frameshifting) and is pulled down toward predictable in-frame deletions when
  there's microhomology around the cut: `frameshift_fraction = max(0.45, 0.66 − 0.25·MH)`,
  where `MH` is a microhomology proxy (complementarity of the flanks around the cut).
- **Knockout probability** = all frameshifts + a fraction (~20%) of in-frame edits that
  still disrupt function: `knockout = frameshift + 0.20·in_frame`.
- The composite **functional-disruption score** is then weighted toward whatever the user
  selected (knockout vs deletion vs exon targeting), so the ranking matches the objective.

I want to be clear this is a *rule-based prior*, not a learned indel model — the right
production version is something like inDelphi/Lindel (covered in future plans).

### B.5 Context adjustment
Experimental context is encoded as **multiplicative weights in a JSON config** (so changing
the biology is a config edit, not a code change). Organism, cell type, Cas enzyme, delivery
method, and expression level each contribute a multiplier; temperature uses a falloff around
the enzyme optimum: `mult = clamp(1 − |T − 37| · 0.02, 0.70, 1.05)`. The combined factor
feeds the outcome model (so, e.g., neurons get a lower predicted edit rate than HEK293), and
enzyme/organism factors also scale the off-target risk (so a high-fidelity variant reads as
lower risk).

### B.6 Multi-objective final score
The final 0–1 score per guide is a weighted combination of the **positives** (on-target,
knockout probability, functional disruption, context compatibility, sequence quality) minus
the **negatives** (off-target risk, structure penalty, GC imbalance), then normalized. The
full signed breakdown is stored so the app can explain exactly what helped and hurt.

### B.7 Quantum-inspired set optimization (QUBO + simulated annealing)
Picking the best *set* of N guides isn't just "take the top N" — you want coverage without
redundancy. I framed it as a **QUBO** (Quadratic Unconstrained Binary Optimization):

minimize `xᵀ Q x`, where `xᵢ ∈ {0,1}` means "include guide i."

- **Diagonal (linear) terms** reward each guide's utility and encode the set-size
  constraint by expanding `P·(Σxᵢ − k)²`.
- **Off-diagonal (quadratic) terms** penalize redundant *pairs* — guides that overlap
  positionally, have similar sequences, or have cut sites within 10 bp.

I solve it with **simulated annealing**: start from a greedy warm-start, then repeatedly
flip a bit and accept the change if it lowers the energy, or with probability
`exp(−ΔE / T)` if it raises it, cooling `T` on a geometric schedule. I used a seeded RNG so
runs are reproducible. I also added a **D-Wave (`dimod`) backend** that consumes the exact
same QUBO — and I verified it returns the same optimum as brute force on small instances. At
this problem size simulated annealing already finds the global optimum, so the quantum path
is really there for future scale (genome-wide / library design), not because it beats
classical today.

### B.8 Experiment outcome simulation (Monte Carlo)
For a chosen guide, I simulate a virtual **diploid** cell population:
- Per-allele loss-of-function probability `p_d = frameshift + 0.20·in_frame`.
- Across `R` replicate "dishes," I add biological variability (efficiency ~ Normal(1, CV))
  and draw the number of knocked-out cells from a **Binomial(n_cells, p_d²)** (both alleles
  disrupted), giving a knockout-rate distribution → mean and 95% CI from percentiles.
- Genotype mix from Hardy-Weinberg-style terms: WT `(1−p_d)²`, het `2p_d(1−p_d)`, KO `p_d²`.
- A synthesized **indel spectrum** (dominant +1 bp insertion, a tail of small deletions, and
  a microhomology-driven deletion peak).

This is illustrative (it propagates the model's own probabilities with noise), not a
wet-lab-validated simulator — but it's a useful way to turn single numbers into "here's the
distribution you'd expect."

### B.9 Explainability
Finally, each guide gets a templated natural-language explanation generated from its score
breakdown — what raised its score, what lowered it, how it compares to the runner-up, and
under what conditions a different guide would win. It's deterministic (auditable), and the
same structured facts could later be sent through an LLM for richer prose.

---

## Part C — Testing and reproducibility

- **63 automated tests** (pytest) cover guide generation geometry, the scoring components,
  the outcome model, the QUBO/optimizer (including that the optimizer is deterministic and
  the D-Wave backend matches the exact optimum), the experiment simulator, and the full
  REST API (auth, credit gating, admin).
- The optimizer uses a fixed seed, so the same input always yields the same guide set.

---

## Part D — Honest summary of the math

Everything in this version is **transparent and rule-based**, chosen from known CRISPR
biology and standard techniques (Shannon entropy, exponential distance decay, NHEJ indel
priors, QUBO/simulated annealing, binomial Monte Carlo). That makes it easy to audit and
easy to upgrade. The clearly-marked next step is to replace the heuristic scorers with
models trained and validated on real data — the architecture was built specifically to make
that a drop-in change.
