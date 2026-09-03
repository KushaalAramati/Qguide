"use client";
// Account sections (Feature 5): Profile · Security · Credits · Billing · Usage.
import { useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Metric, Button } from "@/components/ui";
import { PageHeader } from "@/components/PageHeader";
import { ReplayTourButton } from "@/components/Onboarding";
import { TOUR_STEPS } from "@/lib/tour";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function AccountPage() { return <Shell><AccountView /></Shell>; }

const SECTIONS = ["Profile", "Security", "Credits", "Billing", "Usage", "Onboarding"] as const;
type Sec = typeof SECTIONS[number];

function AccountView() {
  const { account, setAccount, signOut } = useAuth();
  const [sec, setSec] = useState<Sec>("Profile");
  if (!account) return null;
  const used = account.transactions.filter((t) => t.type === "usage").reduce((s, t) => s - t.amount, 0);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="settings"
        title="Account"
        description={`${account.name} · ${account.email}${account.institution ? ` · ${account.institution}` : ""}`}
        actions={<span className="text-[11px] text-faint">{account.role?.toLowerCase().replace("_", " ")}</span>}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="Credit balance" value={account.credits} sub="available" color="brand" />
        <Metric label="Plan" value={account.plan} sub={`since ${account.created.slice(0, 10)}`} />
        <Metric label="Design runs" value={account.runs} sub={`${used} credits used`} color="good" />
        <Metric label="Transactions" value={account.transactions.length} sub="lifetime" />
      </div>

      <div className="flex gap-1 border-b border-border">
        {SECTIONS.map((s) => (
          <button key={s} onClick={() => setSec(s)}
            className={`px-3 py-2 text-sm font-semibold border-b-2 -mb-px ${sec === s ? "text-brand border-brand" : "text-muted border-transparent hover:text-ink"}`}>{s}</button>
        ))}
      </div>

      {sec === "Profile" && <ProfileSection account={account} setAccount={setAccount} signOut={signOut} />}
      {sec === "Security" && <SecuritySection />}
      {sec === "Credits" && (
        <Card>
          <CardTitle>Credits</CardTitle>
          <div className="text-2xl font-display font-extrabold text-brand">{account.credits} <span className="text-sm text-muted font-sans">credits available</span></div>
          <div className="text-sm text-muted mt-1">Each design run costs 5 credits. Plan: {account.plan}.</div>
          <div className="mt-4"><Link href="/buy"><Button>Purchase credits</Button></Link></div>
        </Card>
      )}
      {sec === "Billing" && <Ledger rows={account.transactions.filter((t) => t.type === "purchase" || t.type === "bonus" || t.type === "admin")} title="Billing history" empty="No purchases yet." showPaid />}
      {sec === "Usage" && <Ledger rows={account.transactions.filter((t) => t.type === "usage")} title="Usage history" empty="No usage yet." />}
      {sec === "Onboarding" && (
        <Card>
          <CardTitle>Tutorial</CardTitle>
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
        </Card>
      )}
    </div>
  );
}

function ProfileSection({ account, setAccount, signOut }: any) {
  const [name, setName] = useState(account.name);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  async function save() {
    setBusy(true); setMsg("");
    try { const a = await api.updateProfile({ name }); setAccount(a); setMsg("Saved."); }
    catch (e: any) { setMsg(e.message || "Failed."); } finally { setBusy(false); }
  }
  return (
    <Card>
      <CardTitle>Profile</CardTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
        <div><div className="label mb-1">Full name</div><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div><div className="label mb-1">Email</div><input className="input bg-bg" value={account.email} disabled /></div>
        <div><div className="label mb-1">Plan</div><input className="input bg-bg" value={account.plan} disabled /></div>
        <div><div className="label mb-1">Member since</div><input className="input bg-bg" value={account.created} disabled /></div>
      </div>
      <div className="flex items-center gap-3 mt-4">
        <Button onClick={save} disabled={busy || !name.trim()}>Save profile</Button>
        <Button variant="ghost" onClick={signOut}>Log out</Button>
        {msg && <span className="text-sm text-muted">{msg}</span>}
      </div>
    </Card>
  );
}

function SecuritySection() {
  const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [cf, setCf] = useState("");
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState(""); const [ok, setOk] = useState(false);
  async function change() {
    setMsg(""); setOk(false);
    if (nw.length < 6) return setMsg("New password must be at least 6 characters.");
    if (nw !== cf) return setMsg("New passwords do not match.");
    setBusy(true);
    try { await api.changePassword(cur, nw); setOk(true); setMsg("Password updated."); setCur(""); setNw(""); setCf(""); }
    catch (e: any) { setMsg(e.message || "Failed."); } finally { setBusy(false); }
  }
  return (
    <Card>
      <CardTitle>Password & security</CardTitle>
      <div className="flex flex-col gap-3 max-w-sm">
        <div><div className="label mb-1">Current password</div><input type="password" className="input" value={cur} onChange={(e) => setCur(e.target.value)} /></div>
        <div><div className="label mb-1">New password</div><input type="password" className="input" value={nw} onChange={(e) => setNw(e.target.value)} /></div>
        <div><div className="label mb-1">Confirm new password</div><input type="password" className="input" value={cf} onChange={(e) => setCf(e.target.value)} /></div>
        <div className="flex items-center gap-3">
          <Button onClick={change} disabled={busy || !cur || !nw}>Change password</Button>
          {msg && <span className={`text-sm ${ok ? "text-good" : "text-bad"}`}>{msg}</span>}
        </div>
      </div>
    </Card>
  );
}

function Ledger({ rows, title, empty, showPaid }: { rows: any[]; title: string; empty: string; showPaid?: boolean }) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {rows.length === 0 ? <div className="text-sm text-muted">{empty}</div> : (
        <div className="overflow-auto max-h-[28rem]">
          <table className="w-full text-sm">
            <thead><tr className="text-muted text-left text-xs uppercase">
              {["When", "Type", "Credits", "Balance", "Detail", ...(showPaid ? ["Paid"] : [])].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}
            </tr></thead>
            <tbody>
              {[...rows].reverse().map((t, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="py-1.5 pr-3 whitespace-nowrap">{t.ts}</td>
                  <td className="pr-3 capitalize">{t.type}</td>
                  <td className={`pr-3 font-bold ${t.amount >= 0 ? "text-good" : "text-bad"}`}>{t.amount >= 0 ? "+" : ""}{t.amount}</td>
                  <td className="pr-3">{t.balance}</td>
                  <td className="pr-3">{t.desc}</td>
                  {showPaid && <td className="pr-3">{t.price ? `$${t.price.toFixed(2)}` : "—"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
