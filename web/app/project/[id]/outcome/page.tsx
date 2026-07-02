"use client";
import { Card, CardTitle } from "@/components/ui";
import { OutcomePie, OutcomeBars } from "@/components/Charts";
import { OffTargetHits } from "@/components/Ensemble";
import { useProject } from "@/lib/projectCtx";

export default function Outcome() {
  const { g } = useProject();
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card><CardTitle>Predicted edit outcome — {g.guide_id}</CardTitle><OutcomePie outcome={g.outcome} /></Card>
      <Card><CardTitle>Outcome probabilities</CardTitle><OutcomeBars outcome={g.outcome} /></Card>
      <Card className="md:col-span-2"><OffTargetHits report={g.off_target} /></Card>
      <Card className="md:col-span-2">
        <CardTitle>Why {g.guide_id} ranks here</CardTitle>
        <div className="text-sm">{g.explanation}</div>
        <div className="text-[11px] text-muted mt-2">Predicted / model-based — requires experimental validation.</div>
      </Card>
    </div>
  );
}
