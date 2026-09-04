# SaaS platform upgrade — final report

Branch `feat/saas-platform` (local; nothing pushed or deployed). Everything below is
implemented and tested unless it is listed under **Remaining TODOs** or **Deferred**.
The living per-item checklist is `docs/UPGRADE_CHECKLIST.md`.

## 1. What changed (summary)

The scientific core (`qguide/core/*`) is untouched apart from one branded string in
`core/report.py`. Around it, the app gained:

* **Central branding** — one config on each side (`qguide/app/branding.py`,
  `web/lib/branding.ts`), env-overridable; no product name is hardcoded any more.
* **Production auth** — password policy, real password-reset emails (pluggable
  SMTP/console sender), signup consent recorded with terms version, rate limiting,
  and a boot-time guard that refuses unsafe production configuration.
* **Role-based access control** — `USER / RESEARCHER / ORGANIZATION_ADMIN / ADMIN`
  with a permission matrix; roles and account status are read from the database on
  every request and can only be changed by an admin or the `ADMIN_EMAILS` bootstrap.
* **Admin console** vs **user dashboard** — platform metrics, user/role/status
  management, ledger activity and system health for admins; projects, analyses,
  collaborations and next steps for users. Admins never receive project contents.
* **Collapsible labelled sidebar** with remembered preference, tooltips when
  collapsed, tablet auto-collapse and a mobile drawer; a full **Projects** page; a
  consistent page-header hierarchy with one primary action per page.
* **First-run onboarding** — 11-step tour, shown once per account (server flag),
  resumable, replayable from Settings.
* **Collaboration** — global project ids, `project_memberships`
  (OWNER / EDITOR / VIEWER), server-side authorisation on every project route,
  invite-by-email of registered users, manage/leave, editor re-run in place.
* **Research tools** — per-project experiment notes/metadata/tags/references,
  analysis templates, batch multi-target runs (RESEARCHER role), project
  comparison, history, Markdown/JSON reports with a reproducibility block.
* **Notifications** — data model, API, preferences, and a working bell wired to
  invitations, role changes, project activity, security and billing events.
* **Settings** — Profile · Account · Security · Notifications · Appearance ·
  Subscription · Onboarding.
* **Legal** — modular Terms / Privacy / Scientific & Research-Use Disclaimer served by
  the API, rendered at `/terms` `/privacy` `/disclaimer`, required at signup, linked
  in every footer.

Tests: **192 passing** (77 → 192; 15 new backend suites' worth of behaviour) plus a
Playwright browser smoke test of the main flows (`docs/` → see §12).

## 2. Files created

Backend (`qguide/app/`): `branding.py`, `roles.py`, `access.py`, `migrations.py`,
`emailer.py`, `ratelimit.py`, `legal.py`, `research.py`.
Tests (`qguide/tests/`): `test_auth_roles.py`, `test_collaboration.py`,
`test_research_tools.py`, `test_notifications.py`, `test_user_flows.py`.
Web (`web/`): `lib/branding.ts`, `lib/nav.ts`, `lib/exports.ts`, `lib/tour.ts`,
`components/Brand.tsx`, `components/LegalPage.tsx`, `components/PageHeader.tsx`,
`components/Sidebar.tsx`, `components/Onboarding.tsx`, `components/ShareDialog.tsx`,
`components/NotificationBell.tsx`, `components/research/{ParamsForm,Templates,Batch,Compare,History}.tsx`,
`app/{terms,privacy,disclaimer,projects,collaborations,research,settings}/page.tsx`,
`app/project/[id]/notes/page.tsx`.
Config/docs: `.env.example`, `web/.env.local.example` (extended),
`docs/UPGRADE_CHECKLIST.md`, `docs/UPGRADE_REPORT.md`.

## 3. Files modified

`qguide/app/{main,auth,routes,store}.py`, `qguide/core/report.py`,
`qguide/tests/{test_api,test_account_folders}.py` (signup now passes `accept_terms`,
passwords meet the policy), `web/app/{layout,globals.css}`,
`web/app/{login,dashboard,account,admin,buy,new}/page.tsx`,
`web/app/project/[id]/page.tsx`, `web/components/{Shell,ProjectNav}.tsx`,
`web/lib/{api,projectCtx}.ts(x)`, `.gitignore`, `CLAUDE.md`.

## 4. Database migrations (`qguide/app/migrations.py`, recorded in `schema_migrations`)

| # | What |
|---|------|
| 1 | Legacy additive columns (folders, archive, last_login) — records the old ad-hoc ALTERs |
| 2 | `users.role, status, institution, research_area, terms_accepted_at, terms_version` |
| 3 | `users.onboarding_completed, onboarding_step, onboarding_completed_at` |
| 4 | `projects.uid` (global id, backfilled) + `project_memberships` table + indexes |
| 5 | `notifications` table + `(user_email, read)` index |
| 6 | `projects.experiment_name, cell_line, target_gene, experiment_type, notes, tags, citations, metadata_updated(_by)` + `analysis_templates` table |
| 7 | `users.notification_prefs` |

New tables are created by the ORM (`Base.metadata.create_all`, portable across
SQLite/Postgres); migrations add columns/indexes and run backfills. They run
automatically at startup and are idempotent — a partially migrated database heals.

## 5. New environment variables

See `.env.example` (backend) and `web/.env.local.example` (web). Required in
production: `JWT_SECRET` (≥32 chars), `ALLOWED_ORIGINS` (explicit), `DATABASE_URL`,
`ENVIRONMENT=production`, `ADMIN_EMAILS`. Email: `EMAIL_BACKEND`, `SMTP_*`,
`EMAIL_FROM`, `APP_BASE_URL`. Optional: `APP_*`/`NEXT_PUBLIC_APP_*` branding,
`LOGIN_RATE_LIMIT/WINDOW`, `SIGNUP_RATE_LIMIT`. Dev only: `QGUIDE_DEV_EMAIL=1`.

## 6. Authentication changes

* Passwords: salted PBKDF2-HMAC-SHA256 (unchanged) + policy (8+ chars, letters and
  numbers, blocklist) enforced on signup / change / reset.
* Tokens: HS256 JWT, 7 days (unchanged). The token carries identity only; role and
  status are re-read from the DB per request, so demotion/suspension is immediate.
* Forgot password sends a real email; the token is only returned by the API when no
  SMTP backend exists **and** `QGUIDE_DEV_EMAIL=1`. Production boot refuses that flag.
* Signup requires `accept_terms=true`; timestamp + `TERMS_VERSION` stored.
* Rate limits on login, signup, forgot-password and user lookup (per-process, see
  `ratelimit.py` for the honest scope note).
* Suspended accounts: sign-in refused, existing tokens rejected (403).
* Security notifications on password change/reset.

## 7. Permission model

Application roles (`qguide/app/roles.py`):

| role | permissions |
|---|---|
| USER | run_design, create_project, research_tools |
| RESEARCHER | + batch_analysis |
| ORGANIZATION_ADMIN | + batch_analysis, manage_org (reserved for org features) |
| ADMIN | + admin_console, manage_users, manage_roles |

Roles are assigned only via `ADMIN_EMAILS` (bootstrap) or `POST /admin/role` by an
admin; `PATCH /account/profile` structurally cannot touch role/status/plan/credits.
The last admin cannot demote themselves; admins cannot suspend themselves.

Project roles (`qguide/app/access.py`), enforced by `require_project()` on every
project route:

| | view/export | rename, select guide, notes | re-run in place | share, folders, archive, delete |
|---|---|---|---|---|
| OWNER | ✓ | ✓ | ✓ | ✓ |
| EDITOR | ✓ | ✓ | ✓ (own credits) | — |
| VIEWER | ✓ | — | — | — |

Non-members get **404** on any project URL; members with an insufficient role get 403.

## 8. Payment setup required from you

**Deferred by your decision.** The credit system is unchanged (simulated checkout,
25 signup credits, 5 per run). No Stripe code was added. When you want subscriptions,
the natural seams are: `roles.PERMISSIONS` (plan entitlements can AND with role
permissions in `routes.require_permission`), `billing.py`, and the Settings ›
Subscription panel which already explains the current model honestly.

## 9. External configuration you must complete

1. Set the production env vars above on Render. The API refuses to start in production
   with the dev JWT secret or `QGUIDE_DEV_EMAIL=1`; `ALLOWED_ORIGINS=*`, a short secret,
   empty `ADMIN_EMAILS` or missing SMTP are logged as loud warnings at startup.
2. Configure SMTP (or set `EMAIL_BACKEND=console` knowingly) — without it, reset and
   invitation emails are written to the server log.
3. `APP_BASE_URL` = your Vercel URL so emailed links resolve.
4. Put your admin email in `ADMIN_EMAILS`, sign up, sign in — you are promoted.
5. Have counsel review `qguide/app/legal.py` and bump `TERMS_VERSION` when it changes.
6. Vercel: root directory `web`, `NEXT_PUBLIC_API_URL` (+ optional branding vars).

## 10. Remaining TODOs

* Payments / subscriptions (deferred).
* Email notifications beyond reset + invite (in-app only today); notification
  preferences apply to in-app items.
* Profile image upload (Settings shows initials; a storage backend is needed).
* Self-service account deletion (Settings gives a support mailto).
* Distributed rate limiting if the API is scaled to >1 worker (Redis/DB backend for
  `ratelimit.py`, same interface).
* Token revocation on password change (tokens are stateless; add a `token_version`
  claim if you want immediate invalidation of other browsers).
* ORGANIZATION_ADMIN has a permission slot but no org entity/UI yet.
* Streamlit UI (`qguide/frontend/streamlit_app.py`) still works but does not expose
  roles, collaboration or notes — it is the legacy prototype.
* Lawyer-reviewed legal text.

## 11. Running the updated project

```
# backend (from repo root)
.venv\Scripts\python.exe -m pip install -r requirements-api.txt
set QGUIDE_DEV_EMAIL=1            # so reset links show without SMTP (dev only)
set ADMIN_EMAILS=you@example.org
.venv\Scripts\python.exe -m uvicorn qguide.app.main:app --reload --port 8000

# web
cd web && npm install && npm run dev      # NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.local
```
Migrations run automatically at startup (watch the log for `applied migration 000N`).

## 12. Testing the new functionality

* `python -m pytest` → 192 tests. Suites by area: `test_auth_roles.py`,
  `test_collaboration.py`, `test_research_tools.py`, `test_notifications.py`,
  `test_user_flows.py` (the exact flows from the brief: new user → onboarding →
  dashboard → project; returning user; admin; owner→editor; viewer; unauthorised URL).
* Manual, in the browser: sign up (terms checkbox gates the button) → tour appears →
  Finish → reload: no tour → Settings › Onboarding › Replay. Collapse the sidebar
  («), reload: still collapsed; hover an icon: tooltip. New Analysis → Run → project
  → Share → invite a second account as Viewer → in that account the bell shows the
  invite → open → read-only notice, no Save/Re-run. Change to Editor → Notes tab
  becomes editable. Sign in as a third account and paste the project URL → "does
  not exist or you do not have access". Add your email to `ADMIN_EMAILS` → Admin
  Dashboard appears in the sidebar; another user opening `/admin` is refused.
* A Playwright script exercising all of the above end-to-end passed against a local
  build (31 checks) — see the session notes; it is not committed because it depends
  on a locally running stack.
