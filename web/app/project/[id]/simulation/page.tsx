"use client";
import dynamic from "next/dynamic";
import { Card, CardTitle } from "@/components/ui";
import { useProject } from "@/lib/projectCtx";
import { buildDnaWindow } from "@/lib/dna";

const Loading3D = () => <div className="h-[460px] grid place-items-center text-muted bg-[#0e0a16] rounded-xl">Loading simulation…</div>;
const CrisprSimulation3D = dynamic(() => import("@/components/viz/CrisprSimulation3D").then((m) => m.CrisprSimulation3D), { ssr: false, loading: Loading3D });

export default function Simulation() {
  const { g, fullSeq } = useProject();
  const win = buildDnaWindow(fullSeq, g);
  return (
    <Card>
      <CardTitle>CRISPR–Cas9 process simulation · {g.guide_id}</CardTitle>
      <div className="text-xs text-muted mb-3">
        Animated, illustrative model of the editing mechanism for this guide: scan → PAM → R-loop →
        cleavage → double-strand break → gRNA replaces the cut DNA. Educational visualization, not a physical simulation.
      </div>
      <CrisprSimulation3D win={win} guideSeq={g.sequence} guideId={g.guide_id} />
    </Card>
  );
}
