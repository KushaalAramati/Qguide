"use client";
// Dedicated 3D Visualization Studio — a section of the app focused entirely on the
// spatial/animated views of a design result: the interactive CRISPR–Cas9 process
// simulation plus the guide-RNA and DNA-duplex 3D viewers.
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Shell } from "@/components/Shell";
import { Card, CardTitle } from "@/components/ui";
import { DnaOverview } from "@/components/viz/DnaOverview";
import { api } from "@/lib/api";
import { buildDnaWindow, cleanSeq } from "@/lib/dna";

const Loading3D = () => <div className="h-[420px] grid place-items-center text-muted bg-[#0e0a16] rounded-xl">Loading 3D viewer…</div>;
const GuideRna3D = dynamic(() => import("@/components/viz/GuideRna3D").then((m) => m.GuideRna3D), { ssr: false, loading: Loading3D });
const DnaHelix3D = dynamic(() => import("@/components/viz/DnaHelix3D").then((m) => m.DnaHelix3D), { ssr: false, loading: Loading3D });
const CrisprSimulation3D = dynamic(() => import("@/components/viz/CrisprSimulation3D").then((m) => m.CrisprSimulation3D), { ssr: false, loading: Loading3D });

export default function VisualizePage() {
  return <Shell><Studio /></Shell>;
}

function Studio() {
  const { id } = useParams<{ id: string }>();
  const [proj, setProj] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState("");
  const [selBase, setSelBase] = useState<number | null>(null);
  const [hovBase, setHovBase] = useState<number | null>(null);

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

      {/* guide picker + sequence map */}
      <Card>
        <div className="flex items-center gap-3 flex-wrap mb-2">
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
        </div>
        <div className="text-xs text-muted mb-1">Click a guide marker to visualize it. + strand above the axis, − strand below.</div>
        <DnaOverview seqLength={fullSeq.length} guides={guides} selectedId={sel}
          onSelect={(gid) => { setSel(gid); setSelBase(null); }} />
      </Card>

      {/* CRISPR process simulation — the centerpiece of this section */}
      <Card>
        <div className="flex justify-between items-center mb-1">
          <CardTitle>CRISPR–Cas9 process simulation · {g.guide_id}</CardTitle>
          <code className="text-xs bg-bg rounded px-1 text-brand-dark">{g.sequence} · {g.pam}</code>
        </div>
        <div className="text-xs text-muted mb-3">
          Watch the Cas9–gRNA complex scan the DNA, recognise the PAM, unwind the duplex into an R-loop, and cut — for this specific guide.
          Use Play/scrub, or jump to any stage.
        </div>
        <CrisprSimulation3D win={win} guideSeq={g.sequence} guideId={g.guide_id} />
      </Card>

      {/* static 3D viewers */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <div className="flex justify-between items-center mb-1">
            <CardTitle>Guide RNA 3D · {g.guide_id}</CardTitle>
            <code className="text-xs bg-bg rounded px-1 text-brand-dark">{g.sequence}</code>
          </div>
          <GuideRna3D sequence={g.sequence} selected={selBase} onSelect={setSelBase} onHover={setHovBase} />
          <div className="text-xs text-muted mt-1">Drag to rotate · scroll to zoom · click a base for details.</div>
        </Card>
        <Card>
          <CardTitle>DNA double helix · binding region</CardTitle>
          <DnaHelix3D win={win} onHover={() => {}} />
          <div className="text-xs text-muted mt-1">Highlighted: protospacer (purple rungs) and PAM (gold).</div>
        </Card>
      </div>

      {/* base-level detail for the guide-RNA viewer */}
      <Card>
        <CardTitle>Base-level detail</CardTitle>
        {activeBase != null && g.sequence[activeBase] ? (
          <div className="flex items-center gap-6 text-sm">
            <div className="font-display font-extrabold text-4xl text-brand">{g.sequence[activeBase]}</div>
            <div className="flex gap-6">
              <div><div className="label">Type</div><b>{["A", "G"].includes(g.sequence[activeBase]) ? "Purine" : "Pyrimidine"}</b></div>
              <div><div className="label">Position in guide</div><b>{activeBase + 1} / {g.sequence.length}</b></div>
              <div><div className="label">Genomic index</div><b>{g.position + activeBase}</b></div>
            </div>
            {selBase != null && <button onClick={() => setSelBase(null)} className="btn-ghost text-xs">Clear</button>}
          </div>
        ) : (
          <div className="text-sm text-muted">Hover or click a nucleotide in the Guide RNA 3D viewer to inspect it.</div>
        )}
      </Card>
    </div>
  );
}
