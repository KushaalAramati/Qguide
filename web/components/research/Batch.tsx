"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel, Button } from "@/components/ui";
import { ErrorState } from "@/components/PageHeader";
import { api, projectHref } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BRANDING } from "@/lib/branding";
import { ParamsForm, DesignParams, DEFAULT_PARAMS, paramsSummary } from "./ParamsForm";
import type { Template } from "./Templates";

/**
 * Batch multi-target analysis. Parses FASTA (or "name<TAB>sequence" lines),
 * runs each target through the pipeline with one shared configuration, and
 * files the resulting projects in a folder. Requires the RESEARCHER role
 * (server-enforced); other accounts see exactly why and who can grant it.
 */
type Target = { name: string; sequence: string };

function parseTargets(text: string): Target[] {
  const out: Target[] = [];
  const lines = text.split(/\r?\n/);
  let cur: Target | null = null;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith(">")) {
      if (cur) out.push(cur);
      cur = { name: line.slice(1).trim().split(/\s+/)[0] || `target_${out.length + 1}`, sequence: "" };
    } else if (/^[^\s,\t]+[\t,]\s*[ACGTNacgtn]+$/.test(line)) {
      if (cur) { out.push(cur); cur = null; }
      const [name, seq] = line.split(/[\t,]/);
      out.push({ name: name.trim(), sequence: seq.trim().toUpperCase() });
    } else if (cur) {
      cur.sequence += line.replace(/[^ACGTNacgtn]/g, "").toUpperCase();
    } else if (/^[ACGTNacgtn\s]+$/.test(line)) {
      out.push({ name: `target_${out.length + 1}`, sequence: line.replace(/\s/g, "").toUpperCase() });
    }
  }
  if (cur) out.push(cur);
  return out.filter((t) => t.sequence.length > 0);
}

export function Batch({ template, onTemplateUsed }: { template: Template | null; onTemplateUsed?: () => void }) {
  const { account, refresh } = useAuth();
  const [limits, setLimits] = useState<{ max_targets: number; credits_per_target: number; allowed: boolean; role: string } | null>(null);
  const [text, setText] = useState("");
  const [params, setParams] = useState<DesignParams>({ ...DEFAULT_PARAMS });
  const [folder, setFolder] = useState("");
  const [experiment, setExperiment] = useState("");
  const [tags, setTags] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState<any>(null);

  useEffect(() => { api.batchLimits().then(setLimits).catch(() => {}); }, []);
  useEffect(() => {
    if (template) { setParams({ ...DEFAULT_PARAMS, ...template.params }); onTemplateUsed?.(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template]);

  const targets = parseTargets(text);
  const tooShort = targets.filter((t) => t.sequence.length < 25);
  const max = limits?.max_targets ?? 10;
  const cost = targets.length * (limits?.credits_per_target ?? 5);
  const credits = account?.credits ?? 0;
  const canRun = !!limits?.allowed && targets.length > 0 && targets.length <= max && tooShort.length === 0 && credits >= cost && !busy;

  async function run() {
    if (!canRun) return;
    if (!window.confirm(`Run ${targets.length} target${targets.length === 1 ? "" : "s"} for ${cost} credits?`)) return;
    setBusy(true); setErr(""); setResult(null);
    try {
      const r = await api.runBatch({
        targets, params, folder_name: folder.trim() || undefined, experiment_name: experiment.trim() || undefined,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setResult(r); await refresh();
    } catch (e: any) { setErr(e.message || "Batch failed."); } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-4">
      {limits && !limits.allowed && (
        <div className="border border-warn/40 bg-warn/[0.06] px-3 py-2.5 text-[11.5px] text-warn leading-relaxed">
          Batch analysis is available to accounts with the <b>Researcher</b> role (yours is {limits.role.toLowerCase()}).
          An administrator can grant it from the Admin dashboard, or contact{" "}
          <a className="underline" href={`mailto:${BRANDING.SUPPORT_EMAIL}`}>{BRANDING.SUPPORT_EMAIL}</a>.
          You can still prepare targets and templates here; single runs remain available under New Analysis.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 items-start">
        <div className="flex flex-col gap-4">
          <Panel title="1 · targets" meta={`${targets.length} parsed · max ${max}`}>
            <textarea
              className="input seqtext text-[12px] h-44"
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              placeholder={">BRCA1_exon11\nATGGCCTGACCGGATGCACC...\n>TP53_exon5\nGGATCCAATTGGCCAATTCG...\n\nor one per line:  KRAS<TAB>ATGACTGAATATAAACTTGTGG..."}
            />
            <div className="text-[10.5px] text-faint mt-1.5">
              FASTA records or <code>name&lt;tab&gt;sequence</code> lines. Each target becomes its own project so every project view and export works as usual.
            </div>
            {targets.length > 0 && (
              <table className="dtable mt-3">
                <thead><tr><th>#</th><th>target</th><th>length</th><th /></tr></thead>
                <tbody>
                  {targets.map((t, i) => (
                    <tr key={i}>
                      <td className="tabular-nums text-faint">{i + 1}</td>
                      <td className="text-ink">{t.name}</td>
                      <td className="tabular-nums">{t.sequence.length} bp</td>
                      <td>{t.sequence.length < 25 ? <span className="tag-bad">too short</span> : i >= max ? <span className="tag-warn">over limit</span> : <span className="text-faint">ok</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title="2 · shared configuration" meta={paramsSummary(params)}>
            <ParamsForm value={params} onChange={setParams} />
          </Panel>

          <Panel title="3 · organise results">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <label className="block"><span className="label mb-1 block">Folder (optional)</span>
                <input className="input" value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="e.g. DNA repair screen" /></label>
              <label className="block"><span className="label mb-1 block">Experiment name (optional)</span>
                <input className="input" value={experiment} onChange={(e) => setExperiment(e.target.value)} placeholder="stored in each project's notes" /></label>
              <label className="block"><span className="label mb-1 block">Tags (comma-separated)</span>
                <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="screen, pilot" /></label>
            </div>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 lg:sticky lg:top-0">
          <Panel title="run batch">
            {[["Targets", `${targets.length}`], ["Configuration", paramsSummary(params)], ["Cost", `${cost} credits`], ["Balance", `${credits} credits`]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 py-1.5 border-b border-divider text-[11.5px] last:border-0">
                <span className="text-faint">{k}</span><span className="text-ink text-right">{v}</span></div>
            ))}
            {err && <div className="mt-3"><ErrorState message={err} /></div>}
            <div className="mt-3">
              <Button onClick={run} disabled={!canRun} full>{busy ? `Running ${targets.length} targets…` : "Run batch analysis"}</Button>
            </div>
            {targets.length > max && <div className="text-[10.5px] text-warn mt-1.5">Reduce to {max} targets per batch.</div>}
            {credits < cost && targets.length > 0 && <div className="text-[10.5px] text-warn mt-1.5">Not enough credits — <Link href="/buy" className="underline">add credits</Link>.</div>}
            {busy && <div className="text-[10.5px] text-faint mt-1.5">Each target runs the full pipeline; this can take a little while.</div>}
          </Panel>

          {result && (
            <Panel title="results" meta={`${result.ok} ok · ${result.failed} failed · ${result.elapsed}s`} bodyClass="">
              <table className="dtable">
                <thead><tr><th>target</th><th>guides</th><th>best</th><th>score</th></tr></thead>
                <tbody>
                  {result.results.map((r: any, i: number) => (
                    <tr key={i}>
                      <td>{r.ok ? <Link href={projectHref({ id: r.project_id, uid: r.uid, shared: false })} className="text-brand hover:underline">{r.name}</Link> : <span className="text-ink">{r.name}</span>}
                        {!r.ok && <div className="text-[10.5px] text-bad">{r.error}</div>}</td>
                      <td className="tabular-nums">{r.n_guides ?? "—"}</td>
                      <td className="seqtext text-[11px]">{r.best_guide ?? "—"}</td>
                      <td className="tabular-nums">{r.best_score ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.folder_id && <div className="px-3 py-2 text-[10.5px] text-faint">Filed in folder {folder || result.folder_id} — <Link href="/projects" className="text-brand hover:underline">open projects</Link>.</div>}
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
