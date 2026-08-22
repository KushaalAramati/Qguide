"use client";
// Basic Results (Feature 7) — input summary, headline metrics, and the selected guide.
import Link from "next/link";
import { Card, CardTitle, Metric, BarRow } from "@/components/ui";
import { EnsembleBadges, EnsemblePanel } from "@/components/Ensemble";
import { useProject } from "@/lib/projectCtx";
import { downloadCsv } from "@/lib/csv";

const strandOf = (x: any) => (typeof x?.strand === "string" ? x.strand : x?.strand?.value || "+");

function whyChosen(g: any): [string, boolean][] {
  return [
    ["High predicted knockout probability", g.outcome.knockout_prob >= 0.55],
    ["High on-target efficiency", g.scores.on_target >= 0.6],
    ["Low off-target risk", g.off_target.risk_score < 0.2],
    ["Good GC content and complexity", g.gc_content >= 0.4 && g.gc_content <= 0.65 && g.scores.complexity >= 0.7],
    ["Well positioned for target disruption", g.scores.distance_to_target >= 0.5],
  ];
}

export default function BasicResults() {
  const { id, proj, req, opt, guides, byId, fullSeq, sel, setSel, g } = useProject();

  const strongest = guides[0];
  const safest = [...guides].sort((a, b) => a.off_target.risk_score - b.off_target.risk_score)[0];
  const topKo = [...guides].sort((a, b) => b.outcome.knockout_prob - a.outcome.knockout_prob)[0];
  const topConf = [...guides].sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
  const highRisk = guides.filter((x) => x.off_target.risk_score >= 0.4).length;
  const pamCount = guides.length;

  function exportCsv() {
    const rows = guides.map((x: any, i: number) => ({
      rank: i + 1, guide_id: x.guide_id, sequence: x.sequence, pam: x.pam,
      strand: strandOf(x), position: x.position, gc_content: x.gc_content.toFixed(3),
      on_target: x.scores.on_target.toFixed(3), knockout_prob: x.outcome.knockout_prob.toFixed(3),
      off_target_risk: x.off_target.risk_score.toFixed(3), final_score: x.final_score.toFixed(3),
      confidence: x.confidence.toFixed(3), in_optimized_set: opt.selected_guide_ids.includes(x.guide_id),
    }));
    downloadCsv(`${proj.name}_${id}_guides.csv`, rows);
  }

  const info: [string, any][] = [
    ["Organism", req.organism], ["Cas enzyme", req.cas_enzyme], ["PAM", g.pam],
    ["Desired outcome", req.desired_outcome], ["Cell type", req.cell_type || "—"],
    ["Delivery", req.delivery_method || "—"], ["Temperature", req.temperature != null ? `${req.temperature}°C` : "—"],
    ["Sequence length", `${fullSeq.length} bp`], ["Candidate guides", pamCount],
    ["Set size", req.set_size], ["Optimizer", `${opt.mode} · ${opt.preset || "balanced"}`],
    ["Status", "✓ Complete"],
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <CardTitle>Overview</CardTitle>
        <div className="flex gap-2">
          <Link href={`/project/${id}/ensemble`} className="btn-ghost text-sm">Ensemble breakdown</Link>
          <button onClick={exportCsv} className="btn-ghost text-sm">Export CSV</button>
        </div>
      </div>

      {/* headline summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Metric label="Strongest" value={strongest.guide_id} sub={`score ${strongest.final_score.toFixed(3)}`} color="brand" />
        <Metric label="Safest" value={safest.guide_id} sub={`off-tgt ${safest.off_target.risk_score.toFixed(2)}`} color="good" />
        <Metric label="Highest KO" value={topKo.guide_id} sub={`${(topKo.outcome.knockout_prob * 100).toFixed(0)}%`} />
        <Metric label="Most confident" value={topConf.guide_id} sub={`${((topConf.confidence || 0) * 100).toFixed(0)}%`} />
        <Metric label="High-risk off-tgt" value={highRisk} sub="guides ≥ 0.4" color={highRisk ? "warn" : "good"} />
      </div>

      {/* input summary */}
      <Card>
        <CardTitle>Analysis inputs</CardTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 mt-1">
          {info.map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-dashed border-border py-1.5 text-sm">
              <span className="text-muted">{k}</span><span className="font-semibold">{v}</span>
            </div>
          ))}
        </div>
        {proj.warnings?.length ? (
          <div className="mt-3 text-[13px] text-warn">⚠ {proj.warnings.join(" · ")}</div>
        ) : null}
      </Card>

      {/* selected guide */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1.4fr_1.2fr] gap-4">
        <Card>
          <div className="font-display font-extrabold text-xl text-brand">{g.guide_id}</div>
          <div className="label mt-2">Sequence (5'→3')</div>
          <code className="text-sm bg-bg rounded px-1 text-ink break-all">{g.sequence}</code>
          <div className="flex gap-4 mt-3 flex-wrap">
            {[["PAM", g.pam], ["Strand", strandOf(g)], ["Pos", g.position], ["GC", `${(g.gc_content * 100).toFixed(0)}%`], ["QGuide", g.ensemble?.final_qguide_score?.toFixed(3) ?? "—"]].map(([k, v]) => (
              <div key={k as string}><div className="label">{k}</div><b className={k === "QGuide" ? "text-brand" : ""}>{v}</b></div>
            ))}
          </div>
          <div className="mt-3"><EnsembleBadges e={g.ensemble} /></div>
        </Card>
        <Card>
          <CardTitle>Score breakdown</CardTitle>
          <BarRow label="On-target" value={g.scores.on_target} />
          <BarRow label="Knockout" value={g.outcome.knockout_prob} />
          <BarRow label="Off-target" value={g.off_target.risk_score} tone={g.off_target.risk_score < 0.2 ? "series" : "warn"} />
          <BarRow label="GC content" value={g.scores.gc_content} tone="series" />
          <BarRow label="Complexity" value={g.scores.complexity} tone="series" />
          <BarRow label="Context" value={Math.min(1, g.context.multiplier)} />
          <BarRow label="Structure pen." value={g.scores.secondary_structure_penalty} tone="warn" />
        </Card>
        <Card>
          <CardTitle>Why this guide?</CardTitle>
          {whyChosen(g).map(([t, ok]) => (
            <div key={t} className="flex items-center gap-2 my-1 text-sm font-medium">
              <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] font-extrabold ${ok ? "bg-brand/15 text-brand" : "bg-bg text-muted"}`}>{ok ? "✓" : "–"}</span>{t}
            </div>
          ))}
        </Card>
      </div>
      <Card><EnsemblePanel e={g.ensemble} /></Card>
    </div>
  );
}
