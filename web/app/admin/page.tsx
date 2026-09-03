"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/Shell";
import { Panel, Metric, Button, BarRow } from "@/components/ui";
import { PageHeader, Tabs, EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api, Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";
import { APP_SLUG, BRANDING } from "@/lib/branding";

/**
 * Administrator console. Everything here is account-level operations data:
 * counts, plans, roles, ledger activity, system health. Project contents are
 * never fetched — the backend does not expose them to admins either.
 */
export default function AdminPage() {
  return <Shell><AdminView /></Shell>;
}

const SECTIONS = ["Overview", "Users", "Activity", "System"] as const;
type Sec = typeof SECTIONS[number];

function AdminView() {
  const { account } = useAuth();
  const [sec, setSec] = useState<Sec>("Overview");
  if (!account) return null;
  if (!account.is_admin) {
    return (
      <div className="flex flex-col gap-3">
        <PageHeader title="Admin dashboard" />
        <ErrorState message="You don't have administrator access. Administrator roles are assigned by an existing admin or through the server's ADMIN_EMAILS configuration." />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="administration"
        title="Admin dashboard"
        description={`Operate ${BRANDING.APP_NAME}: users, roles, account status, activity and system health. Research data stays private to its owners and collaborators.`}
      />
      <Tabs<Sec> items={SECTIONS} value={sec} onChange={setSec} />
      {sec === "Overview" && <Overview />}
      {sec === "Users" && <Users selfEmail={account.email} />}
      {sec === "Activity" && <Activity />}
      {sec === "System" && <System />}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Overview                                                                     //
// --------------------------------------------------------------------------- //
function Overview() {
  const [st, setSt] = useState<any>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setErr("");
    api.adminStats().then(setSt).catch((e) => setErr(e.message || "Failed to load statistics."));
  }, []);
  useEffect(() => { load(); }, [load]);

  if (err) return <ErrorState message={err} retry={load} />;
  if (!st) return <LoadingRows n={6} />;

  const maxWeek = Math.max(1, ...st.weekly.map((w: any) => Math.max(w.signups, w.projects)));
  const plans = Object.entries(st.billing.users_by_plan as Record<string, number>).sort((a, b) => b[1] - a[1]);
  const roles = Object.entries(st.users_by_role as Record<string, number>).sort((a, b) => b[1] - a[1]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Metric label="Registered users" value={st.users.total} sub={`${st.users.suspended} suspended`} color="brand" />
        <Metric label="Active (30 days)" value={st.users.active_30d} sub={`${st.users.active_7d} in last 7 days`} meter={st.users.total ? st.users.active_30d / st.users.total : 0} />
        <Metric label="New users (7d)" value={st.users.new_7d} sub={`${st.users.new_30d} in 30 days`} />
        <Metric label="Projects" value={st.projects.total} sub={`+${st.projects.new_7d} this week`} />
        <Metric label="Design runs" value={st.usage.total_runs} sub={`${st.usage.credits_in_circulation} credits outstanding`} />
        <Metric label="Revenue" value={`$${st.billing.revenue_total.toFixed(0)}`} sub={`$${st.billing.revenue_30d.toFixed(0)} in 30 days · ${st.billing.purchases} purchases`} color="good" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 items-start">
        <Panel title="growth · last 12 weeks" meta="signups vs projects">
          <table className="dtable">
            <thead><tr><th>week ending</th><th className="w-full">signups</th><th>projects</th></tr></thead>
            <tbody>
              {st.weekly.map((w: any) => (
                <tr key={w.week_ending}>
                  <td className="whitespace-nowrap text-muted">{w.week_ending}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="flex-1 h-[6px] bg-track overflow-hidden">
                        <span className="block h-full bg-brand" style={{ width: `${(w.signups / maxWeek) * 100}%` }} />
                      </span>
                      <span className="w-6 text-right tabular-nums">{w.signups}</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="w-16 h-[6px] bg-track overflow-hidden">
                        <span className="block h-full bg-series" style={{ width: `${(w.projects / maxWeek) * 100}%` }} />
                      </span>
                      <span className="w-6 text-right tabular-nums">{w.projects}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel title="users by plan">
            {plans.map(([name, n]) => <BarRow key={name} label={name} value={n / Math.max(1, st.users.total)} tone="accent" />)}
          </Panel>
          <Panel title="users by role">
            {roles.map(([name, n]) => <BarRow key={name} label={name.toLowerCase()} value={n / Math.max(1, st.users.total)} />)}
          </Panel>
        </div>
      </div>

      <Panel title="recent signups" meta={`${st.recent_signups.length} most recent`} bodyClass="">
        {st.recent_signups.length === 0 ? <EmptyState title="No signups yet." /> : (
          <table className="dtable">
            <thead><tr><th>name</th><th>email</th><th>plan</th><th>role</th><th>joined</th></tr></thead>
            <tbody>
              {st.recent_signups.map((u: any) => (
                <tr key={u.email}>
                  <td className="text-ink">{u.name}</td>
                  <td>{u.email}</td>
                  <td>{u.plan}</td>
                  <td><span className={u.role === "ADMIN" ? "tag-good" : "text-muted"}>{u.role.toLowerCase()}</span></td>
                  <td className="whitespace-nowrap text-muted">{u.created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Users                                                                        //
// --------------------------------------------------------------------------- //
function Users({ selfEmail }: { selfEmail: string }) {
  const [users, setUsers] = useState<any[] | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [q, setQ] = useState("");
  const [credits, setCredits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      const [u, r] = await Promise.all([api.adminUsers(), api.adminRoles()]);
      setUsers(u);
      setRoles(r.roles);
      setCredits(Object.fromEntries(u.map((x: any) => [x.email, String(x.credits)])));
    } catch (e: any) {
      setErr(e.message || "Failed to load users.");
      setUsers([]);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function act(email: string, fn: () => Promise<any>, ok: string) {
    setBusy(email); setMsg(""); setErr("");
    try { await fn(); setMsg(ok); await load(); }
    catch (e: any) { setErr(e.message || "Action failed."); }
    finally { setBusy(""); }
  }

  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (users || []).filter((u) => !t || `${u.name} ${u.email} ${u.plan} ${u.role}`.toLowerCase().includes(t));
  }, [users, q]);

  function exportUsers() {
    downloadCsv(`${APP_SLUG}_users_${new Date().toISOString().slice(0, 10)}.csv`,
      (users || []).map((u) => ({ name: u.name, email: u.email, role: u.role, status: u.status, plan: u.plan,
        credits: u.credits, design_runs: u.runs, projects: u.n_projects, institution: u.institution || "",
        created: u.created, last_login: u.last_login || "" })));
  }

  if (users === null) return <LoadingRows n={6} />;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 border border-border bg-well px-2 py-1 w-72 max-w-full">
          <span className="text-brand text-[11px]">/</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter by name, email, plan or role"
                 aria-label="Filter users" className="w-full bg-transparent border-0 outline-none text-[11px] text-ink placeholder:text-faint" />
        </div>
        <span className="text-[11px] text-faint">{shown.length} of {users.length}</span>
        <span className="flex-1" />
        <button onClick={exportUsers} className="btn-ghost text-[11.5px]" disabled={!users.length}>Export CSV</button>
      </div>
      {err && <ErrorState message={err} />}
      {msg && <div className="text-[11.5px] text-brand">{msg}</div>}

      <Panel title="all users" meta="role and status changes are logged to the user's ledger" bodyClass="overflow-x-auto">
        {shown.length === 0 ? <EmptyState title="No users match." /> : (
          <table className="dtable min-w-[900px]">
            <thead><tr>
              {["user", "role", "status", "plan", "projects", "runs", "credits", "last login", ""].map((h) => <th key={h}>{h}</th>)}
            </tr></thead>
            <tbody>
              {shown.map((u) => {
                const self = u.email === selfEmail;
                const suspended = u.status === "suspended";
                return (
                  <tr key={u.email} className={suspended ? "opacity-60" : ""}>
                    <td>
                      <div className="text-ink">{u.name}{self && <span className="ml-1.5 text-faint">(you)</span>}</div>
                      <div className="text-faint text-[10.5px]">{u.email}{u.institution ? ` · ${u.institution}` : ""}</div>
                    </td>
                    <td>
                      <select
                        value={u.role}
                        disabled={busy === u.email}
                        aria-label={`Role for ${u.email}`}
                        onChange={(e) => act(u.email, () => api.adminSetRole(u.email, e.target.value as Role), `Role for ${u.email} set to ${e.target.value}.`)}
                        className="border border-border bg-well px-1.5 py-0.5 text-[11px] text-ink outline-none focus:border-brand"
                      >
                        {roles.map((r) => <option key={r} value={r}>{r.toLowerCase().replace("_", " ")}</option>)}
                      </select>
                    </td>
                    <td>
                      {self ? <span className="text-faint">active</span> : (
                        <button
                          disabled={busy === u.email}
                          onClick={() => {
                            if (!suspended && !window.confirm(`Suspend ${u.email}? They will be signed out immediately and unable to sign in.`)) return;
                            act(u.email, () => api.adminSetStatus(u.email, suspended ? "active" : "suspended"),
                                `${u.email} ${suspended ? "reactivated" : "suspended"}.`);
                          }}
                          className={suspended ? "tag-bad hover:opacity-80" : "tag-good hover:opacity-80"}
                          title={suspended ? "Reactivate account" : "Suspend account"}
                        >
                          {suspended ? "suspended" : "active"}
                        </button>
                      )}
                    </td>
                    <td className="whitespace-nowrap">{u.plan}</td>
                    <td className="tabular-nums">{u.n_projects ?? 0}</td>
                    <td className="tabular-nums">{u.runs}</td>
                    <td>
                      <div className="flex gap-1 items-center">
                        <input type="number" min={0} aria-label={`Credits for ${u.email}`}
                               className="input !py-0.5 !px-1.5 w-20 !text-[11px]"
                               value={credits[u.email] ?? ""}
                               onChange={(e) => setCredits({ ...credits, [u.email]: e.target.value })} />
                        <button
                          className="btn-ghost !py-0.5 !px-2 !text-[11px]"
                          disabled={busy === u.email || String(u.credits) === credits[u.email]}
                          onClick={() => {
                            const v = parseInt(credits[u.email]);
                            if (!isNaN(v) && v >= 0) act(u.email, () => api.adminSetCredits(u.email, v), `Set ${u.email} to ${v} credits.`);
                          }}
                        >set</button>
                      </div>
                    </td>
                    <td className="whitespace-nowrap text-muted">{u.last_login || "—"}</td>
                    <td className="text-faint text-[10.5px] whitespace-nowrap">joined {u.created?.slice(0, 10)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Activity                                                                     //
// --------------------------------------------------------------------------- //
function Activity() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setErr("");
    api.adminActivity(100).then(setRows).catch((e) => setErr(e.message || "Failed to load activity."));
  }, []);
  useEffect(() => { load(); }, [load]);
  if (err) return <ErrorState message={err} retry={load} />;
  if (!rows) return <LoadingRows n={8} />;
  return (
    <Panel title="application activity" meta="most recent 100 ledger events" bodyClass="">
      {rows.length === 0 ? <EmptyState title="No activity yet." body="Design runs, purchases and admin actions will appear here." /> : (
        <table className="dtable">
          <thead><tr><th>when</th><th>user</th><th>event</th><th>credits</th><th>balance</th><th>detail</th></tr></thead>
          <tbody>
            {rows.map((t, i) => (
              <tr key={i}>
                <td className="whitespace-nowrap text-muted">{t.ts}</td>
                <td>{t.email}</td>
                <td><span className={t.type === "admin" ? "tag-warn" : t.type === "purchase" ? "tag-good" : "text-muted"}>{t.type}</span></td>
                <td className={`tabular-nums ${t.amount > 0 ? "text-brand" : t.amount < 0 ? "text-bad" : "text-faint"}`}>{t.amount > 0 ? "+" : ""}{t.amount}</td>
                <td className="tabular-nums">{t.balance}</td>
                <td className="text-muted">{t.desc}{t.price ? ` · $${t.price.toFixed(2)}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

// --------------------------------------------------------------------------- //
// System                                                                       //
// --------------------------------------------------------------------------- //
function System() {
  const [h, setH] = useState<any>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setErr("");
    api.adminHealth().then(setH).catch((e) => setErr(e.message || "Failed to load health."));
  }, []);
  useEffect(() => { load(); }, [load]);
  if (err) return <ErrorState message={err} retry={load} />;
  if (!h) return <LoadingRows n={5} />;

  const Row = ({ k, v, ok }: { k: string; v: any; ok?: boolean }) => (
    <div className="flex items-center gap-3 py-1.5 border-b border-divider last:border-b-0 text-[11.5px]">
      <span className="w-44 text-faint">{k}</span>
      <span className="text-cell flex-1 truncate">{String(v)}</span>
      {ok !== undefined && <span className={ok ? "tag-good" : "tag-bad"}>{ok ? "ok" : "check"}</span>}
    </div>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <Panel title="database" meta={h.database.dialect}>
        <Row k="connection" v={h.database.ok ? "reachable" : h.database.error} ok={h.database.ok} />
        <Row k="schema version" v={h.database.migration_version ?? "—"} />
      </Panel>
      <Panel title="authentication">
        <Row k="JWT secret" v={h.auth.jwt_secret_configured ? "configured" : "DEFAULT DEV KEY"} ok={h.auth.jwt_secret_configured} />
        <Row k="token lifetime" v={`${h.auth.token_ttl_days} days`} />
        <Row k="CORS origins" v={h.cors.origins.join(", ")} ok={!h.cors.origins.includes("*")} />
      </Panel>
      <Panel title="email">
        <Row k="backend" v={h.email.backend} ok={h.email.configured} />
        {!h.email.configured && <div className="caveat mt-2">No SMTP backend configured — password-reset and invitation emails are written to the server log instead of being delivered.</div>}
      </Panel>
      <Panel title="runtime">
        <Row k="environment" v={h.runtime.environment} />
        <Row k="python" v={h.runtime.python} />
        <Row k="quantum sampler (dimod)" v={h.quantum.dimod_available ? "available" : "not installed"} ok={h.quantum.dimod_available} />
      </Panel>
    </div>
  );
}
