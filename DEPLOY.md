# Deploying Q-Guide to Streamlit Community Cloud

A free, public URL you can share with testers. ~10 minutes.

## What's already prepared
- `requirements.txt` (repo root) — the exact deps the app needs.
- `.streamlit/config.toml` — the purple theme.
- `.python-version` → 3.12.
- `.gitignore` — keeps the venv, logs, and the runtime SQLite DB out of git.
- SQLite persistence (`qguide/app/store.py`) — accounts, **hashed** passwords,
  credits, the transaction ledger and projects survive refreshes.

## Step 1 — Put the code on GitHub
From `D:\guideRna` (already a git repo with an initial commit):

```bash
# create an EMPTY repo on github.com first (e.g. "q-guide"), then:
git remote add origin https://github.com/<your-username>/q-guide.git
git branch -M main
git push -u origin main
```

(If you prefer, GitHub Desktop → "Add existing repository" → `D:\guideRna` → Publish.)

## Step 2 — Deploy on Streamlit Community Cloud
1. Go to **https://share.streamlit.io** and sign in with GitHub.
2. **Create app → Deploy a public app from a repo.**
3. Fill in:
   - **Repository:** `<your-username>/q-guide`
   - **Branch:** `main`
   - **Main file path:** `qguide/frontend/streamlit_app.py`
4. **Advanced settings → Python version: 3.12.**
5. Click **Deploy**. First build takes a few minutes (it compiles dimod/dwave-samplers).

You'll get a URL like `https://<your-app>.streamlit.app` — share that with testers.

## Notes for testers
- **Accounts persist** while the app instance is alive (survive refresh; each tester
  signs up once, balance is remembered). A full host reboot (long inactivity) clears
  the on-instance DB — for permanent storage, move to a hosted Postgres later.
- **Sign-in is required**; a new account gets **25 free credits**; each design run
  costs **5 credits**. The **Buy Credits** checkout is **simulated** (no real charge).
- Passwords are salted + PBKDF2-hashed, but this is a **prototype** — don't use real
  passwords.

## Updating the live app
Push to `main` and Streamlit Cloud redeploys automatically:
```bash
git add -A && git commit -m "..." && git push
```

## Alternative: run it for someone quickly without deploying
From `D:\guideRna`: double-click `run.bat`, then share your machine's
`http://<your-ip>:8501` (same Wi‑Fi) or a tunnel (`cloudflared tunnel --url http://localhost:8501`).
