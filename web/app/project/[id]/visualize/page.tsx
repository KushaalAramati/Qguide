"use client";
// Dedicated 3D Visualization Studio — an open dashboard of independently
// openable panels (not a step-by-step flow). Each panel lazy-mounts its heavy
// 3D canvas only when opened, so you can pop open whatever you want to inspect.
import { ReactNode, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Shell } from "@/components/Shell";
import { Metric } from "@/components/ui";
import { DnaOverview } from "@/components/viz/DnaOverview";
import { api } from "@/lib/api";
import { buildDnaWindow, cleanSeq, BASE_NAME } from "@/lib/dna";

const Loading3D = () => <div className="h-[420px] grid place-items-center text-muted bg-[#0e0a16] rounded-xl">Loading 3D viewer…</div>;
const GuideRna3D = dynamic(() => import("@/components/viz/GuideRna3D").then((m) => m.GuideRna3D), { ssr: false, loading: Loading3D });
const DnaHelix3D = dynamic(() => import("@/components/viz/DnaHelix3D").then((m) => m.DnaHelix3D), { ssr: false, loading: Loading3D });
const CrisprSimulation3D = dynamic(() => import("@/components/viz/CrisprSimulation3D").then((m) => m.CrisprSimulation3D), { ssr: false, loading: Loading3D });

export default function VisualizePage() {
  return <Shell><Studio /></Shell>;
}

// A collapsible dashboard panel. Children render (and 3D mounts) only when open.
function Panel({ title, subtitle, icon, wide, open, onToggle, children }: {
  title: string; subtitle?: string; icon: string; wide?: boolean;
  open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <div className={`card !p-0 overflow-hidden self-start ${wide ? "md:col-span-2" : ""}`}>
      <button onClick={onToggle} className="w-full flex items-center justify-between p-3 hover:bg-brand/5 transition">
        <span className="flex items-center gap-2 text-left">
          <span className="text-lg">{icon}</span>
          <span>
            <span className="block font-display font-extrabold text-sm text-brand">{title}</span>
            {subtitle && <span className="block text-xs text-muted">{subtitle}</span>}
          </span>
        </span>
        <span className="text-brand text-xs font-bold whitespace-nowrap ml-2">{open ? "▾ Close" : "▸ Open"}</span>
      </button>
      {open && <div className="p-3 pt-0">{children}</div>}
    </div>
  );
}

function Studio() {
  const { id } = useParams<{ id: string }>();
  const [proj, setProj] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState("");
  const [selBase, setSelBase] = useState<number | null>(null);
  const [hovBase, setHovBase] = useState<number | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ sim: true, map: true });

  useEffect(() => {
    setProj(null); setErr("");
    api.project(id)
      .then((p) => { setProj(p); setSel(p.selected_guide || p.response.guides[0]?.guide_id); })
      .catch((e) => setErr(e.message || "Failed to load project."));
  }, [id]);

  const guides: any[] = proj?.response?.guides ?? [];
  const byId: Record<string, any> = useMemo(() => Object.fromEntries(guides.map((g) => [g.guide_id, g])), [guides]);
  const g = byId[sel] || guides[0];
  const req = proj?.response?.request;
  const fullSeq = req ? cleanSeq(req.sequence) : "";
  const win = useMemo(() => (g ? buildDnaWindow(fullSeq, g) : null), [fullSeq, g]);
  const strand = (x: any) => (typeof x?.strand === "string" ? x.strand : x?.strand?.value || "+");
  const activeBase = selBase ?? hovBase;

  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const setAll = (v: boolean) => setOpen(v ? { sim: true, map: true, guide: true, helix: true, analytics: true } : {});

  if (err) return <div className="text-bad font-semibold">{err}</div>;
  if (!proj || !g || !win) return <div className="text-muted">Loading 3D studio…</div>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-start">
        <div>
          <div className="font-display font-extrabold text-3xl">🧬 3D Visualization Studio</div>
          <div className="text-muted font-medium">{req.cas_enzyme} ({g.pam}) · {req.desired_outcome} · {proj.name}</div>
        </div>
        <Link href={`/project/${id}`} className="btn-ghost text-sm">← Back to result</Link>
      </div>

      {/* control bar: guide picker + open/collapse all */}
      <div className="card flex items-center gap-4 flex-wrap">
        <div>
          <div className="label">Guide to visualize</div>
          <select className="input max-w-xs" value={sel} onChange={(e) => { setSel(e.target.value); setSelBase(null); }}>
            {guides.map((x) => <option key={x.guide_id}>{x.guide_id}</option>)}
          </select>
        </div>
        <div className="flex gap-4 text-sm">
          {[["Sequence (5'→3')", g.sequence], ["PAM", g.pam], ["Strand", strand(g)], ["Pos", `${g.position}`], ["GC", `${(g.gc_content * 100).toFixed(0)}%`]].map(([k, v]) => (
            <div key={k as string}><div className="label">{k}</div><b className={k === "Sequence (5'→3')" ? "font-mono text-brand-dark" : ""}>{v}</b></div>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          <button onClick={() => setAll(true)} className="btn-ghost text-xs">⤢ Open all</button>
          <button onClick={() => setAll(false)} className="btn-ghost text-xs">⤡ Collapse all</button>
        </div>
      </div>

      {/* dashboard grid — open any panel in any order */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <Panel icon="🧭" title="Sequence map" subtitle="All PAM sites · click a marker to switch guide" wide
          open={!!open.map} onToggle={() => toggle("map")}>
          <div className="text-xs text-muted mb-1">+ strand above the axis, − strand below.</div>
          <DnaOverview seqLength={fullSeq.length} guides={guides} selectedId={sel}
            onSelect={(gid) => { setSel(gid); setSelBase(null); }} />
        </Panel>

        <Panel icon="▶" title={`CRISPR–Cas9 process simulation · ${g.guide_id}`}
          subtitle="scan → PAM → R-loop → cleavage → break → gRNA replaces cut DNA" wide
          open={!!open.sim} onToggle={() => toggle("sim")}>
          <div className="text-xs text-muted mb-3">
            Play, scrub, or jump to any stage. The final step shows the cut DNA being released and the guide/edit strand sliding into the gap.
          </div>
          <CrisprSimulation3D win={win} guideSeq={g.sequence} guideId={g.guide_id} />
        </Panel>

        <Panel icon="🧬" title={`Guide RNA 3D · ${g.guide_id}`} subtitle="click a base to inspect it"
          open={!!open.guide} onToggle={() => toggle("guide")}>
          <GuideRna3D sequence={g.sequence} selected={selBase} onSelect={setSelBase} onHover={setHovBase} />
          <div className="mt-2 rounded-lg bg-bg border border-border p-2 text-sm">
            {activeBase != null && g.sequence[activeBase] ? (
              <div className="flex items-center gap-4">
                <span className="font-display font-extrabold text-3xl text-brand">{g.sequence[activeBase]}</span>
                <span className="flex gap-4">
                  <span><span className="label block">Base</span><b>{BASE_NAME[g.sequence[activeBase]] || "—"}</b></span>
                  <span><span className="label block">Type</span><b>{["A", "G"].includes(g.sequence[activeBase]) ? "Purine" : "Pyrimidine"}</b></span>
                  <span><span className="label block">In guide</span><b>{activeBase + 1}/{g.sequence.length}</b></span>
                  <span><span className="label block">Genomic idx</span><b>{g.position + activeBase}</b></span>
                </span>
                {selBase != null && <button onClick={() => setSelBase(null)} className="btn-ghost text-xs ml-auto">Clear</button>}
              </div>
            ) : <span className="text-muted">Hover or click a nucleotide above to inspect it.</span>}
          </div>
        </Panel>

        <Panel icon="🌀" title="DNA double helix · binding region" subtitle="protospacer + PAM highlighted"
          open={!!open.helix} onToggle={() => toggle("helix")}>
          <DnaHelix3D win={win} onHover={() => {}} />
        </Panel>

        <Panel icon="📊" title={`Analytics · ${g.guide_id}`} subtitle="scores & coordinates" wide
          open={!!open.analytics} onToggle={() => toggle("analytics")}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Efficiency (on-target)" value={g.scores.on_target.toFixed(3)} color="brand" />
            <Metric label="Specificity" value={(1 - g.off_target.risk_score).toFixed(3)} color="good" />
            <Metric label="Off-target risk" value={`${(g.off_target.risk_score * 100).toFixed(0)}%`} sub={g.off_target.risk_category} color="warn" />
            <Metric label="Knockout prob." value={g.outcome.knockout_prob.toFixed(3)} color="good" />
            <Metric label="GC content" value={`${(g.gc_content * 100).toFixed(0)}%`} />
            <Metric label="2° structure penalty" value={g.scores.secondary_structure_penalty.toFixed(3)} />
            <Metric label="Final score" value={g.final_score.toFixed(3)} color="brand" />
            <Metric label="Coordinates" value={`${g.position}–${g.end ?? g.position + g.sequence.length}`} sub={`${strand(g)} · ${g.pam}`} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
