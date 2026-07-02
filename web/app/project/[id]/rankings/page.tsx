"use client";
import { useMemo, useState } from "react";
import { Card, Pill, scoreKind, riskKind } from "@/components/ui";
import { useProject } from "@/lib/projectCtx";

const strandOf = (x: any) => (typeof x?.strand === "string" ? x.strand : x?.strand?.value || "+");
type SortKey = "rank" | "on" | "ko" | "off" | "final";

export default function Rankings() {
  const { guides, sel, setSel } = useProject();
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("rank");

  const rows = useMemo(() => {
    let r = guides.map((g, i) => ({ g, rank: i + 1 }));
    if (q) r = r.filter(({ g }) => `${g.guide_id} ${g.sequence}`.toLowerCase().includes(q.toLowerCase()));
    const key: Record<SortKey, (x: any) => number> = {
      rank: (x) => x.rank, on: (x) => -x.g.scores.on_target, ko: (x) => -x.g.outcome.knockout_prob,
      off: (x) => x.g.off_target.risk_score, final: (x) => -x.g.final_score,
    };
    return [...r].sort((a, b) => key[sort](a) - key[sort](b));
  }, [guides, q, sort]);

  const H: [string, SortKey | null][] = [
    ["Rank", "rank"], ["Guide", null], ["Sequence", null], ["PAM", null], ["Pos", null], ["Strand", null],
    ["GC", null], ["On-target", "on"], ["KO", "ko"], ["Off-target", "off"], ["Total", "final"],
  ];

  return (
    <Card className="overflow-x-auto">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search guides…"
          className="input max-w-xs" />
        <span className="text-xs text-muted">{rows.length} of {guides.length} guides · click a header to sort</span>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-muted text-left text-xs uppercase">
          {H.map(([h, k]) => (
            <th key={h} className={`py-1 pr-3 whitespace-nowrap ${k ? "cursor-pointer hover:text-ink" : ""}`}
              onClick={() => k && setSort(k)}>{h}{sort === k ? " ↓" : ""}</th>
          ))}
        </tr></thead>
        <tbody>
          {rows.map(({ g, rank }) => (
            <tr key={g.guide_id} className={`border-t border-border cursor-pointer ${g.guide_id === sel ? "bg-brand/5" : ""}`}
              onClick={() => setSel(g.guide_id)}>
              <td className="py-1.5 pr-3">{rank === 1 ? "★ " : ""}{rank}</td>
              <td className="pr-3"><span className="text-brand font-bold">{g.guide_id}</span></td>
              <td className="pr-3"><code className="text-xs bg-bg rounded px-1">{g.sequence}</code></td>
              <td className="pr-3">{g.pam}</td><td className="pr-3">{g.position}</td><td className="pr-3">{strandOf(g)}</td>
              <td className="pr-3">{(g.gc_content * 100).toFixed(0)}%</td>
              <td className="pr-3"><Pill value={g.scores.on_target.toFixed(2)} kind={scoreKind(g.scores.on_target)} /></td>
              <td className="pr-3"><Pill value={g.outcome.knockout_prob.toFixed(2)} kind={scoreKind(g.outcome.knockout_prob)} /></td>
              <td className="pr-3"><Pill value={g.off_target.risk_score.toFixed(2)} kind={riskKind(g.off_target.risk_score)} /></td>
              <td className="pr-3 font-extrabold text-brand">{g.final_score.toFixed(3)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
