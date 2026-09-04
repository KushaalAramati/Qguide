"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel, Button } from "@/components/ui";
import { EmptyState, ErrorState } from "@/components/PageHeader";
import { api, ProjectMeta, projectHref } from "@/lib/api";

/** Side-by-side comparison of 2–4 projects the user can open. */
export function Compare() {
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState<any>(null);

  useEffect(() => { api.projects().then((p) => setProjects(p.filter((x) => !x.archived))).catch(() => {}); }, []);
  const key = (p: ProjectMeta) => (p.shared && p.uid ? p.uid : p.id);
  const toggle = (k: string) => setPicked((s) => (s.includes(k) ? s.filter((x) => x !== k) : s.length < 4 ? [...s, k] : s));

  async function run() {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api.compareProjects(picked)); } catch (e: any) { setErr(e.message || "Comparison failed."); } finally { setBusy(false); }
  }

  const shown = projects.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(q.toLowerCase()));
  const fmt = (v: any) => (typeof v === "number" ? v.toFixed(3) : v ?? "—");

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4 items-start">
        <Panel title="pick 2–4 projects" meta={`${picked.length} selected`} bodyClass="">
          <div className="px-2 pt-2">
            <input className="input !py-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter" aria-label="Filter projects" />
          </div>
          <div className="max-h-[360px] overflow-auto py-1">
            {shown.map((p) => {
              const k = key(p);
              const on = picked.includes(k);
              return (
                <label key={k} className={`flex items-center gap-2 px-3 py-1 text-[11.5px] cursor-pointer ${on ? "bg-brand/[0.08] text-brand" : "text-muted hover:text-ink"}`}>
                  <input type="checkbox" checked={on} onChange={() => toggle(k)} disabled={!on && picked.length >= 4} />
                  <span className="truncate flex-1">{p.name}</span>
                  <span className="text-[10px] text-faint">{p.shared ? p.role.toLowerCase() : p.id}</span>
                </label>
              );
            })}
            {shown.length === 0 && <div className="px-3 py-2 text-[11px] text-faint">No projects.</div>}
          </div>
          <div className="px-3 py-2 border-t border-divider">
            <Button onClick={run} disabled={busy || picked.length < 2} full>{busy ? "Comparing…" : "Compare"}</Button>
          </div>
        </Panel>

        <div className="min-w-0">
          {err && <ErrorState message={err} />}
          {!res && !err && <Panel title="comparison"><EmptyState title="Select two or more projects and press Compare." body="You will get inputs, score statistics, the optimised sets and top guides side by side — and any protospacers that appear in more than one project." /></Panel>}
          {res && (
            <Panel title="comparison" meta={`${res.projects.length} projects`} bodyClass="overflow-x-auto">
              <table className="dtable min-w-[640px]">
                <thead><tr><th className="w-40" /> {res.projects.map((p: any) => <th key={p.uid}><Link href={projectHref({ id: p.id, uid: p.uid, shared: p.role !== "OWNER" })} className="text-brand hover:underline normal-case tracking-normal text-[11.5px]">{p.name}</Link></th>)}</tr></thead>
                <tbody>
                  {[
                    ["organism", (p: any) => p.inputs.organism], ["nuclease", (p: any) => p.inputs.cas_enzyme],
                    ["outcome", (p: any) => p.inputs.desired_outcome], ["risk tolerance", (p: any) => p.inputs.risk_tolerance],
                    ["sequence length", (p: any) => `${p.inputs.sequence_length} bp`], ["optimizer", (p: any) => p.inputs.optimizer_mode],
                    ["candidate guides", (p: any) => p.stats.n_guides], ["mean on-target", (p: any) => fmt(p.stats.mean_on_target)],
                    ["mean off-target risk", (p: any) => fmt(p.stats.mean_off_target_risk)], ["high-risk guides", (p: any) => p.stats.high_risk_guides],
                    ["mean final score", (p: any) => fmt(p.stats.mean_final_score)], ["set · mean score", (p: any) => fmt(p.stats.set_mean_final_score)],
                    ["set · mean risk", (p: any) => fmt(p.stats.set_mean_off_target_risk)], ["set method", (p: any) => p.optimized_set.method],
                    ["optimised set", (p: any) => p.optimized_set.guide_ids.join(", ")],
                    ["experiment", (p: any) => p.metadata?.experiment_name || "—"], ["cell line", (p: any) => p.metadata?.cell_line || "—"],
                  ].map(([label, f]: any) => (
                    <tr key={label}><td className="text-faint">{label}</td>{res.projects.map((p: any) => <td key={p.uid} className="tabular-nums">{f(p)}</td>)}</tr>
                  ))}
                  <tr><td className="text-faint align-top">top guides</td>
                    {res.projects.map((p: any) => (
                      <td key={p.uid} className="align-top">
                        {p.top_guides.map((g: any) => (
                          <div key={g.guide_id} className="text-[10.5px] py-0.5">
                            <span className={g.in_set ? "text-brand" : "text-cell"}>{g.guide_id}</span> <span className="seqtext">{g.sequence}</span>
                            <span className="text-faint"> {g.final_score.toFixed(3)}</span>
                          </div>
                        ))}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
              {res.common_top_guides.length > 0 && (
                <div className="px-3 py-2 text-[11px] text-muted border-t border-divider">Protospacers shared across projects: <span className="seqtext">{res.common_top_guides.join(", ")}</span></div>
              )}
              <div className="caveat">{res.disclaimer}</div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
