"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel } from "@/components/ui";
import { EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api, projectHref } from "@/lib/api";

export function History() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.researchHistory(100).then(setData).catch((e) => setErr(e.message || "Could not load history.")); }, []);
  if (err) return <ErrorState message={err} />;
  if (!data) return <LoadingRows n={6} />;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
      <Panel title="analysis runs" meta={`${data.events.length} events`} bodyClass="">
        {data.events.length === 0 ? <EmptyState title="No analyses yet." body="Design runs, re-runs and batch runs appear here as they happen." /> : (
          <table className="dtable">
            <thead><tr><th>when</th><th>run</th><th>credits</th></tr></thead>
            <tbody>
              {data.events.map((e: any, i: number) => (
                <tr key={i}><td className="text-muted whitespace-nowrap">{e.ts}</td><td>{e.desc}</td><td className="tabular-nums text-bad">{e.amount}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="projects" meta={`${data.projects.length}`} bodyClass="">
        {data.projects.length === 0 ? <EmptyState title="No projects yet." /> : (
          <table className="dtable">
            <thead><tr><th>project</th><th>guides</th><th>role</th><th>created</th></tr></thead>
            <tbody>
              {data.projects.map((p: any) => (
                <tr key={p.uid || p.id}>
                  <td><Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link>{p.archived && <span className="ml-2 text-[10px] text-faint">archived</span>}</td>
                  <td className="tabular-nums">{p.n_guides ?? "—"}</td>
                  <td className="text-muted">{(p.role || "OWNER").toLowerCase()}</td>
                  <td className="text-muted whitespace-nowrap">{p.created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
