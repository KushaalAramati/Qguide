"use client";
// Settings — Profile · Account · Security · Notifications · Appearance · Subscription · Onboarding
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Shell } from "@/components/Shell";
import { Panel, Metric, Button } from "@/components/ui";
import { PageHeader, Tabs, ErrorState } from "@/components/PageHeader";
import { ReplayTourButton } from "@/components/Onboarding";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TOUR_STEPS } from "@/lib/tour";
import { useAuth } from "@/lib/auth";
import { api, Account } from "@/lib/api";
import { BRANDING } from "@/lib/branding";

export default function AccountPage() {
  return (
    <Shell>
      <Suspense fallback={null}><SettingsView /></Suspense>
    </Shell>
  );
}

const SECTIONS = ["Profile", "Account", "Security", "Notifications", "Appearance", "Subscription", "Onboarding"] as const;
type Sec = typeof SECTIONS[number];

function SettingsView() {
  const { account, setAccount, signOut } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const wanted = params.get("section") as Sec | null;
  const [sec, setSec] = useState<Sec>(wanted && SECTIONS.includes(wanted) ? wanted : "Profile");
  useEffect(() => { if (wanted && SECTIONS.includes(wanted)) setSec(wanted); }, [wanted]);
  if (!account) return null;

  function go(s: Sec) { setSec(s); router.replace(`/account?section=${s}`); }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="settings"
        title="Settings"
        description={`${account.name} · ${account.email}`}
        actions={<span className="text-[11px] text-faint">{account.role?.toLowerCase().replace("_", " ")} · {account.plan}</span>}
      />
      <Tabs<Sec> items={SECTIONS} value={sec} onChange={go} />
      {sec === "Profile" && <Profile account={account} setAccount={setAccount} />}
      {sec === "Account" && <AccountSection account={account} signOut={signOut} />}
      {sec === "Security" && <Security signOut={signOut} />}
      {sec === "Notifications" && <NotificationPrefs />}
      {sec === "Appearance" && <Appearance />}
      {sec === "Subscription" && <Subscription account={account} />}
      {sec === "Onboarding" && <Onboarding account={account} />}
    </div>
  );
}

// --------------------------------------------------------------------------- //
function Profile({ account, setAccount }: { account: Account; setAccount: (a: Account) => void }) {
  const [name, setName] = useState(account.name);
  const [inst, setInst] = useState(account.institution || "");
  const [area, setArea] = useState(account.research_area || "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const dirty = name !== account.name || inst !== (account.institution || "") || area !== (account.research_area || "");
  async function save() {
    setBusy(true); setMsg(""); setErr("");
    try { setAccount(await api.updateProfile({ name, institution: inst, research_area: area })); setMsg("Profile saved."); }
    catch (e: any) { setErr(e.message || "Save failed."); } finally { setBusy(false); }
  }
  return (
    <Panel title="profile" meta="visible to collaborators">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
        <label className="block"><span className="label mb-1 block">Full name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block"><span className="label mb-1 block">Email</span><input className="input opacity-70" value={account.email} disabled /></label>
        <label className="block"><span className="label mb-1 block">Institution</span><input className="input" value={inst} placeholder="Lab, university or company" onChange={(e) => setInst(e.target.value)} /></label>
        <label className="block"><span className="label mb-1 block">Role / research area</span><input className="input" value={area} placeholder="e.g. Functional genomics, gene therapy" onChange={(e) => setArea(e.target.value)} /></label>
      </div>
      <div className="flex items-center gap-3 mt-4">
        <Button onClick={save} disabled={busy || !name.trim() || !dirty}>{busy ? "Saving…" : "Save profile"}</Button>
        {msg && <span className="text-[11.5px] text-brand">{msg}</span>}
        {err && <span className="text-[11.5px] text-bad">{err}</span>}
      </div>
      <div className="text-[10.5px] text-faint mt-3">Profile image upload is not available yet; collaborators see your initial.</div>
    </Panel>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-divider last:border-b-0 text-[11.5px]">
      <span className="w-40 text-faint">{k}</span><span className="text-cell flex-1">{v}</span>
    </div>
  );
}

function AccountSection({ account, signOut }: { account: Account; signOut: () => void }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <Panel title="account">
        <Row k="email" v={account.email} />
        <Row k="member since" v={account.created} />
        <Row k="last sign-in" v={account.last_login || "—"} />
        <Row k="role" v={<span className={account.is_admin ? "tag-good" : ""}>{account.role?.toLowerCase().replace("_", " ")}</span>} />
        <Row k="status" v={account.status} />
        <Row k="terms accepted" v={account.terms_accepted_at || "—"} />
      </Panel>
      <Panel title="actions">
        <div className="flex flex-col gap-3 text-[11.5px]">
          <div>
            <Button variant="ghost" onClick={signOut}>Sign out</Button>
            <div className="text-[10.5px] text-faint mt-1">Signs this browser out. Sessions expire automatically after 7 days.</div>
          </div>
          <div className="pt-3 border-t border-divider">
            <div className="text-ink">Delete account</div>
            <div className="text-[10.5px] text-faint mt-0.5">
              Self-service deletion is not available yet. Email{" "}
              <a className="text-brand hover:underline" href={`mailto:${BRANDING.SUPPORT_EMAIL}?subject=Account%20deletion%20request`}>{BRANDING.SUPPORT_EMAIL}</a>{" "}
              from this address and your account and projects will be removed.
            </div>
          </div>
          <div className="pt-3 border-t border-divider text-[10.5px] text-faint">
            <Link href="/terms" className="text-brand hover:underline">Terms</Link> · <Link href="/privacy" className="text-brand hover:underline">Privacy</Link> · <Link href="/disclaimer" className="text-brand hover:underline">Scientific disclaimer</Link>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Security({ signOut }: { signOut: () => void }) {
  const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [cf, setCf] = useState("");
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  async function change() {
    setMsg(""); setErr("");
    if (nw.length < 8) return setErr("New password must be at least 8 characters.");
    if (!/[A-Za-z]/.test(nw) || !/\d/.test(nw)) return setErr("Use both letters and numbers.");
    if (nw !== cf) return setErr("New passwords do not match.");
    setBusy(true);
    try { await api.changePassword(cur, nw); setMsg("Password updated. A security notice was added to your notifications."); setCur(""); setNw(""); setCf(""); }
    catch (e: any) { setErr(e.message || "Failed."); } finally { setBusy(false); }
  }
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <Panel title="change password">
        <div className="flex flex-col gap-3 max-w-sm">
          <label className="block"><span className="label mb-1 block">Current password</span><input type="password" autoComplete="current-password" className="input" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
          <label className="block"><span className="label mb-1 block">New password</span><input type="password" autoComplete="new-password" className="input" value={nw} onChange={(e) => setNw(e.target.value)} /></label>
          <label className="block"><span className="label mb-1 block">Confirm new password</span><input type="password" autoComplete="new-password" className="input" value={cf} onChange={(e) => setCf(e.target.value)} /></label>
          <div className="text-[10.5px] text-faint">At least 8 characters with letters and numbers.</div>
          <div className="flex items-center gap-3">
            <Button onClick={change} disabled={busy || !cur || !nw}>{busy ? "Updating…" : "Change password"}</Button>
          </div>
          {msg && <div className="text-[11.5px] text-brand">{msg}</div>}
          {err && <ErrorState message={err} />}
        </div>
      </Panel>
      <Panel title="sessions">
        <div className="text-[11.5px] text-muted leading-relaxed">
          Sign-in tokens are valid for 7 days and are stored only in this browser. If you think your account was accessed by someone else, change your password (which does not revoke other browsers' tokens until they expire) and contact{" "}
          <a className="text-brand hover:underline" href={`mailto:${BRANDING.SUPPORT_EMAIL}`}>{BRANDING.SUPPORT_EMAIL}</a>.
        </div>
        <div className="mt-3"><Button variant="ghost" onClick={signOut}>Sign out of this browser</Button></div>
      </Panel>
    </div>
  );
}

function NotificationPrefs() {
  const [prefs, setPrefs] = useState<Record<string, boolean> | null>(null);
  const [cats, setCats] = useState<Record<string, string>>({});
  const [err, setErr] = useState(""); const [busy, setBusy] = useState("");
  useEffect(() => {
    api.notificationPrefs().then((r) => { setPrefs(r.preferences); setCats(r.categories); }).catch((e) => setErr(e.message));
  }, []);
  async function toggle(k: string) {
    if (!prefs) return;
    setBusy(k);
    try { const r = await api.setNotificationPrefs({ [k]: !prefs[k] }); setPrefs(r.preferences); }
    catch (e: any) { setErr(e.message); } finally { setBusy(""); }
  }
  return (
    <Panel title="notification preferences" meta="in-app notifications">
      {err && <ErrorState message={err} />}
      {!prefs ? <div className="text-[11px] text-faint">loading…</div> : (
        <div className="divide-y divide-divider max-w-2xl">
          {Object.entries(cats).map(([k, desc]) => (
            <label key={k} className="flex items-start gap-3 py-2.5 cursor-pointer">
              <input type="checkbox" className="mt-0.5" checked={!!prefs[k]} disabled={busy === k} onChange={() => toggle(k)} />
              <span><span className="block text-[12px] text-ink capitalize">{k.replace("_", " ")}</span><span className="block text-[11px] text-faint">{desc}</span></span>
            </label>
          ))}
        </div>
      )}
      <div className="text-[10.5px] text-faint mt-3">Email delivery of notifications is limited to password resets and project invitations for now.</div>
    </Panel>
  );
}

function Appearance() {
  const [side, setSide] = useState<string>("");
  useEffect(() => { try { setSide(localStorage.getItem("qg-sidebar") || "auto"); } catch {} }, []);
  function setSidebar(v: string) {
    try { v === "auto" ? localStorage.removeItem("qg-sidebar") : localStorage.setItem("qg-sidebar", v); } catch {}
    setSide(v); window.dispatchEvent(new Event("resize"));
  }
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <Panel title="theme">
        <ThemeToggle />
        <div className="text-[10.5px] text-faint mt-2">Light “Stone” or dark “Charcoal”. Follows your OS until you choose.</div>
      </Panel>
      <Panel title="sidebar">
        <div className="seg" role="group" aria-label="Sidebar">
          {[["auto", "automatic"], ["expanded", "expanded"], ["collapsed", "collapsed"]].map(([v, l]) => (
            <button key={v} className={side === v ? "on" : ""} onClick={() => setSidebar(v)}>{l}</button>
          ))}
        </div>
        <div className="text-[10.5px] text-faint mt-2">Automatic keeps labels on wide screens and collapses to icons on narrower ones. Takes effect after the next navigation.</div>
      </Panel>
    </div>
  );
}

function Subscription({ account }: { account: Account }) {
  const [view, setView] = useState<"billing" | "usage">("billing");
  const used = account.transactions.filter((t) => t.type === "usage").reduce((s, t) => s - t.amount, 0);
  const rows = view === "billing"
    ? account.transactions.filter((t) => ["purchase", "bonus", "admin"].includes(t.type))
    : account.transactions.filter((t) => t.type === "usage");
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Plan" value={account.plan} sub="credit-based" />
        <Metric label="Credits" value={account.credits} sub="5 per design run" color={account.credits < 5 ? "bad" : "brand"} />
        <Metric label="Design runs" value={account.runs} sub={`${used} credits used`} />
        <Metric label="Purchases" value={account.transactions.filter((t) => t.type === "purchase").length} sub="lifetime" />
      </div>
      <Panel title="plan" meta="subscriptions coming later">
        <div className="text-[11.5px] text-muted leading-relaxed max-w-2xl">
          {BRANDING.APP_NAME} currently meters usage with credits: every design run, re-run or batch target costs 5 credits, and new accounts start with 25. Subscription plans are not offered yet; when they are, your plan and billing portal will appear here.
        </div>
        <div className="mt-3"><Link href="/buy" className="btn-primary text-[12px]">Add credits</Link></div>
      </Panel>
      <Panel title={view === "billing" ? "billing history" : "usage history"} meta={
        <span className="seg"><button className={view === "billing" ? "on" : ""} onClick={() => setView("billing")}>billing</button><button className={view === "usage" ? "on" : ""} onClick={() => setView("usage")}>usage</button></span>
      } bodyClass="">
        {rows.length === 0 ? <div className="px-3 py-4 text-[11.5px] text-muted">Nothing here yet.</div> : (
          <div className="overflow-auto max-h-[28rem]">
            <table className="dtable">
              <thead><tr><th>when</th><th>type</th><th>credits</th><th>balance</th><th>detail</th>{view === "billing" && <th>paid</th>}</tr></thead>
              <tbody>
                {[...rows].reverse().map((t, i) => (
                  <tr key={i}>
                    <td className="whitespace-nowrap text-muted">{t.ts}</td>
                    <td>{t.type}</td>
                    <td className={`tabular-nums ${t.amount >= 0 ? "text-brand" : "text-bad"}`}>{t.amount >= 0 ? "+" : ""}{t.amount}</td>
                    <td className="tabular-nums">{t.balance}</td>
                    <td className="text-muted">{t.desc}</td>
                    {view === "billing" && <td className="tabular-nums">{t.price ? `$${t.price.toFixed(2)}` : "—"}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

function Onboarding({ account }: { account: Account }) {
  return (
    <Panel title="tutorial">
      <div className="text-[12px] text-muted">
        {account.onboarding?.completed
          ? `You finished the walkthrough${account.onboarding.completed_at ? ` on ${account.onboarding.completed_at}` : ""}. Replay it any time — it takes about two minutes.`
          : "The walkthrough is still open — it will show on your next visit to the dashboard."}
      </div>
      <div className="mt-3"><ReplayTourButton /></div>
      <div className="mt-4 pt-3 border-t border-divider">
        <div className="label mb-1.5">what it covers</div>
        <ol className="text-[11.5px] text-muted grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-0.5 list-decimal list-inside">
          {TOUR_STEPS.map((s) => <li key={s.title}>{s.title}</li>)}
        </ol>
      </div>
    </Panel>
  );
}
