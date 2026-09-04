"use client";
// Research Tools — progressive disclosure: the everyday workflow stays on New
// Analysis; multi-target batches, templates, comparison and history live here.
import { useState } from "react";
import { Shell } from "@/components/Shell";
import { PageHeader, Tabs } from "@/components/PageHeader";
import { Batch } from "@/components/research/Batch";
import { Templates, Template } from "@/components/research/Templates";
import { Compare } from "@/components/research/Compare";
import { History } from "@/components/research/History";

const TABS = ["Batch analysis", "Templates", "Compare", "History"] as const;
type Tab = typeof TABS[number];

export default function ResearchPage() {
  return <Shell><Research /></Shell>;
}

function Research() {
  const [tab, setTab] = useState<Tab>("Batch analysis");
  const [tpl, setTpl] = useState<Template | null>(null);
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="research tools"
        title="Research Tools"
        description="Run several targets with one configuration, save analysis templates, compare projects side by side, and review your experiment history. Notes, tags and references live on each project's Notes tab; reports export from the project page."
      />
      <Tabs<Tab> items={TABS} value={tab} onChange={setTab} />
      {tab === "Batch analysis" && <Batch template={tpl} onTemplateUsed={() => setTpl(null)} />}
      {tab === "Templates" && <Templates onUse={(t) => { setTpl(t); setTab("Batch analysis"); }} />}
      {tab === "Compare" && <Compare />}
      {tab === "History" && <History />}
    </div>
  );
}
