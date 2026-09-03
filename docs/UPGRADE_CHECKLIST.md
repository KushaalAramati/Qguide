# SaaS platform upgrade — living checklist

Branch: `feat/saas-platform` (local only; nothing pushed or deployed until you merge).
Legend: `[x]` done & tested · `[~]` in progress · `[ ]` not started · `[-]` deferred by decision.

Decisions so far
- Billing: keep the credit system as-is for now; Stripe subscriptions deferred (your call).
- Email: pluggable sender, SMTP + console fallback.
- Delivery: one check-in per phase; this file is updated at every check-in.
- Git: feature branch, no push.

## Phase 1 — Branding, auth hardening, roles, migrations  `[x]`
- [x] Central branding config — `qguide/app/branding.py`, `web/lib/branding.ts`, `web/components/Brand.tsx`; `GET /branding`
- [x] All hardcoded product names replaced (API title, page metadata, shell, login, CSV export)
- [x] Password policy in one place (8+ chars, letters+numbers, blocklist) for signup / change / reset
- [x] Pluggable email (`qguide/app/emailer.py`): SMTP or console; reset / welcome / invite templates
- [x] Forgot-password sends email; token only surfaced when no SMTP **and** `QGUIDE_DEV_EMAIL=1`
- [x] Rate limiting on login / signup / forgot (`qguide/app/ratelimit.py`, per-process — documented)
- [x] Production boot guard: refuses default/short `JWT_SECRET`, `ALLOWED_ORIGINS=*`, dev-email mode
- [x] Terms + privacy acceptance required at signup; timestamp and version stored
- [x] Roles `USER / RESEARCHER / ORGANIZATION_ADMIN / ADMIN` (`qguide/app/roles.py`) + permission matrix
- [x] Role and status re-read from DB on every request (no token claims trusted)
- [x] Self-service profile cannot touch role / status / plan / credits
- [x] Admin endpoints: `/admin/role`, `/admin/status`, `/admin/roles`; last-admin and self-suspend guards
- [x] `ADMIN_EMAILS` bootstrap promotes at startup and sign-in
- [x] Versioned migration runner with `schema_migrations` ledger (`qguide/app/migrations.py`)
- [x] Migration 0002: role, status, institution, research_area, terms_accepted_at, terms_version
- [x] Legal module (`qguide/app/legal.py`), `GET /legal/{slug}`, pages `/terms` `/privacy` `/disclaimer`
- [x] Signup UI: terms consent, institution, policy hint, precise error + loading states
- [x] Tests: 166 passing (`qguide/tests/test_auth_roles.py` added)
- [x] `next build` verification (run in the cloud sandbox; Google Fonts stubbed there only)

## Phase 2 — User dashboard vs admin dashboard  `[x]`
- [x] `GET /admin/stats` (users total / active / new, projects, plan + role breakdown, 12-week trend, recent signups)
- [x] `GET /admin/activity` (ledger events, gene names stripped) · `GET /admin/health` (db, migrations, email, auth, CORS, quantum sampler)
- [x] Admin dashboard: Overview · Users (search, role select, suspend/reactivate, credits, CSV) · Activity · System
- [x] User dashboard: header with primary CTA, metrics, recent projects, next steps, guide activity; loading/empty/error states
- [x] Shared `PageHeader` / `Tabs` / `EmptyState` / `LoadingRows` / `ErrorState` primitives
- [x] Admin never sees project contents (server-side; test asserts no sequences leak)
- [ ] "Shared with me" section on the user dashboard — lands with Phase 5

## Phase 3 — Collapsible sidebar + information hierarchy  `[x]`
- [x] `lib/nav.ts` single nav definition; `components/Sidebar.tsx` expanded (logo + labels) / collapsed (icons + tooltips)
- [x] Preference remembered (`localStorage: qg-sidebar`); auto-collapses < 1024 px until the user chooses
- [x] < 768 px: sidebar becomes a drawer opened from the command bar (Esc / backdrop closes)
- [x] Admin Dashboard entry only for admins (server enforces regardless)
- [x] Project explorer moved to a full `/projects` page (folders, filter, archive, move/rename/delete)
- [x] Project header: back link, larger title, facts strip, primary **Export results ▾** (CSV / JSON via `lib/exports.ts`)
- [x] New Analysis: numbered panels, sticky run summary, primary **Run analysis** in header + summary, short-sequence guard
- [x] Account / Billing pages on `PageHeader`; simulated-checkout notice made explicit
- [x] Status bar now reports real API reachability; hardcoded "postgres" / "GRCh38" labels removed
- [x] Footer legal links inside the app shell
- [ ] Collaborations / Research Tools nav entries — added when their pages land (Phases 5, 6)

## Phase 4 — First-time onboarding  `[ ]`
- [ ] `onboarding_completed` / `onboarding_step` on user; API to read/update
- [ ] Step-by-step tour (Next / Back / Skip / Finish), shown once
- [ ] Replay from Settings and Help

## Phase 5 — Collaboration and permissions  `[ ]`
- [ ] Global project id + owner; `project_memberships` (OWNER / EDITOR / VIEWER)
- [ ] Invite by email (registered users), manage access, remove, change role
- [ ] Every project route authorised server-side; guessed URLs return 404/403
- [ ] Share / Manage access UI; collaborators list; Collaborations page

## Phase 6 — Researcher tools  `[ ]`
- [ ] Experiment metadata (organism, cell line, target gene, nuclease, type, notes, tags)
- [ ] Batch / multi-target analysis, saved templates, comparison, history
- [ ] CSV / JSON export with reproducibility metadata

## Phase 7 — Notifications, settings, legal  `[ ]`
- [ ] `notifications` table + API (list, mark read, mark all read, deep link)
- [ ] Working bell; events: invite, collaborator joined, project changed, security alert
- [ ] Settings: Profile · Account · Security · Notifications · Appearance · Subscription · Tutorial
- [ ] Footer legal links inside the app shell

## Phase 8 — Testing + final report  `[ ]`
- [ ] Flow tests: signup→onboarding→dashboard→project; collaboration; viewer denial; unauthorised URL
- [ ] Final report: files, migrations, env vars, permission model, external config, TODOs

## Deferred
- [-] Stripe subscriptions / plan entitlements (kept credit packs; simulated checkout unchanged)
