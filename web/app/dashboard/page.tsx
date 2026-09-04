"use client";
// User dashboard: the landing view after sign-in. Answers "what have I got,
// what happened recently, what should I do next" — and nothing administrative.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Panel, Metric } from "@/components/ui";
import { PageHeader, EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api, ProjectMeta, projectHref } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BRANDING } from "@/lib/branding";

export default function DashboardPage() {
  return <Shell><Dash /></Shell>;
}

function Dash() {
  const { account, refresh } = useAuth();
  const [projects, setProjects] = useState<ProjectMeta[] | null>(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    api.projects().then((p) => setProjects(p || [])).catch((e) => { setErr(e.message || "Could not load projects."); setProjects([]); });
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { load(); }, [load]);

  const all = (projects || []).filter((p) => !p.shared);
  const shared = (projects || []).filter((p) => p.shared);
  const active = all.filter((p) => !p.archived);
  const totalGuides = all.reduce((s, p) => s + (p.n_guides || 0), 0);
  const recent = [...active].sort((a, b) => (b.created || "").localeCompare(a.created || "")).slice(0, 8);
  const maxG = Math.max(1, ...recent.map((p) => p.n_guides || 0));
  const low = (account?.credits ?? 0) < 5;
  const firstName = account?.name?.split(" ")[0];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="overview"
        title={firstName ? `Welcome back, ${firstName}` : "Dashboard"}
        description={`Your CRISPR design projects and analyses in ${BRANDING.APP_NAME}.`}
        primary={<Link href="/new" className="btn-primary text-[12px]">＋ Create project</Link>}
        actions={low ? <Link href="/buy" className="btn-ghost text-[12px]">Add credits</Link> : undefined}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Projects" value={projects ? active.length : "—"} sub={all.length - active.length ? `${all.length - active.length} archived` : "active designs"} color="brand" />
        <Metric label="Analyses run" value={account?.runs ?? "—"} sub="lifetime design runs" />
        <Metric label="Guides evaluated" value={projects ? totalGuides : "—"} sub="across all projects" />
        <Metric label="Credits" value={account?.credits ?? "—"} sub={account?.plan || ""} color={low ? "bad" : "good"} />
      </div>

      {err && <ErrorState message={err} retry={load} />}

      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-4 items-start">
        <Panel title="recent projects" meta={projects ? `${active.length} active` : ""} bodyClass="">
          {projects === null ? <LoadingRows n={5} /> : recent.length === 0 ? (
            <EmptyState
              title="No projects yet."
              body="A project is one design run: paste a target sequence, choose a nuclease and outcome, and get ranked, explained guide RNAs."
              action={<Link href="/new" className="btn-primary text-[12px]">Create your first project</Link>}
            />
          ) : (
            <table className="dtable">
              <thead><tr><th>project</th><th>guides</th><th>best guide</th><th>created</th></tr></thead>
              <tbody>
                {recent.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link>
                      <span className="ml-2 text-faint text-[10.5px] tabular-nums">{p.id}</span>
                    </td>
                    <td className="tabular-nums">{p.n_guides ?? "—"}</td>
                    <td className="seqtext text-[11px]">{p.best_guide || "—"}</td>
                    <td className="text-muted whitespace-nowrap">{p.created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel title="next steps">
            <div className="flex flex-col divide-y divide-divider">
              <Action href="/new" title="New analysis" body="Design guides for a target sequence." />
              <Action href="/collaborations" title="Collaborations" body={shared.length ? `${shared.length} project${shared.length === 1 ? "" : "s"} shared with you.` : "Projects shared with you by other researchers."} />
              <Action href="/account" title="Account & settings" body="Profile, password, usage history." />
              <Action href="/buy" title="Credits" body={`${account?.credits ?? 0} available · 5 per design run.`} />
              <Action href="/disclaimer" title="How to read the scores" body="What predictions mean and what to validate." />
            </div>
          </Panel>

          {shared.length > 0 && (
            <Panel title="shared with me" meta={`${shared.length}`} bodyClass="">
              <table className="dtable">
                <tbody>
                  {shared.slice(0, 5).map((p) => (
                    <tr key={p.uid || p.id}>
                      <td><Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link>
                        <span className="block text-[10.5px] text-faint">{p.owner_name || p.owner_email}</span></td>
                      <td className="text-right"><span className={p.role === "EDITOR" ? "tag-good" : "tag-warn"}>{p.role.toLowerCase()}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {shared.length > 5 && <div className="px-3 py-1.5 text-[10.5px]"><Link href="/collaborations" className="text-brand hover:underline">all {shared.length} →</Link></div>}
            </Panel>
          )}

          {recent.length > 0 && (
            <Panel title="candidate guides per project">
              <div className="flex flex-col gap-1.5">
                {recent.slice(0, 6).map((p) => (
                  <div key={p.id} className="flex items-center gap-2 text-[11px]">
                    <span className="w-24 text-muted truncate" title={p.name}>{p.name}</span>
                    <span className="flex-1 h-[6px] bg-track overflow-hidden">
                      <span className="block h-full bg-series" style={{ width: `${((p.n_guides || 0) / maxG) * 100}%` }} />
                    </span>
                    <span className="w-7 text-right tabular-nums text-cell">{p.n_guides ?? 0}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function Action({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link href={href} className="group flex items-start gap-3 py-2 first:pt-0 last:pb-0">
      <span className="text-brand mt-0.5">›</span>
      <span className="min-w-0">
        <span className="block text-[12px] text-ink group-hover:text-brand">{title}</span>
        <span className="block text-[11px] text-faint">{body}</span>
      </span>
    </Link>
  );
}
