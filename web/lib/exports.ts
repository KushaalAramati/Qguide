// Export helpers shared by project pages and (later) research tools.
import { downloadCsv } from "@/lib/csv";
import { BRANDING, SHORT_DISCLAIMER } from "@/lib/branding";

const strandOf = (x: any) => (typeof x?.strand === "string" ? x.strand : x?.strand?.value || "+");

/** Flat, spreadsheet-friendly rows for a project's guide list. */
export function guideRows(guides: any[], opt: any) {
  const chosen: string[] = opt?.selected_guide_ids || [];
  return guides.map((x: any, i: number) => ({
    rank: i + 1,
    guide_id: x.guide_id,
    sequence: x.sequence,
    pam: x.pam,
    strand: strandOf(x),
    position: x.position,
    gc_content: x.gc_content?.toFixed(3),
    on_target: x.scores?.on_target?.toFixed(3),
    knockout_prob: x.outcome?.knockout_prob?.toFixed(3),
    off_target_risk: x.off_target?.risk_score?.toFixed(3),
    final_score: x.final_score?.toFixed(3),
    precision_score: x.ensemble?.final_qguide_score?.toFixed(3) ?? "",
    confidence: x.confidence?.toFixed(3),
    in_optimized_set: chosen.includes(x.guide_id),
  }));
}

export const safeName = (s: string) => (s || "project").replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 60);
const safe = safeName;

export function downloadText(filename: string, text: string, type = "text/plain") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportGuidesCsv(proj: any, id: string, guides: any[], opt: any) {
  downloadCsv(`${safe(proj?.name)}_${id}_guides.csv`, guideRows(guides, opt));
}

/** Full JSON export: inputs, every guide, the optimised set and provenance. */
export function exportProjectJson(proj: any, id: string) {
  const payload = {
    exported_by: BRANDING.APP_NAME,
    exported_at: new Date().toISOString(),
    disclaimer: SHORT_DISCLAIMER,
    project: { id, name: proj?.name, created: proj?.created, elapsed_s: proj?.elapsed,
               selected_guide: proj?.selected_guide },
    request: proj?.response?.request,
    optimized_set: proj?.response?.optimized_set,
    guides: proj?.response?.guides,
    assumptions: proj?.response?.assumptions ?? proj?.response?.warnings ?? undefined,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `${safe(proj?.name)}_${id}.json`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
