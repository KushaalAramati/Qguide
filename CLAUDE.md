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
- `docs/UPGRADE_REPORT.md` + `docs/UPGRADE_CHECKLIST.md` (the SaaS layer: auth, roles,
  collaboration, research tools, notifications, legal)

## Layout
- `qguide/core/` — scientific pipeline: generate → score → off_target → context → outcome →
  **ensemble** → optimize → explain. Key modules: `models.py` (Stage A model-adapter registry: named on-target/specificity/repair models with real/heuristic/provisional kinds; unavailable ML models abstain — feeds real cross-model agreement + per-model breakdown into the ensemble), `ensemble.py` (named-component
  `final_qguide_score` with goal profiles × risk tolerance; now also emits `model_scores`, `limitations`, `rationale`), `outcome_modes.py` (pluggable
  OutcomeMode registry), `off_target.py` (per-hit report + genome-engine stub), `optimization.py`
  (QUBO + simulated annealing + D-Wave `dimod`; modes classical/quantum_inspired/quantum_hardware;
  Top-N-vs-set comparison), `benchmark.py`, `report.py`, `pipeline.py` (orchestrator).
- `qguide/app/` — FastAPI: `routes.py` (auth/credits/projects/collaboration/notifications/admin +
  `/report` `/benchmark` `/optimizer/modes`), `research.py` (research tools router), `schemas.py`
  (Guide has `ensemble: EnsembleScore`), `store.py` (SQLAlchemy via `DATABASE_URL`, hashed
  passwords), `auth.py` (JWT), `access.py` (project OWNER/EDITOR/VIEWER authorisation),
  `roles.py` (app roles + permissions), `migrations.py` (versioned schema migrations),
  `branding.py` (product identity — never hardcode the name), `legal.py`, `emailer.py`,
  `ratelimit.py`, `billing.py`.
- `web/` — Next.js 14 + TS + Tailwind. `lib/branding.ts` (product identity), `lib/nav.ts`
  (sidebar), `components/Shell.tsx` + `Sidebar.tsx` (chrome), `components/Ensemble.tsx` (score
  breakdown / off-target hits / optimizer comparison), `components/viz/` (React-Three-Fiber 3D
  guide + DNA helix + map), `components/research/` (batch / templates / compare / history).
- `qguide/frontend/streamlit_app.py` — the original Streamlit UI (still works; legacy prototype).

## Run / test (from repo root `D:\guideRna`)
- Tests: `.venv\Scripts\python.exe -m pytest`  (**192 passing**)
- API: `.venv\Scripts\python.exe -m uvicorn qguide.app.main:app --reload --port 8000`  (`/docs`)
- UI: `cd web && npm run dev`  (set `web/.env.local` → `NEXT_PUBLIC_API_URL=http://localhost:8000`)
- DB: SQLite locally (`DATABASE_URL` unset), Postgres in prod. Schema changes go in
  `qguide/app/migrations.py` (append a numbered `Migration`; never edit a shipped one).
- Env: see `.env.example`; production boot refuses the dev `JWT_SECRET` / `ALLOWED_ORIGINS=*`.
  Locally set `QGUIDE_DEV_EMAIL=1` to see reset links without SMTP.

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
- Every project route goes through `access.require_project()`; every privileged action is
  enforced server-side (the UI hiding a button is never the control).
- Product name / support email / legal entity come from `branding.py` / `lib/branding.ts`.

## Next up — accuracy roadmap (in order)
1. **Doench Rule Set 2** on-target model (code-only, validated) — start here.
2. inDelphi/Lindel outcome model behind `OutcomeMode`.
3. Benchmark harness vs a public dataset (prove accuracy).
4. Genome-backed off-target + CFD behind `GenomeAlignmentOffTargetEngine` (Phase A = provided reference).
