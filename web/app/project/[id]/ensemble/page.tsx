"use client";
// Ensemble Breakdown page (Feature 1): every scoring variable, model contribution,
// weight, agreement, uncertainty and final score — per guide, in one place.
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Card, CardTitle } from "@/components/ui";
import { EnsemblePanel, EnsembleBadges } from "@/components/Ensemble";
import { api } from "@/lib/api";

const COLS: [string, string][] = [
  ["on_target_score", "On-tgt"],
  ["desired_outcome_score", "Outcome"],
  ["off_target_score", "Off-tgt safe"],
  ["specificity_score", "Specif."],
  ["repair_outcome_score", "Repair"],
  ["genomic_context_score", "Genomic"],
  ["cell_context_score", "Cell"],
  ["model_agreement_score", "Agree"],
  ["uncertainty_score", "Uncert."],
  ["final_qguide_score", "QGuide"],
];

export default function EnsemblePage() {
  return <Shell><Breakdown /></Shell>;
}

function Breakdown() {
  const { id } = useParams<{ id: string }>();
  const [proj, setProj] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState("");

  useEffect(() => {
    setProj(null); setErr("");
    api.project(id)
      .then((p) => { setProj(p); setSel(p.selected_guide || p.response.guides[0]?.guide_id); })
      .catch((e) => setErr(e.message || "Failed to load project."));
  }, [id]);

  const guides: any[] = proj?.response?.guides ?? [];
  const byId: Record<string, any> = useMemo(() => Object.fromEntries(guides.map((g) => [g.guide_id, g])), [guides]);
  const g = byId[sel] || guides[0];

  if (err) return <div className="text-bad font-semibold">{err}</div>;
  if (!proj || !g) return <div className="text-muted">Loading ensemble breakdown…</div>;

  const e = g.ensemble;
  const weights: [string, number][] = Object.entries(e?.weights || {}) as any;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-start">
        <div>
          <div className="font-display font-extrabold text-3xl">Ensemble Breakdown</div>
          <div className="text-muted font-medium">{proj.name} · goal profile <b>{e?.goal_profile}</b></div>
        </div>
        <Link href={`/project/${id}`} className="btn-ghost text-sm">← Back to result</Link>
      </div>

      {/* cross-guide matrix of every component score */}
      <Card className="overflow-x-auto">
        <CardTitle>All guides · every scoring variable</CardTitle>
        <table className="w-full text-sm">
          <thead><tr className="text-muted text-left text-xs uppercase">
            <th className="py-1 pr-3">Guide</th>
            {COLS.map(([, label]) => <th key={label} className="py-1 pr-3 whitespace-nowrap text-right">{label}</th>)}
            <th className="py-1 pr-3">Conf.</th>
          </tr></thead>
          <tbody>
            {guides.map((x) => {
              const xe = x.ensemble || {};
              const on = x.guide_id === sel;
              return (
                <tr key={x.guide_id} className={`border-t border-border cursor-pointer ${on ? "bg-brand/5" : ""}`}
                  onClick={() => setSel(x.guide_id)}>
                  <td className="py-1.5 pr-3"><button className="text-brand font-extrabold">{x.guide_id}</button></td>
                  {COLS.map(([field]) => (
                    <td key={field} className={`pr-3 text-right font-mono ${field === "final_qguide_score" ? "font-bold text-brand" : ""}`}>
                      {typeof xe[field] === "number" ? xe[field].toFixed(2) : "—"}
                    </td>
                  ))}
                  <td className="pr-3">{xe.confidence_label || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="text-[11px] text-muted mt-2">Click a guide to inspect its full breakdown below. Off-tgt safe = 1 − off-target risk. Uncert. lower is better.</div>
      </Card>

      {/* selected guide: full breakdown + models + rationale + limitations */}
      <div className="grid grid-cols-[1.4fr_1fr] gap-4 items-start">
        <Card>
          <div className="flex items-center justify-between mb-2">
            <div className="font-display font-extrabold text-xl text-brand">{g.guide_id}</div>
            <EnsembleBadges e={e} />
          </div>
          <EnsemblePanel e={e} />
        </Card>

        <Card>
          <CardTitle>Applied weights</CardTitle>
          <div className="text-xs text-muted mb-2">Weights depend on goal + risk tolerance. Positive components are rewarded; off-target & uncertainty are penalties.</div>
          {weights.length === 0 ? <div className="text-sm text-muted">—</div> : weights.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 my-1">
              <span className="w-32 text-xs text-muted font-semibold">{k}</span>
              <div className="flex-1 h-2 rounded-full bg-bg overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.abs(v) * 200)}%`, background: k === "off_target" || k === "uncertainty" ? "#C9892F" : "#7A33A6" }} />
              </div>
              <span className="w-10 text-right text-xs font-bold">{v.toFixed(2)}</span>
            </div>
          ))}
          <div className="mt-3 text-[11px] text-muted">
            Guide selector:
            <select className="input mt-1" value={sel} onChange={(ev) => setSel(ev.target.value)}>
              {guides.map((x) => <option key={x.guide_id}>{x.guide_id}</option>)}
            </select>
          </div>
        </Card>
      </div>

      <div className="text-[11px] text-muted">
        Computational predictions — heuristic / provisional components are flagged above and require experimental validation.
      </div>
    </div>
  );
}
