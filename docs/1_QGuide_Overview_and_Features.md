# Q-Guide — Application Overview & Features

**Author:** Kushaal Aramati
**Project:** Q-Guide — a context-aware guide-RNA recommendation platform for CRISPR
**Status:** Working prototype (deployed and usable)
**Last updated:** June 2026

---

## 1. What this project is (in one paragraph)

Q-Guide is a web application that helps a researcher design guide RNAs (gRNAs) for
CRISPR experiments. You paste in a DNA sequence, pick your Cas enzyme and what you're
trying to achieve (e.g., knock out a gene), and the app generates candidate guides,
scores them, predicts what the edit will actually do, and ranks them — with a written
explanation for *why* each guide ranked where it did. There's also an interactive 3D
viewer so you can actually look at the guide RNA and the DNA binding region.

I want to be upfront about one thing from the start: this is a **prototype**. The
scoring and prediction models are interpretable, rule-based models (not yet trained on
wet-lab data), and the off-target check is a heuristic rather than a full genome search.
I'll be specific about that throughout, because I think honesty about the limits is more
useful than overselling it. The point of this version was to build the *whole platform
end-to-end* — the science pipeline, the web app, accounts, and deployment — so that the
individual models can later be swapped for production-grade ones without rebuilding
everything.

---

## 2. The problem I was trying to solve

Most existing tools (CHOPCHOP, CRISPOR, Benchling) answer the question **"which guide
cuts the best?"** That's useful, but it's not the question a biologist actually has. The
real question is usually **"which guide gives me the *outcome* I want, in *my* specific
experiment?"** A guide can cut very efficiently but still produce an in-frame edit that
leaves a working protein — which means the knockout *failed*, even though the "cutting
score" was great.

So the idea behind Q-Guide is to optimize for the **predicted biological outcome and the
user's objective**, while also taking the **experimental context** (cell type, delivery
method, temperature, enzyme) into account — and to *explain itself* instead of being a
black-box ranking.

---

## 3. Who it's for

- Academic labs and grad students planning CRISPR knockouts/edits
- Biotech startups that want a faster first-pass guide selection
- Honestly, also me — it started as a way to learn bioinformatics, full-stack
  development, and a bit of optimization theory in one project.

---

## 4. Main features

### 4.1 Accounts, credits, and admin
- **Sign up / log in** (JWT auth, passwords are salted + hashed — never stored in plain
  text). New accounts get **25 free credits**.
- **Credit system:** each full design run costs **5 credits**. Running is blocked when
  you hit zero, with a prompt to buy more. The "Buy Credits" checkout is **simulated**
  for now (no real payment) but is structured so a real processor like Stripe can drop in.
- **Admin panel** (restricted to allow-listed emails): see every user (name, email,
  credits, number of runs, signup date, last login), change anyone's credit balance, and
  export everything as a CSV. This was important so the platform can actually be managed.

### 4.2 Guide RNA design (the core workflow)
1. Enter a DNA sequence (FASTA headers are handled).
2. Pick the CRISPR system (SpCas9, SaCas9, Cas12a, etc.) and your desired outcome
   (knockout, gene disruption, exon targeting, deletion, custom).
3. Optionally add experimental context: organism, cell type, delivery method, temperature.
4. Hit **Run** — the pipeline generates candidates, scores them, predicts outcomes,
   applies context, and runs the optimization.

### 4.3 Results dashboard
- A **ranked, color-coded table** of candidate guides with sequence, PAM, position,
  strand, on-target score, knockout probability, off-target risk, and a final score.
- A **"Selected Guide" panel** with a full score breakdown and a plain-English
  **"Why this guide?"** checklist.
- An **optimized guide set** (not just the single best guide — the best *combination*),
  with the reasons each guide was chosen and why alternatives were rejected.
- **Outcome charts** (frameshift / in-frame / no-edit pie, knockout/exon bars, radar).
- **CSV export** of all results, so you can take it into Excel or a lab notebook.

### 4.4 Experiment outcome prediction
For any guide (even the worst-ranked one), you can run a **Monte-Carlo simulation** of a
virtual cell population. It predicts the editing efficiency, the biallelic knockout rate
with a 95% confidence band, the genotype mix (wild-type / heterozygous / knockout), and a
predicted indel spectrum. This is meant to answer "okay, but what would my dish actually
look like?"

### 4.5 Context sensitivity & experiment simulation
You can re-run the same design across different conditions (Cas enzyme, cell type,
delivery, temperature, objective) and see how the predicted result changes. For example,
the same guide is predicted to knock out ~57% in neurons vs ~69% in HEK293 cells — the app
makes that difference visible instead of giving one context-blind number.

### 4.6 Interactive 3D visualization (the newest part)
- **3D guide-RNA molecular viewer:** the nucleotides are drawn as colored spheres on a
  helical backbone (A=green, U=yellow, C=blue, G=red). You can rotate, zoom, pan, auto-
  rotate, reset, go fullscreen, and take a screenshot. Hovering a base shows its position;
  clicking it opens a detail panel.
- **DNA double-helix viewer:** shows the binding region as a rotating double helix
  (A=green, T=orange, C=blue, G=red) with the protospacer and PAM highlighted.
- **Linear sequence map:** a clickable overview of the whole sequence showing where every
  candidate guide binds. Clicking a marker loads that guide into the 3D viewers.
- Everything is linked: selecting a guide updates the molecule, the helix, and the
  analytics panel together.

It uses React Three Fiber and Three.js for GPU-accelerated rendering. I'll be honest that
the 3D structure is a *stylized* representation (a helix with correctly colored bases),
not a physics-accurate predicted fold — but it's genuinely interactive and useful for
inspecting the sequence visually.

---

## 5. How it's different from existing tools

| | Typical tools (CHOPCHOP/CRISPOR) | Q-Guide |
|---|---|---|
| Main question | "Which guide cuts well?" | "Which guide achieves my *outcome*?" |
| Outcome prediction | Efficiency proxy | Frameshift / knockout / exon-disruption probabilities |
| Experimental context | Not modeled | Cell type, delivery, temperature, enzyme re-weight the ranking |
| Selection | A ranked list | A ranked list **+ an optimized guide set** |
| Explanation | A score table | A written reason for every choice |
| Visualization | 2D tracks | Interactive 3D molecule + DNA helix |

**The honest caveat:** Q-Guide is differentiated in *approach and experience*, not yet in
validated raw accuracy. Tools like CRISPOR do real genome-wide off-target search and use
published, benchmarked efficiency models — so for pure accuracy today, they're ahead. The
plan (next document) is to plug those kinds of validated models into Q-Guide's existing
architecture.

---

## 6. Technology used

- **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, JWT auth. Scientific core in
  pure Python/NumPy.
- **Frontend:** Next.js (React), TypeScript, TailwindCSS, Recharts, React Three Fiber /
  Three.js (for 3D).
- **Optimization:** a QUBO formulation solved with simulated annealing, with a D-Wave
  (dimod) backend wired in for the quantum-annealing path.
- **Deployment:** backend + Postgres on Render, frontend on Vercel, code on GitHub.

---

## 7. Current limitations (being honest)

- Scoring and outcome models are rule-based/heuristic, not trained on experimental data.
- Off-target analysis is a heuristic estimate; there is no genome-wide alignment yet.
- The "Buy Credits" payment is simulated.
- The 3D structures are stylized, not predicted folds.

None of these are hidden in the app — there's a disclaimer banner, and the "assumptions"
are listed. I'd rather it be trusted for what it is than oversold.

---

## 8. Summary

Q-Guide is a complete, working CRISPR guide-design platform that reframes the problem
around *biological outcome and experimental context*, explains its recommendations, and
makes them visually explorable in 3D — built as a real full-stack product (accounts,
credits, admin, deployment) so that the underlying models can be upgraded to
production-grade without rebuilding the platform.
