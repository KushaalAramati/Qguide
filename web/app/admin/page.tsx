"use client";
import { useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Metric, Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";

export default function AdminPage() {
  return <Shell><AdminView /></Shell>;
}

function AdminView() {
  const { account } = useAuth();
  const [users, setUsers] = useState<any[] | null>(null);
  const [err, setErr] = useState("");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [savingEmail, setSavingEmail] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    setErr("");
    try {
      const u = await api.adminUsers();
      setUsers(u);
      setEdits(Object.fromEntries(u.map((x: any) => [x.email, String(x.credits)])));
    } catch (e: any) {
      setErr(e.status === 403 ? "You don't have admin access. Ask an admin to add your email to ADMIN_EMAILS." : (e.message || "Failed to load users."));
      setUsers([]);
    }
  }
  useEffect(() => { load(); }, []);

  async function save(email: string) {
    const val = parseInt(edits[email]);
    if (isNaN(val) || val < 0) return;
    setSavingEmail(email); setMsg("");
    try {
      await api.adminSetCredits(email, val);
      setMsg(`✓ Set ${email} to ${val} credits.`);
      await load();
    } catch (e: any) {
      setErr(e.message || "Update failed.");
    } finally {
      setSavingEmail("");
    }
  }

  if (!account) return null;

  const totalCredits = (users || []).reduce((s, u) => s + u.credits, 0);
  const totalRuns = (users || []).reduce((s, u) => s + u.runs, 0);

  function exportUsers() {
    const rows = (users || []).map((u) => ({
      name: u.name,
      email: u.email,
      plan: u.plan,
      credits: u.credits,
      design_runs: u.runs,
      created: u.created,
      last_login: u.last_login || "",
    }));
    downloadCsv(`qguide_users_${new Date().toISOString().slice(0, 10)}.csv`, rows);
  }

  return (
    <div>
      <div className="flex justify-between items-start">
        <div>
          <div className="font-display font-extrabold text-3xl">🛡️ Admin</div>
          <div className="text-muted font-medium">Users, activity, and credit control.</div>
        </div>
        {users && users.length > 0 && (
          <button onClick={exportUsers} className="btn-ghost text-sm">⬇ Export analytics (CSV)</button>
        )}
      </div>

      {err && <div className="mt-4 card !bg-bad/5 border-bad/30 text-bad font-semibold">{err}</div>}

      {users && users.length > 0 && (
        <>
          <div className="grid grid-cols-3 gap-4 mt-4">
            <Metric label="Total users" value={users.length} sub="signed up" color="brand" />
            <Metric label="Credits in circulation" value={`💎 ${totalCredits}`} sub="across all users" />
            <Metric label="Total design runs" value={totalRuns} sub="all-time" color="good" />
          </div>

          {msg && <div className="mt-3 text-good font-semibold">{msg}</div>}

          <Card className="mt-5 overflow-x-auto">
            <CardTitle>All users</CardTitle>
            <table className="w-full text-sm">
              <thead><tr className="text-muted text-left text-xs uppercase">
                {["Name", "Email", "Plan", "Runs", "Created", "Last login", "Credits", "Set credits"].map((h) => (
                  <th key={h} className="py-2 pr-3 whitespace-nowrap">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.email} className="border-t border-border">
                    <td className="py-2 pr-3 font-semibold">{u.name}</td>
                    <td className="pr-3">{u.email}</td>
                    <td className="pr-3">{u.plan}</td>
                    <td className="pr-3">{u.runs}</td>
                    <td className="pr-3 whitespace-nowrap text-muted">{u.created}</td>
                    <td className="pr-3 whitespace-nowrap text-muted">{u.last_login || "—"}</td>
                    <td className="pr-3 font-extrabold text-brand">{u.credits}</td>
                    <td className="pr-3">
                      <div className="flex gap-1 items-center">
                        <input type="number" min={0} className="input !py-1 !px-2 w-20"
                          value={edits[u.email] ?? ""} onChange={(e) => setEdits({ ...edits, [u.email]: e.target.value })} />
                        <Button onClick={() => save(u.email)} disabled={savingEmail === u.email}>
                          {savingEmail === u.email ? "…" : "Set"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-xs text-muted mt-2">Setting credits records an "admin" entry in that user's transaction history.</div>
          </Card>
        </>
      )}
    </div>
  );
}
