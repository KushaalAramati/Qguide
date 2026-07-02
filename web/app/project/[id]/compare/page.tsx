"use client";
import { Card, CardTitle } from "@/components/ui";
import { CompareBars, GuideRadar } from "@/components/Charts";
import { useProject } from "@/lib/projectCtx";

export default function Compare() {
  const { guides, g } = useProject();
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card><CardTitle>Top guides compared</CardTitle><CompareBars guides={guides.slice(0, 6)} /></Card>
      <Card><CardTitle>Profile — {g.guide_id}</CardTitle><GuideRadar guide={g} /></Card>
    </div>
  );
}
