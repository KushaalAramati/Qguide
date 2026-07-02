# Q-Guide — project guide for Claude Code

Q-Guide is an **outcome-first, explainable, context-aware CRISPR guide-RNA design and
optimization** platform. It's a deployed web app: **FastAPI + PostgreSQL backend (Render)**
and a **Next.js frontend (Vercel)**. The differentiator is not "which guide cuts best" but
"what outcome will I get, why this guide, how confident, and which guide *set* is best" —
via ensemble scoring + quantum-inspired multi-guide selection.

> Honesty rule: scoring/outcome models are **interpretable heuristics** (not trained on
> wet-lab data) and off-target is heuristic (no genome alignment). Provisional components
> are flagged in code and UI. Never present predictions as validated/clinical.

## Read first
- `docs/1_QGuide_Overview_and_Features.md`, `docs/2_QGuide_Development_Process_and_Algorithms.md`,
  `docs/3_QGuide_Future_Plans_and_Roadmap.md`
- `DEPLOY.md` (deploy runbook)

## Layout
- `qguide/core/` — scientific pipeline: generate → score → off_target → context → outcome →
  **ensemble** → optimize → explain. Key modules: `ensemble.py` (named-component
  `final_qguide_score` with goal profiles × risk tolerance), `outcome_modes.py` (pluggable
  OutcomeMode registry), `off_target.py` (per-hit report + genome-engine stub), `optimization.py`
  (QUBO + simulated annealing + D-Wave `dimod`; modes classical/quantum_inspired/quantum_hardware;
  Top-N-vs-set comparison), `benchmark.py`, `report.py`, `pipeline.py` (orchestrator).
- `qguide/app/` — FastAPI: `routes.py` (auth/credits/projects/run/admin + `/report` `/benchmark`
  `/optimizer/modes`), `schemas.py` (Guide has `ensemble: EnsembleScore`), `store.py` (SQLAlchemy
  via `DATABASE_URL`, hashed passwords), `auth.py` (JWT), `billing.py`.
- `web/` — Next.js 14 + TS + Tailwind. `components/Ensemble.tsx` (score breakdown / off-target
  hits / optimizer comparison), `components/viz/` (React-Three-Fiber 3D guide + DNA helix + map).
- `qguide/frontend/streamlit_app.py` — the original Streamlit UI (still works).

## Run / test (from repo root `D:\guideRna`)
- Tests: `.venv\Scripts\python.exe -m pytest`  (**77 passing**)
- API: `.venv\Scripts\python.exe -m uvicorn qguide.app.main:app --reload --port 8000`  (`/docs`)
- UI: `cd web && npm run dev`  (set `web/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8000`)
- DB: SQLite locally (`DATABASE_URL` unset), Postgres in prod.

## Deploy (the recurring gotcha)
- **Backend auto-deploys to Render** on every push to `main`. Verify: https://qguide-api.onrender.com/health
- **Frontend (Vercel) does NOT reliably auto-deploy** — the live site is stale and CLI `vercel deploy`
  keeps stalling. Fix (user, dashboard, once): connect the Vercel `web` project to GitHub with
  **Root Directory = `web`**. Don't loop on one-off CLI deploys.
- Commit to `main` (that's what deploys). Commit author = GitHub no-reply email.

## Conventions
- Keep changes **additive** and tested; run pytest before committing.
- Windows: use the **Bash tool `rm`** for cleanup (PowerShell `Remove-Item` is guarded under `D:\guideRna`).
- Scoring/off-target/outcome/optimizer all have **swappable interfaces** — add real models there.

## Next up — accuracy roadmap (in order)
1. **Doench Rule Set 2** on-target model (code-only, validated) — start here.
2. inDelphi/Lindel outcome model behind `OutcomeMode`.
3. Benchmark harness vs a public dataset (prove accuracy).
4. Genome-backed off-target + CFD behind `GenomeAlignmentOffTargetEngine` (Phase A = provided reference).
