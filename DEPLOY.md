# Deploying Q-Guide — FastAPI on Render + Next.js on Vercel

Architecture:
- **Backend** (FastAPI + Postgres) → **Render** (`render.yaml` blueprint)
- **Frontend** (Next.js) → **Vercel** (`web/` directory)

Both are free-tier friendly. You'll need a GitHub account, a Render account, and a
Vercel account (all free).

---

## Step 0 — Push the code to GitHub
From `D:\guideRna` (already a git repo):

```bash
git branch -M main          # if you want main as default
# create an EMPTY repo at github.com/new (e.g. "q-guide"), then:
git remote add origin https://github.com/<your-username>/q-guide.git
git push -u origin main
```
(Or GitHub Desktop → Add existing repo → `D:\guideRna` → Publish.)

---

## Step 1 — Backend on Render (FastAPI + Postgres)
1. Go to **https://dashboard.render.com** → **New + → Blueprint**.
2. Connect your GitHub repo. Render reads **`render.yaml`** and proposes:
   - a **web service** `qguide-api` (build `pip install -r requirements-api.txt`,
     start `uvicorn qguide.app.main:app --host 0.0.0.0 --port $PORT`)
   - a **Postgres** database `qguide-db`
   - `JWT_SECRET` (auto-generated) and `DATABASE_URL` (wired from the DB)
3. Click **Apply**. First build takes a few minutes.
4. When live, note the URL, e.g. **`https://qguide-api.onrender.com`**.
   Test it: open `https://qguide-api.onrender.com/health` → `{"status":"ok",...}`.

> Free Postgres lasts ~90 days on Render's free tier; the web service cold-starts
> after 15 min idle (first request after idle is slow). Both fine for testing.

---

## Step 2 — Frontend on Vercel (Next.js)
1. Go to **https://vercel.com/new** → import the same GitHub repo.
2. **Root Directory: `web`** (important — the Next app lives there).
3. Framework preset auto-detects **Next.js**. Leave build/output defaults.
4. **Environment variable:**
   - `NEXT_PUBLIC_API_URL` = `https://qguide-api.onrender.com` (your Render URL, no trailing slash)
5. **Deploy.** You'll get a URL like **`https://q-guide.vercel.app`** — share this with testers.

---

## Step 3 — Lock CORS to your Vercel domain
Back in Render → `qguide-api` → **Environment** → set:
- `ALLOWED_ORIGINS` = `https://q-guide.vercel.app` (your Vercel URL)

Save (the service redeploys). Now only your frontend can call the API.

---

## Done — what testers get
- A real login (JWT), **25 free credits** on signup, **5 credits per design run**.
- Accounts/credits/projects persist in Postgres (survive refreshes & restarts).
- **Buy Credits is a simulated checkout** (no real charge).
- Passwords are salted + PBKDF2-hashed. Still a prototype — don't use real passwords.

## Updating
Push to your branch; Render and Vercel auto-redeploy.

---

## Running the whole stack locally (for development)
Two terminals from `D:\guideRna`:

```bash
# 1) backend (SQLite by default)
.venv\Scripts\python.exe -m uvicorn qguide.app.main:app --reload --port 8000

# 2) frontend
cd web
copy .env.local.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                                # http://localhost:3000
```

The original Streamlit app still works too: `run.bat` (or
`streamlit run qguide/frontend/streamlit_app.py`).
