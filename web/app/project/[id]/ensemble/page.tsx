"use client";
// Ensemble Breakdown (Feature 1) — every scoring variable, model contribution, weight.
import { Card, CardTitle } from "@/components/ui";
import { EnsemblePanel, EnsembleBadges, PrecisionPanel, OffTargetSeverityPanel, BioContextPanel } from "@/components/Ensemble";
import { useProject } from "@/lib/projectCtx";

const COLS: [string, string][] = [
  ["on_target_score", "On-tgt"], ["desired_outcome_score", "Outcome"], ["off_target_score", "Off-safe"],
  ["specificity_score", "Specif."], ["repair_outcome_score", "Repair"], ["genomic_context_score", "Genomic"],
  ["cell_context_score", "Cell"], ["model_agreement_score", "Agree"], ["uncertainty_score", "Uncert."],
  ["final_qguide_score", "QGuide"],
];

export default function EnsembleBreakdown() {
  const { guides, sel, setSel, g } = useProject();
  const e = g.ensemble;
  const weights: [string, number][] = Object.entries(e?.weights || {}) as any;

  return (
    <div className="flex flex-col gap-4">
      <Card className="overflow-x-auto">
        <CardTitle>All guides · every scoring variable</CardTitle>
        <table className="w-full text-sm">
          <thead><tr className="text-muted text-left text-xs uppercase">
            <th className="py-1 pr-3">Guide</th>
            {COLS.map(([, label]) => <th key={label} className="py-1 pr-3 whitespace-nowrap text-right">{label}</th>)}
            <th className="py-1 pr-3 whitespace-nowrap text-right">Precision</th>
            <th className="py-1 pr-3">Conf.</th>
          </tr></thead>
          <tbody>
            {guides.map((x) => {
              const xe = x.ensemble || {};
              const xp = x.precision || {};
              return (
                <tr key={x.guide_id} className={`border-t border-border cursor-pointer ${x.guide_id === sel ? "bg-brand/5" : ""}`}
                  onClick={() => setSel(x.guide_id)}>
                  <td className="py-1.5 pr-3"><span className="text-brand font-bold">{x.guide_id}</span></td>
                  {COLS.map(([field]) => (
                    <td key={field} className={`pr-3 text-right font-mono ${field === "final_qguide_score" ? "font-bold text-brand" : ""}`}>
                      {typeof xe[field] === "number" ? xe[field].toFixed(2) : "—"}
                    </td>
                  ))}
                  <td className="pr-3 text-right font-mono font-bold text-brand">
                    {typeof xp.score === "number" ? xp.score.toFixed(2) : "—"}
                  </td>
                  <td className="pr-3">{xp.confidence_label || xe.confidence_label || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="text-[11px] text-muted mt-2">Click a guide to inspect its full breakdown. Off-safe = 1 − off-target risk. Uncert. lower is better. Precision = the outcome-first QGuide Precision Score.</div>
      </Card>

      {g?.precision?.components?.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4 items-start">
          <Card><PrecisionPanel p={g.precision} /></Card>
          <div className="flex flex-col gap-4">
            <Card><OffTargetSeverityPanel sev={g.off_target?.severity} /></Card>
            <Card><BioContextPanel bc={g.bio_context} /></Card>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4 items-start">
        <Card>
          <div className="flex items-center justify-between mb-2">
            <div className="font-display font-extrabold text-xl text-brand">{g.guide_id}</div>
            <EnsembleBadges e={e} />
          </div>
          <EnsemblePanel e={e} />
        </Card>
        <Card>
          <CardTitle>Applied weights</CardTitle>
          <div className="text-xs text-muted mb-2">Weights depend on goal + risk tolerance. Off-target & uncertainty are penalties.</div>
          {weights.length === 0 ? <div className="text-sm text-muted">—</div> : weights.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 my-1">
              <span className="w-32 text-xs text-muted font-semibold">{k}</span>
              <div className="flex-1 h-2 rounded-full bg-bg overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.abs(v) * 200)}%`, background: k === "off_target" || k === "uncertainty" ? "#c07c1e" : "#4b54c9" }} />
              </div>
              <span className="w-10 text-right text-xs font-bold">{v.toFixed(2)}</span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
