"use client";
import { Card, CardTitle } from "@/components/ui";
import { CompareBars } from "@/components/Charts";
import { OptimizerComparison } from "@/components/Ensemble";
import { useProject } from "@/lib/projectCtx";

export default function BestSet() {
  const { opt, byId } = useProject();
  const chosen = opt.selected_guide_ids.map((gid: string) => byId[gid]).filter(Boolean);
  return (
    <div className="flex flex-col gap-4">
      <Card><OptimizerComparison opt={opt} /></Card>
      <Card>
        <CardTitle>Optimized set: {opt.selected_guide_ids.join(", ")}</CardTitle>
        {opt.tradeoffs?.map((t: string, i: number) => <div key={i} className="text-sm text-muted">• {t}</div>)}
        <div className="mt-3"><CompareBars guides={chosen} /></div>
      </Card>
    </div>
  );
}
