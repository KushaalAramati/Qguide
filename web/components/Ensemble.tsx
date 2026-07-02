"use client";
import { BarRow, CardTitle, Pill } from "./ui";

const PURPLE = "#7A33A6", BLUE = "#9B59B6", AMBER = "#C9892F";

const TASK_LABEL: Record<string, string> = {
  on_target: "On-target activity", specificity: "Specificity", repair: "Repair outcome",
};

function KindBadge({ kind, available }: { kind: string; available: boolean }) {
  if (!available)
    return <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-bg text-muted" title="Model not installed — abstains (no score)">provisional · abstains</span>;
  const map: Record<string, string> = {
    real: "bg-brand/10 text-brand", heuristic: "bg-warn/15 text-[#9A6818]",
  };
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${map[kind] || "bg-bg text-muted"}`}>{kind}</span>;
}

function ModelBreakdown({ e }: { e: any }) {
  const rows: any[] = Array.isArray(e.model_scores) ? e.model_scores : [];
  if (!rows.length) return null;
  return (
    <div className="mt-3 border-t border-border pt-2">
      <div className="label mb-1">Contributing models</div>
      {["on_target", "specificity", "repair"].map((task) => {
        const group = rows.filter((m) => m.task === task);
        if (!group.length) return null;
        return (
          <div key={task} className="mb-2">
            <div className="text-[11px] font-bold text-muted uppercase tracking-wide">{TASK_LABEL[task] || task}</div>
            {group.map((m, i) => (
              <div key={i} className="flex items-center gap-2 text-sm py-0.5">
                <span className="flex-1 truncate" title={m.note}>{m.name}</span>
                <KindBadge kind={m.kind} available={m.available} />
                <span className="w-12 text-right font-mono">{m.available && m.score != null ? Number(m.score).toFixed(2) : "\u2014"}</span>
              </div>
            ))}
          </div>
        );
      })}
      <div className="text-[10px] text-muted">Biological scores come from classical bioinformatics / ML models above; unavailable ML models abstain (—) rather than guess.</div>
    </div>
  );
}

const COMPONENT_LABELS: [string, string, string][] = [
  // [ensemble field, label, color]
  ["on_target_score", "On-target", PURPLE],
  ["desired_outcome_score", "Desired outcome", PURPLE],
  ["off_target_score", "Off-target safety", PURPLE],
  ["specificity_score", "Specificity", BLUE],
  ["repair_outcome_score", "Repair outcome", BLUE],
  ["genomic_context_score", "Genomic context", BLUE],
  ["cell_context_score", "Cell context", BLUE],
  ["model_agreement_score", "Model agreement", AMBER],
];

export function EnsembleBadges({ e }: { e: any }) {
  if (!e) return null;
  const kind = (b: string) =>
    /high off-target|low confidence/i.test(b) ? "bad"
      : /medium/i.test(b) ? "warn" : "good";
  return (
    <div className="flex flex-wrap gap-1.5">
      {(e.badges || []).map((b: string, i: number) => (
        <Pill key={i} value={b} kind={kind(b) as any} />
      ))}
    </div>
  );
}

export function EnsemblePanel({ e }: { e: any }) {
  if (!e) return null;
  const prov = new Set(e.provisional || []);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <CardTitle>Ensemble breakdown</CardTitle>
        <span className="text-sm font-extrabold text-brand">
          QGuide score {e.final_qguide_score?.toFixed(3)}
        </span>
      </div>
      <div className="text-xs text-muted mb-2">Goal profile: <b>{e.goal_profile}</b> · confidence{" "}
        <b>{e.confidence_label}</b></div>
      {COMPONENT_LABELS.map(([field, label, color]) => (
        <div key={field} className="flex items-center gap-1">
          <div className="flex-1">
            <BarRow label={label} value={e[field] ?? 0} color={color} />
          </div>
          {prov.has(field) && <span className="text-[10px] text-warn font-bold" title="Provisional / placeholder component">prov</span>}
        </div>
      ))}
      <BarRow label="Uncertainty" value={e.uncertainty_score ?? 0} color={AMBER} />
      {e.rationale && (
        <div className="text-[12px] text-ink bg-bg rounded-lg p-2 mt-2">{e.rationale}</div>
      )}
      <ModelBreakdown e={e} />
      {Array.isArray(e.limitations) && e.limitations.length > 0 && (
        <div className="text-[11px] text-muted mt-2">
          <b>Limitations</b>
          <ul className="list-disc ml-4 mt-0.5">
            {e.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}
          </ul>
        </div>
      )}
      {prov.size > 0 && (
        <div className="text-[11px] text-muted mt-2">⚠ <b>prov</b> = provisional placeholder
          component (heuristic pending a real trained/genome-backed model).</div>
      )}
    </div>
  );
}

export function OffTargetHits({ report }: { report: any }) {
  if (!report) return null;
  const hits = report.hits || [];
  const sevKind = (s: string) => (s === "high" ? "bad" : s === "moderate" ? "warn" : "good");
  return (
    <div>
      <div className="flex items-center justify-between">
        <CardTitle>Predicted off-target sites</CardTitle>
        <span className="text-xs text-muted">burden {report.aggregate_burden?.toFixed(2)}</span>
      </div>
      {report.warning && (
        <div className="text-[11px] rounded-lg bg-amber-50 border border-warn/30 text-[#8a5a12] p-2 my-2">
          ⚠ {report.warning}
        </div>
      )}
      {hits.length === 0 ? (
        <div className="text-sm text-muted">No concerning off-target sites predicted.</div>
      ) : (
        <table className="w-full text-sm mt-1">
          <thead><tr className="text-muted text-left text-xs uppercase">
            {["Locus", "MM", "Positions", "PAM", "CFD*", "Annotation", "Severity"].map((h) => (
              <th key={h} className="py-1 pr-3 whitespace-nowrap">{h}</th>))}
          </tr></thead>
          <tbody>
            {hits.map((h: any, i: number) => (
              <tr key={i} className="border-t border-border">
                <td className="py-1.5 pr-3">{h.locus}</td>
                <td className="pr-3">{h.mismatches}</td>
                <td className="pr-3">{(h.mismatch_positions || []).join(", ") || "—"}</td>
                <td className="pr-3">{h.pam}</td>
                <td className="pr-3">{h.cfd_score?.toFixed(2)}</td>
                <td className="pr-3">{h.annotation}</td>
                <td className="pr-3"><Pill value={h.severity} kind={sevKind(h.severity) as any} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="text-[11px] text-muted mt-2">*CFD-style score is a heuristic placeholder;
        sites are provisional until genome-backed alignment is enabled.</div>
    </div>
  );
}

export function OptimizerComparison({ opt }: { opt: any }) {
  if (!opt) return null;
  const sign = (n: number) => (n >= 0 ? "+" : "") + n.toFixed(3);
  return (
    <div>
      <CardTitle>Optimized set vs. naive Top-N</CardTitle>
      <div className="text-xs text-muted mb-2">Optimizer: <b>{opt.mode}</b> ({opt.method})</div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="card !p-3">
          <div className="label">Top-N by individual score</div>
          <div className="font-bold">{(opt.top_n_individual || []).join(", ") || "—"}</div>
        </div>
        <div className="card !p-3">
          <div className="label">Optimized set</div>
          <div className="font-bold text-brand">{(opt.selected_guide_ids || []).join(", ")}</div>
        </div>
      </div>
      <div className="flex gap-4 mt-2 text-sm">
        <div>Δ mean score <b>{sign(opt.expected_outcome_delta ?? 0)}</b></div>
        <div>Δ mean off-target <b>{sign(opt.off_target_delta ?? 0)}</b></div>
      </div>
      <div className="text-sm text-muted mt-2">{opt.comparison_note}</div>
    </div>
  );
}
