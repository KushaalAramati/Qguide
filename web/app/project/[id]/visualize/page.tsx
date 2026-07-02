"use client";
// 3D Visualizer (Feature 7/8) — open dashboard of independently collapsible panels.
import { ReactNode, useState } from "react";
import dynamic from "next/dynamic";
import { Metric } from "@/components/ui";
import { DnaOverview } from "@/components/viz/DnaOverview";
import { useProject } from "@/lib/projectCtx";
import { buildDnaWindow, BASE_NAME } from "@/lib/dna";

const Loading3D = () => <div className="h-[420px] grid place-items-center text-muted bg-[#0e0a16] rounded-xl">Loading 3D viewer…</div>;
const GuideRna3D = dynamic(() => import("@/components/viz/GuideRna3D").then((m) => m.GuideRna3D), { ssr: false, loading: Loading3D });
const DnaHelix3D = dynamic(() => import("@/components/viz/DnaHelix3D").then((m) => m.DnaHelix3D), { ssr: false, loading: Loading3D });
const CrisprSimulation3D = dynamic(() => import("@/components/viz/CrisprSimulation3D").then((m) => m.CrisprSimulation3D), { ssr: false, loading: Loading3D });

function Panel({ title, subtitle, icon, wide, open, onToggle, children }: {
  title: string; subtitle?: string; icon: string; wide?: boolean;
  open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <div className={`card !p-0 overflow-hidden self-start ${wide ? "md:col-span-2" : ""}`}>
      <button onClick={onToggle} className="w-full flex items-center justify-between p-3 hover:bg-bg transition">
        <span className="flex items-center gap-2 text-left">
          <span className="text-base">{icon}</span>
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

export default function Visualize() {
  const { guides, fullSeq, sel, setSel, g } = useProject();
  const [selBase, setSelBase] = useState<number | null>(null);
  const [hovBase, setHovBase] = useState<number | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ sim: true, map: true });
  const win = buildDnaWindow(fullSeq, g);
  const activeBase = selBase ?? hovBase;
  const toggle = (k: string) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const setAll = (v: boolean) => setOpen(v ? { sim: true, map: true, guide: true, helix: true, analytics: true } : {});

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end gap-2">
        <button onClick={() => setAll(true)} className="btn-ghost text-xs">Open all</button>
        <button onClick={() => setAll(false)} className="btn-ghost text-xs">Collapse all</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <Panel icon="⊹" title="Sequence map" subtitle="click a marker to switch guide" wide
          open={!!open.map} onToggle={() => toggle("map")}>
          <DnaOverview seqLength={fullSeq.length} guides={guides} selectedId={sel}
            onSelect={(gid) => { setSel(gid); setSelBase(null); }} />
        </Panel>

        <Panel icon="▶" title={`CRISPR–Cas9 simulation · ${g.guide_id}`}
          subtitle="scan → PAM → R-loop → cleavage → break → gRNA replaces cut DNA" wide
          open={!!open.sim} onToggle={() => toggle("sim")}>
          <CrisprSimulation3D win={win} guideSeq={g.sequence} guideId={g.guide_id} />
        </Panel>

        <Panel icon="⬡" title={`Guide RNA 3D · ${g.guide_id}`} subtitle="click a base to inspect"
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
                </span>
              </div>
            ) : <span className="text-muted">Hover or click a nucleotide above to inspect it.</span>}
          </div>
        </Panel>

        <Panel icon="◉" title="DNA double helix · binding region" subtitle="protospacer + PAM"
          open={!!open.helix} onToggle={() => toggle("helix")}>
          <DnaHelix3D win={win} onHover={() => {}} />
        </Panel>

        <Panel icon="▦" title={`Analytics · ${g.guide_id}`} subtitle="scores & coordinates" wide
          open={!!open.analytics} onToggle={() => toggle("analytics")}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Efficiency" value={g.scores.on_target.toFixed(3)} color="brand" />
            <Metric label="Specificity" value={(1 - g.off_target.risk_score).toFixed(3)} color="good" />
            <Metric label="Off-target risk" value={`${(g.off_target.risk_score * 100).toFixed(0)}%`} sub={g.off_target.risk_category} color="warn" />
            <Metric label="GC content" value={`${(g.gc_content * 100).toFixed(0)}%`} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
