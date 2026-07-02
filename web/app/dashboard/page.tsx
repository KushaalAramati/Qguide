"use client";
// Main dashboard (Feature 8): overview after login.
import { useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Metric } from "@/components/ui";
import { api, Account } from "@/lib/api";

export default function DashboardPage() {
  return <Shell><Dash /></Shell>;
}

function Dash() {
  const [acct, setAcct] = useState<Account | null>(null);
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    api.me().then(setAcct).catch(() => {});
    api.projects().then((p) => setProjects(p || [])).catch(() => {});
  }, []);

  const totalGuides = projects.reduce((s, p) => s + (p.n_guides || 0), 0);
  const recent = [...projects].slice(-6).reverse();
  const maxG = Math.max(1, ...projects.map((p) => p.n_guides || 0));

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-between items-end">
        <div>
          <div className="font-display font-extrabold text-3xl">Dashboard</div>
          <div className="text-muted">{acct ? `Welcome back, ${acct.name}.` : "Loading…"}</div>
        </div>
        <Link href="/new" className="btn-primary text-sm">＋ New project</Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="Projects" value={projects.length} sub="total designs" color="brand" />
        <Metric label="Analyses run" value={acct?.runs ?? "—"} sub="lifetime" />
        <Metric label="Guides evaluated" value={totalGuides} sub="across projects" />
        <Metric label="Credits" value={acct?.credits ?? "—"} sub={acct?.plan || ""} color={acct && acct.credits < 5 ? "bad" : "good"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4 items-start">
        <Card>
          <div className="flex items-center justify-between mb-2">
            <CardTitle>Recent projects</CardTitle>
            <Link href="/new" className="text-brand text-sm font-semibold">New →</Link>
          </div>
          {recent.length === 0 ? (
            <div className="text-sm text-muted py-6 text-center">
              No projects yet. <Link href="/new" className="text-brand font-semibold">Create your first design →</Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead><tr className="text-muted text-left text-xs uppercase">
                {["Project", "Guides", "Best", "Created"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}
              </tr></thead>
              <tbody>
                {recent.map((p) => (
                  <tr key={p.id} className="border-t border-border">
                    <td className="py-2 pr-3"><Link href={`/project/${p.id}`} className="text-brand font-semibold">{p.name}</Link> <span className="text-muted text-xs">· {p.id}</span></td>
                    <td className="pr-3">{p.n_guides ?? "—"}</td>
                    <td className="pr-3 font-mono text-xs">{p.best_guide || "—"}</td>
                    <td className="pr-3 text-muted text-xs">{p.created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card>
          <CardTitle>Project activity</CardTitle>
          <div className="text-xs text-muted mb-3">Candidate guides per recent project</div>
          {recent.length === 0 ? <div className="text-sm text-muted">—</div> : (
            <div className="flex flex-col gap-2">
              {recent.map((p) => (
                <div key={p.id} className="flex items-center gap-2">
                  <span className="w-24 text-xs text-muted truncate">{p.name}</span>
                  <div className="flex-1 h-2.5 rounded-full bg-bg overflow-hidden">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${((p.n_guides || 0) / maxG) * 100}%` }} />
                  </div>
                  <span className="w-8 text-right text-xs font-bold">{p.n_guides ?? 0}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 pt-3 border-t border-border">
            <div className="label mb-1">Quick actions</div>
            <div className="flex flex-col gap-1.5 text-sm">
              <Link href="/new" className="text-brand font-semibold">＋ Start a new guide design</Link>
              <Link href="/buy" className="text-brand font-semibold">◈ Purchase credits</Link>
              <Link href="/account" className="text-brand font-semibold">◔ Account & billing</Link>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
