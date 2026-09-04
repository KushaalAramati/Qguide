"use client";
import { useMemo, useState } from "react";
import { Pill, scoreKind, riskKind } from "@/components/ui";
import { useProject } from "@/lib/projectCtx";

const strandOf = (x: any) => (typeof x?.strand === "string" ? x.strand : x?.strand?.value || "+");
type SortKey = "rank" | "on" | "ko" | "off" | "final";

/** Inline bar — quantity at a glance without leaving the row. */
function MiniBar({ v }: { v: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block w-10 h-[5px] bg-track2 align-middle overflow-hidden">
        <span className="block h-full bg-series" style={{ width: `${Math.max(0, Math.min(100, v * 100))}%` }} />
      </span>
      <span className="tabular-nums">{v.toFixed(2)}</span>
    </span>
  );
}

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
    ["#", "rank"], ["id", null], ["protospacer·pam", null], ["str", null], ["pos", null],
    ["gc", null], ["on_tgt", "on"], ["ko", "ko"], ["off", "off"], ["q_guide", "final"],
  ];

  return (
    <div className="panel">
      <div className="panel-head">
        <span>ranked guides</span>
        <span className="meta flex items-center gap-3">
          <span>
            {rows.length} of {guides.length} rows · order by{" "}
            <span className="text-muted">{sort === "rank" ? "q_guide" : sort}</span> desc
          </span>
        </span>
      </div>

      <div className="px-3 py-2 border-b border-divider flex items-center gap-2">
        <span className="text-brand text-[11px]">/</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="filter guides"
          aria-label="Filter guides"
          className="flex-1 bg-transparent border-0 outline-none text-[11.5px] text-ink placeholder:text-faint"
        />
        <span className="text-[10px] text-faint">click a header to sort</span>
      </div>

      <div className="overflow-x-auto">
        <table className="dtable">
          <thead>
            <tr>
              {H.map(([h, k]) => (
                <th
                  key={h}
                  onClick={() => k && setSort(k)}
                  className={`whitespace-nowrap ${k ? "cursor-pointer hover:text-ink" : ""}`}
                >
                  {h}{sort === k ? " ▾" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ g, rank }) => {
              const on = g.guide_id === sel;
              return (
                <tr
                  key={g.guide_id}
                  className={`cursor-pointer ${on ? "is-selected" : "hover:bg-brand/5"}`}
                  onClick={() => setSel(g.guide_id)}
                >
                  <td className="tabular-nums">{String(rank).padStart(2, "0")}</td>
                  <td className={on ? "" : "text-ink"}>{g.guide_id}</td>
                  <td className="seqtext whitespace-nowrap">
                    {g.sequence}<span className="text-warn">{g.pam}</span>
                  </td>
                  <td>{strandOf(g)}</td>
                  <td className="tabular-nums">{g.position}</td>
                  <td className="tabular-nums">{(g.gc_content * 100).toFixed(0)}</td>
                  <td><MiniBar v={g.scores.on_target} /></td>
                  <td className="tabular-nums">{g.outcome.knockout_prob.toFixed(2)}</td>
                  <td><Pill value={g.off_target.risk_score.toFixed(2)} kind={riskKind(g.off_target.risk_score)} /></td>
                  <td className={`tabular-nums ${scoreKind(g.final_score) === "good" ? "text-brand" : ""}`}>
                    {g.final_score.toFixed(3)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="caveat">
        off_target is a motif scan with no genome alignment, and repair/context terms are untrained
        priors — treat this ordering as a ranking aid, not a validated prediction.
      </div>
    </div>
  );
}
