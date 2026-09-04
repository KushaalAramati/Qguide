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
- [x] "Shared with me" section on the user dashboard (Phase 5)

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
- [x] Collaborations nav entry (Phase 5) · [x] Research Tools nav entry (Phase 6)

## Phase 4 — First-time onboarding  `[x]`
- [x] Migration 0003: `onboarding_completed`, `onboarding_step`, `onboarding_completed_at`; `GET/PATCH /account/onboarding`; flag on `/me`
- [x] 11-step tour (`lib/tour.ts`, `components/Onboarding.tsx`): Next / Back / Skip tutorial / Finish, ← → Esc keys, deep links
- [x] Shown once per **account** (server flag), progress persisted step by step
- [x] Replay tutorial from Settings › Onboarding (lists the steps)
- [x] Test: first login shows it, finish persists, second login does not, replay resets

## Phase 5 — Collaboration and permissions  `[x]`
- [x] Migration 0004: global `projects.uid` (backfilled for existing rows) + `project_memberships` (project_uid, user_email, role, invited_by, created; unique index)
- [x] Migration 0005: `notifications` table (API/UI in Phase 7) — invites, role changes, removals, re-runs, deletions already write to it
- [x] `qguide/app/access.py`: OWNER / EDITOR / VIEWER, capability matrix, `require_project()` used by every project route
- [x] Non-members get 404 on any project URL (existence not revealed); insufficient role gets 403
- [x] `GET /projects` = own (with collaborator counts) + shared-with-me (with role, owner name)
- [x] `GET/POST/PATCH/DELETE /projects/{id}/members`; invite requires a registered account; owners cannot be removed; collaborators can leave
- [x] `GET /users/lookup` (auth + rate-limited exact match) for the invite dialog
- [x] Editors: rename, save selected guide, `POST /projects/{id}/rerun` in place (charged to the runner). Owner-only: share, delete, folders/archive
- [x] Invitation email via the pluggable sender
- [x] UI: Share / Access dialog (live lookup, role select, change/remove/leave), role badge + read-only notice in project header, Save selection / Re-run actions
- [x] `/collaborations` page + sidebar entry; "shared with me" on dashboard and projects page
- [x] Tests: 11 new in `test_collaboration.py` (180 total) — editor access + modify, viewer denial, stranger 404, leave, delete cascade, legacy uid backfill

## Phase 6 — Researcher tools  `[x]`
- [x] Migration 0006: experiment_name, cell_line, target_gene, experiment_type, notes, tags, citations (+ audit fields) on projects; `analysis_templates` table
- [x] `qguide/app/research.py` router (scientific core untouched): metadata, tags, templates CRUD, batch, compare, history, report
- [x] Project **Notes** tab: experiment metadata, notes, tags (autocomplete from your library), references (DOI/URL); editors write, viewers read
- [x] Analysis templates (parameters only — never sequences), validated against `DesignRequest`
- [x] Batch multi-target runs (FASTA or name↹sequence), one shared config or template, files results in a folder, tags them; credits checked up front, charged per run; ≤10 targets
- [x] Batch is gated by the RESEARCHER role (`batch_analysis` permission) — non-researchers see why and who can grant it; every account keeps templates/compare/history/notes
- [x] Compare 2–4 accessible projects: inputs, score stats, optimised sets, top guides, shared protospacers
- [x] Experiment history (run ledger + projects)
- [x] Reports: `GET /research/projects/{id}/report` (JSON or Markdown) from the stored result with metadata + reproducibility block; both in the Export menu
- [x] `/research` page + sidebar entry; report title now branded
- [x] Tests: 4 new in `test_research_tools.py` (184 total)

## Phase 7 — Notifications, settings, legal  `[x]`
- [x] Notifications API: list (+unread-only), unread count, mark read / unread / all, delete; deep `link` on each item; per-user only
- [x] Events wired: project invite, role changed, access removed, collaborator left, rename, notes updated, re-run completed, project deleted, password changed / reset, credits purchased or adjusted, role changed by admin
- [x] Migration 0007 + per-category preferences (collaboration · project activity · account · billing) — muted categories are not written
- [x] Working bell in the top bar: polled unread badge, panel with mark-read toggles, mark all, click-through to the linked project/settings
- [x] Settings (`/account`, `/settings` alias, `?section=` deep links): Profile (name, institution, research area) · Account · Security (policy-checked password change) · Notifications · Appearance (theme + sidebar) · Subscription (plan, credits, billing/usage ledgers) · Onboarding
- [x] Legal footer inside the app shell (Phase 3) and on auth/legal pages
- [x] Tests: 4 new in `test_notifications.py` (188 total)

## Phase 8 — Testing + final report  `[x]`
- [x] `test_user_flows.py`: new user (signup → onboarding → dashboard → project), returning user, admin, owner→editor, viewer denial, unauthorised URL — 192 tests total
- [x] Browser smoke test (Playwright, local stack): 31 checks incl. terms gate, tour next/back/finish/not-again, sidebar collapse + tooltip + persistence, run analysis, share dialog with live lookup, bell → project, editor notes, viewer read-only, stranger denied, research/collaborations/settings/projects render, admin sidebar + users table, mobile drawer
- [x] `docs/UPGRADE_REPORT.md` (deliverable §21), `.env.example`, `web/.env.local.example`, `CLAUDE.md` updated

## Deferred
- [-] Stripe subscriptions / plan entitlements (kept credit packs; simulated checkout unchanged)
