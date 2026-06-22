"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Metric, Pill, BarRow, scoreKind, riskKind } from "@/components/ui";
import { OutcomePie, OutcomeBars, GuideRadar, CompareBars } from "@/components/Charts";
import { api } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";

export default function ProjectPage() {
  return <Shell><Dashboard /></Shell>;
}

const TABS = ["Guide Rankings", "Best Guide Set", "Outcome", "Compare"];

function whyChosen(g: any): [string, boolean][] {
  return [
    ["High predicted knockout probability", g.outcome.knockout_prob >= 0.55],
    ["High on-target efficiency", g.scores.on_target >= 0.6],
    ["Low off-target risk", g.off_target.risk_score < 0.2],
    ["Good GC content and complexity", g.gc_content >= 0.4 && g.gc_content <= 0.65 && g.scores.complexity >= 0.7],
    ["Well positioned for target disruption", g.scores.distance_to_target >= 0.5],
  ];
}

function Dashboard() {
  const { id } = useParams<{ id: string }>();
  const [proj, setProj] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState("");
  const [tab, setTab] = useState(0);

  useEffect(() => {
    setProj(null); setErr("");
    api.project(id)
      .then((p) => { setProj(p); setSel(p.selected_guide || p.response.guides[0]?.guide_id); })
      .catch((e) => setErr(e.message || "Failed to load project."));
  }, [id]);

  if (err) return <div className="text-bad font-semibold">{err}</div>;
  if (!proj) return <div className="text-muted">Loading project…</div>;

  const resp = proj.response;
  const guides: any[] = resp.guides;
  const byId: Record<string, any> = Object.fromEntries(guides.map((g) => [g.guide_id, g]));
  const g = byId[sel] || guides[0];
  const opt = resp.optimized_set;
  const req = resp.request;

  const onMean = guides.reduce((s, x) => s + x.scores.on_target, 0) / guides.length;
  const offMean = guides.reduce((s, x) => s + x.off_target.risk_score, 0) / guides.length;
  const koMean = guides.reduce((s, x) => s + x.outcome.knockout_prob, 0) / guides.length;
  const setScore = opt.selected_guide_ids.reduce((s: number, gid: string) => s + (byId[gid]?.final_score || 0), 0);
  const chosen = opt.selected_guide_ids.map((gid: string) => byId[gid]).filter(Boolean);
  const strand = (x: any) => (typeof x.strand === "string" ? x.strand : x.strand?.value || "+");

  function exportCsv() {
    const rows = guides.map((x: any, i: number) => ({
      rank: i + 1,
      guide_id: x.guide_id,
      sequence: x.sequence,
      pam: x.pam,
      strand: strand(x),
      position: x.position,
      gc_content: x.gc_content.toFixed(3),
      on_target: x.scores.on_target.toFixed(3),
      knockout_prob: x.outcome.knockout_prob.toFixed(3),
      frameshift_prob: x.outcome.frameshift_prob.toFixed(3),
      functional_disruption: x.outcome.functional_disruption_score.toFixed(3),
      off_target_risk: x.off_target.risk_score.toFixed(3),
      off_target_category: x.off_target.risk_category,
      final_score: x.final_score.toFixed(3),
      confidence: x.confidence.toFixed(3),
      in_optimized_set: opt.selected_guide_ids.includes(x.guide_id),
    }));
    downloadCsv(`${proj.name}_${id}_guides.csv`, rows);
  }

  return (
    <div>
      <div className="flex justify-between items-start">
        <div>
          <div className="font-display font-extrabold text-3xl">Design Result</div>
          <div className="text-muted font-medium">{req.cas_enzyme} ({guides[0].pam}) · {req.desired_outcome} · {req.organism} · {proj.name}</div>
        </div>
        <div className="text-right">
          <span className="inline-flex items-center gap-2 bg-brand/10 text-brand-dark border border-brand/30 rounded-xl px-3 py-2 font-bold">✓ Optimization complete</span>
          <div className="text-muted text-xs mt-1">Completed in {proj.elapsed}s · {opt.method}</div>
          <button onClick={exportCsv} className="btn-ghost mt-2 text-sm">⬇ Export results (CSV)</button>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4 mt-4">
        <Metric label="Candidate guides" value={guides.length} sub="PAM sites found" />
        <Metric label="Best single guide" value={resp.best_single_guide_id} sub={`Score ${guides[0].final_score.toFixed(3)}`} color="brand" />
        <Metric label={`Best ${req.set_size}-guide set`} value={opt.selected_guide_ids.map((s: string) => s.replace("gRNA_", "")).join(", ")} sub={`Set score ${setScore.toFixed(2)}`} color="brand" />
        <Metric label="Avg on-target" value={onMean.toFixed(2)} sub="across guides" />
        <Metric label="Avg off-target" value={offMean.toFixed(2)} sub="lower is better" color="warn" />
        <Metric label="Predicted KO" value={koMean.toFixed(2)} sub="population avg" color="good" />
      </div>

      {/* Selected guide band */}
      <div className="mt-5">
        <div className="label mb-1">Selected guide</div>
        <select className="input max-w-xs mb-3" value={sel} onChange={(e) => setSel(e.target.value)}>
          {guides.map((x) => <option key={x.guide_id}>{x.guide_id}</option>)}
        </select>
        <div className="grid grid-cols-[1.1fr_1.5fr_1.2fr] gap-4">
          <Card>
            <div className="font-display font-extrabold text-xl text-brand">{g.guide_id}</div>
            <div className="label mt-2">Sequence (5'→3')</div>
            <code className="text-sm bg-bg rounded px-1 text-brand-dark break-all">{g.sequence}</code>
            <div className="flex gap-4 mt-3 flex-wrap">
              {[["PAM", g.pam], ["Strand", strand(g)], ["Pos", g.position], ["GC", `${(g.gc_content * 100).toFixed(0)}%`], ["Total", g.final_score.toFixed(3)]].map(([k, v]) => (
                <div key={k as string}><div className="label">{k}</div><b className={k === "Total" ? "text-brand" : ""}>{v}</b></div>
              ))}
            </div>
          </Card>
          <Card>
            <CardTitle>Score breakdown</CardTitle>
            <BarRow label="On-target" value={g.scores.on_target} />
            <BarRow label="Knockout" value={g.outcome.knockout_prob} />
            <BarRow label="Off-target" value={g.off_target.risk_score} color={g.off_target.risk_score < 0.2 ? "#7A33A6" : "#C9892F"} />
            <BarRow label="GC content" value={g.scores.gc_content} color="#9B59B6" />
            <BarRow label="Complexity" value={g.scores.complexity} color="#9B59B6" />
            <BarRow label="Context" value={Math.min(1, g.context.multiplier)} />
            <BarRow label="Structure pen." value={g.scores.secondary_structure_penalty} color="#C9892F" />
          </Card>
          <Card>
            <CardTitle>Why this guide?</CardTitle>
            {whyChosen(g).map(([t, ok]) => (
              <div key={t} className="flex items-center gap-2 my-1 text-sm font-semibold">
                <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] font-extrabold ${ok ? "bg-brand/15 text-brand" : "bg-bg text-muted"}`}>{ok ? "✓" : "–"}</span>{t}
              </div>
            ))}
          </Card>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border mt-6 mb-4">
        {TABS.map((t, i) => (
          <button key={t} onClick={() => setTab(i)} className={`px-3 py-2 font-bold text-sm ${tab === i ? "text-brand border-b-2 border-brand" : "text-muted"}`}>{t}</button>
        ))}
      </div>

      {tab === 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-muted text-left text-xs uppercase">
              {["Rank", "Guide", "Sequence", "PAM", "Pos", "Strand", "On-target", "KO", "Off-target", "Total"].map((h) => <th key={h} className="py-1 pr-3 whitespace-nowrap">{h}</th>)}
            </tr></thead>
            <tbody>
              {guides.slice(0, 15).map((x, i) => (
                <tr key={x.guide_id} className={`border-t border-border ${x.guide_id === sel ? "bg-brand/5" : ""}`}>
                  <td className="py-1.5 pr-3">{i === 0 ? "⭐ " : ""}{i + 1}</td>
                  <td className="pr-3"><button className="text-brand font-extrabold" onClick={() => setSel(x.guide_id)}>{x.guide_id}</button></td>
                  <td className="pr-3"><code className="text-xs bg-bg rounded px-1">{x.sequence}</code></td>
                  <td className="pr-3">{x.pam}</td><td className="pr-3">{x.position}</td><td className="pr-3">{strand(x)}</td>
                  <td className="pr-3"><Pill value={x.scores.on_target.toFixed(2)} kind={scoreKind(x.scores.on_target)} /></td>
                  <td className="pr-3"><Pill value={x.outcome.knockout_prob.toFixed(2)} kind={scoreKind(x.outcome.knockout_prob)} /></td>
                  <td className="pr-3"><Pill value={x.off_target.risk_score.toFixed(2)} kind={riskKind(x.off_target.risk_score)} /></td>
                  <td className="pr-3 font-extrabold text-brand">{x.final_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-muted mt-2">Showing top 15 of {guides.length}. Click a guide id to inspect it above.</div>
        </Card>
      )}

      {tab === 1 && (
        <Card>
          <CardTitle>Optimized set: {opt.selected_guide_ids.join(", ")}</CardTitle>
          <div className="text-xs text-muted mb-2">method {opt.method} · objective {opt.objective_value}</div>
          {opt.tradeoffs?.map((t: string, i: number) => <div key={i} className="text-sm text-muted">• {t}</div>)}
          <div className="mt-3"><CompareBars guides={chosen} /></div>
        </Card>
      )}

      {tab === 2 && (
        <div className="grid grid-cols-2 gap-4">
          <Card><CardTitle>Predicted edit outcome — {g.guide_id}</CardTitle><OutcomePie outcome={g.outcome} /></Card>
          <Card><CardTitle>Outcome probabilities</CardTitle><OutcomeBars outcome={g.outcome} /></Card>
          <Card className="col-span-2"><CardTitle>Why {g.guide_id} ranks here</CardTitle><div className="text-sm">{g.explanation}</div></Card>
        </div>
      )}

      {tab === 3 && (
        <div className="grid grid-cols-2 gap-4">
          <Card><CardTitle>Top guides compared</CardTitle><CompareBars guides={guides.slice(0, 6)} /></Card>
          <Card><CardTitle>Profile — {g.guide_id}</CardTitle><GuideRadar guide={g} /></Card>
        </div>
      )}
    </div>
  );
}
