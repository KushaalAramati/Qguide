# Q-Guide — Future Plans & Roadmap

**Author:** Kushaal Aramati
**Status of the project today:** working prototype, deployed, end-to-end
**Purpose:** lay out what I'd build next and in what order

---

## How I'm thinking about priorities

The current version proves out the *whole platform* — the pipeline, the web app, accounts,
admin, and deployment all work. The honest gap is **scientific accuracy**: the scoring and
prediction models are interpretable heuristics, and there's no genome-wide off-target
search yet. So the roadmap is organized around one idea:

> The platform is built; the next phase is making the *numbers* trustworthy by replacing
> heuristics with models trained and validated on real experimental data — and the
> architecture was designed so each of these is a drop-in swap, not a rewrite.

I've split this into four tracks and ranked them by impact-per-effort.

---

## Track 1 — Scientific accuracy (the most important work)

This is where I'd spend most of the effort, because it's what would make Q-Guide's results
genuinely competitive with established tools.

**1.1 Trained on-target efficiency model (quick, high-value).**
Replace the heuristic on-target score with a published, benchmarked model — **Doench Rule
Set 2 (Azimuth)** — which is a gradient-boosted model trained on thousands of measured
guides. This is "code-only" (it needs the 30-mer sequence context we already have, no
genome), so it can ship on the current free infrastructure. *Effort: low. Accuracy gain:
high.*

**1.2 Data-driven outcome model.**
Replace the rule-based NHEJ prior with a real indel-prediction model — **inDelphi, Lindel,
or FORECasT** — which are trained on measured indel spectra and predict the actual
distribution of edits (and therefore a real knockout probability) per guide. This makes the
"functional outcome" feature — the thing that differentiates Q-Guide — actually accurate.
*Effort: medium. Accuracy gain: high.*

**1.3 Genome-grounded off-target analysis (the biggest single gap).**
This is the largest scientific improvement and the hardest. Properly, you align each guide
against a reference genome (BWA/Bowtie), enumerate near-matches, and score each site with
the **CFD (Cutting Frequency Determination)** and/or **MIT specificity** scores, which were
derived from measured cleavage data.
- *Phase A (deployable now):* real alignment against a **provided/small reference** (a
  plasmid, amplicon, or small genome like *E. coli*/yeast, or a user-uploaded FASTA). This
  is real CFD-scored off-target search, just scoped to references that fit in memory — and
  it already covers a lot of real use cases.
- *Phase B (needs infrastructure):* genome-wide search for human/mouse. A human genome
  index is several GB of RAM, which the free hosting tier can't hold. Options, cheapest
  first: (1) call an external genome off-target API and host nothing, (2) stand up a paid
  worker with a prebuilt index + persistent disk, (3) keep precomputed indexes in cloud
  storage. I'd start with option 1.

**1.4 Validation / benchmarking (this is what lets us *claim* accuracy).**
Build a benchmark harness that runs predictions against held-out public datasets and reports
a number — correlation/AUC of predicted vs measured efficiency, and overlap of predicted
off-targets with experimental sets (GUIDE-seq / CIRCLE-seq). Without this we can only *say*
it's accurate; with it we can *show* it. *I'd do this in parallel with 1.1–1.2 so every model
change comes with a measured improvement.*

**1.5 Gene-structure awareness.**
To honestly claim "this disrupts the gene," the app needs the gene's structure — which
exon/isoform the cut lands in and whether it hits a functional domain. That means pulling in
genome coordinates + annotations rather than working off a pasted sequence alone.

**Suggested order:** 1.1 → 1.2 → 1.4 (benchmark) → 1.3 (Phase A) → 1.5 → 1.3 (Phase B).

---

## Track 2 — The quantum optimization path

The optimizer is already a QUBO with a D-Wave (`dimod`) backend, so the structure is ready.
Honest assessment:
- At today's problem sizes (one locus, tens-to-hundreds of guides), classical simulated
  annealing already finds the global optimum, so real quantum hardware gives **no practical
  advantage** yet.
- It becomes interesting only at large scale — **genome-wide / many-loci or multiplexed
  library design** — where the QUBO gets big and dense. Even then, current quantum hardware
  hasn't clearly beaten good classical solvers, so I'd treat it as a research/forward-looking
  feature, not an accuracy lever.

**Plan:** keep the QUBO formulation as the standard interface; add a real D-Wave Leap (and/or
Qiskit QAOA) path so we can demo "running on a quantum annealer," and revisit it seriously
only when we're solving genome-scale set-selection problems. I would *not* claim quantum
makes the biological predictions more accurate — it optimizes the same model's output.

---

## Track 3 — Product & platform features

- **More CRISPR systems:** finish first-class support for SaCas9, Cas12a, and add **base
  editors and prime editors** (with edit-type-specific outcome models).
- **FASTA upload + reference selection** in the UI (needed for Track 1.3 Phase A).
- **Reports / export:** a polished PDF report per design (already have CSV export).
- **Full table UX:** server-side sort/filter/search/pagination on the rankings table for
  large guide sets.
- **Real payments:** swap the simulated checkout for Stripe (the credit system is already
  structured for it).
- **Standalone visualizer pages & Off-Target Analysis page** as dedicated routes (the 3D
  engine is built; this is mostly layout/IA work).
- **Collaboration:** shareable projects, team workspaces, and an audit trail.

---

## Track 4 — Engineering & operations

- **Frontend auto-deploy:** finish wiring the Vercel project to GitHub so every push deploys
  both backend (already automatic on Render) and frontend without a manual step.
- **Durable database & backups:** move off the free Postgres tier for anything beyond
  testing, with scheduled backups.
- **Lock down CORS** to the production frontend domain, add rate limiting, and add proper
  secrets management.
- **CI:** run the test suite automatically on every push before deploy.
- **Monitoring & logging** for the live services.

---

## A realistic near-term plan (if I had the next few weeks)

1. **Doench Rule Set 2** on-target model + a **benchmark harness** → first measurable
   accuracy jump, fully deployable now.
2. **inDelphi/Lindel** outcome model → makes the headline "outcome prediction" feature real.
3. **Phase-A real off-target** (CFD on a provided reference) + **FASTA upload**.
4. **Stripe** + **frontend auto-deploy** + **CI** → make it a real product people can pay
   for and that ships safely.

Everything after that (genome-wide off-target, base/prime editors, gene-structure awareness,
serious quantum) is bigger and would depend on what users actually need and what
infrastructure budget is available.

---

## One-paragraph summary for the busy reader

The platform is done; the next phase is accuracy. The single highest-value moves are
swapping the heuristic on-target and outcome scorers for **validated, trained models
(Doench Rule Set 2, inDelphi/Lindel)** and adding a **benchmark harness** to prove the
improvement — all of which deploy on what we already have. The biggest scientific gap,
**genome-grounded off-target search (CFD)**, comes next and needs some infrastructure. The
quantum path is real and future-proof but is a scaling story, not an accuracy one. The
architecture was deliberately built with swappable interfaces so all of this slots in
without rebuilding the application.
