# QGuide — Local demo (self-contained, no cloud needed)

Runs entirely on your machine: FastAPI backend on **:8000** (SQLite, no Postgres),
Next.js UI on **:3000**, and the UI is pointed at the LOCAL backend (so it does NOT
depend on Render/Vercel — which is why it works even when the cloud deploy is down).

## Prerequisites (one time)
- **Python 3.10+**  and  **Node.js 18+** installed and on PATH.
- A Python venv is optional. If `.venv` exists it's used automatically; otherwise the
  script installs into your system Python.

## Start it (two windows)
1. Double-click **`run_backend.bat`**  → wait for `Application startup complete` and
   "Uvicorn running on http://127.0.0.1:8000". Leave this window open.
2. Double-click **`run_frontend.bat`** → first run installs UI deps (a few minutes),
   then prints "ready on http://localhost:3000". Leave this window open.
3. Open **http://localhost:3000** in your browser.

(Prefer a terminal? Backend: `python -m uvicorn qguide.app.main:app --port 8000`
from the repo root. Frontend: `cd web && npm run dev`.)

## Do this for the demo (2 minutes)
1. **Create account** on the login screen → you get **25 free credits**
   (25 = 5 runs). The email `hnreddy@biovaram.com` is the admin, so signing up with it
   also unlocks the Admin page.
2. **New project** → paste a DNA sequence (any ACGT string ~60–200 bp works), pick
   knockout, choose a QUBO preset, run (costs 5 credits).
3. Walk the result: **Basic Results → Guide Rankings → Best Guide Set** (preset + set
   metrics) **→ Outcome → Compare → 3D Visualizer → Simulation → Ensemble breakdown**.
4. Show **folders** (sidebar: New folder, drag a project's ⋯ menu → Move), the
   **account sections**, and the **admin page**.

## Troubleshooting
- **UI loads but nothing works / login fails:** the backend window isn't running, or
  `web/.env.local` isn't `NEXT_PUBLIC_API_URL=http://localhost:8000`. Both scripts set
  this for you; restart `run_frontend.bat` after changing it.
- **Port already in use:** close the other process, or change `--port 8000`
  (and update `web/.env.local` to match).
- **`python` not found:** install Python and re-open the terminal, or edit the first
  lines of `run_backend.bat` to point at your Python.
- **Backend dependency errors:** from the repo root run
  `python -m pip install -r requirements-api.txt`.
- Data lives in `qguide_data.db` (SQLite) in the repo root; delete it to reset the demo.

## Notes
- Optional D-Wave/quantum-inspired optimizer packages (`dimod`, `dwave-samplers`) are
  in `requirements-api.txt`; if not installed the optimizer falls back to the classical
  solver automatically — the demo still works.
- This is a research demo: scores are interpretable heuristics and off-target is
  heuristic (no genome alignment) — computational predictions requiring validation.
