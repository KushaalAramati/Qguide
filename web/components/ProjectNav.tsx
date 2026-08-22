"use client";
// Persistent project header + sub-navigation (Feature 7). Gates rendering on the
// shared project load so each feature page can assume data is present.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { useProject } from "@/lib/projectCtx";

const NAV: [string, string][] = [
  ["", "basic"],
  ["/rankings", "rankings"],
  ["/best-set", "best_set"],
  ["/outcome", "outcome"],
  ["/compare", "compare"],
  ["/visualize", "3d"],
  ["/simulation", "simulation"],
  ["/ensemble", "ensemble"],
];

/** key/value fact used in the header strip — label above, value below. */
function Fact({ k, v }: { k: string; v: ReactNode }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-faint">{k}</span> <span className="text-muted">{v}</span>
    </span>
  );
}

export function ProjectFrame({ children }: { children: ReactNode }) {
  const { id, proj, req, opt, err, loading, guides, sel, setSel, g } = useProject();
  const path = usePathname();

  if (err) {
    return (
      <div className="panel">
        <div className="panel-head">error</div>
        <div className="caveat border-t-0 text-bad bg-bad/[0.06]">{err}</div>
      </div>
    );
  }
  if (loading || !g) {
    return <div className="text-faint text-[11.5px] tracking-[0.12em] uppercase">loading project&hellip;</div>;
  }
  const base = `/project/${id}`;

  return (
    <div className="flex flex-col gap-3">
      {/* ---- header ---- */}
      <div className="border-b border-border pb-0">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-[16px] font-medium text-title tracking-tightest">
              {proj.name}
              <span className="ml-2.5 text-[11.5px] text-faint font-normal">{id}</span>
            </h1>
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-2 text-[10.5px]">
              <Fact k="nuclease" v={`${req.cas_enzyme}/${g.pam}`} />
              <Fact k="outcome" v={req.desired_outcome} />
              <Fact k="organism" v={req.organism} />
              <Fact k="optimizer" v={opt?.method ?? "—"} />
              <Fact k="guides" v={guides.length} />
            </div>
          </div>

          <label className="flex items-center gap-2 text-[10.5px]">
            <span className="text-faint">guide</span>
            <select
              className="border border-border bg-well px-2 py-1 text-[11.5px] text-ink outline-none focus:border-brand"
              value={sel}
              onChange={(e) => setSel(e.target.value)}
            >
              {guides.map((x: any) => <option key={x.guide_id}>{x.guide_id}</option>)}
            </select>
          </label>
        </div>

        {/* ---- view tabs ---- */}
        <div className="flex mt-3 -mb-px overflow-x-auto">
          {NAV.map(([slug, label]) => {
            const href = base + slug;
            const active = path === href;
            return (
              <Link
                key={label}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`px-2.5 py-1.5 text-[11px] whitespace-nowrap border-b transition-colors ${
                  active
                    ? "text-brand border-brand bg-brand/[0.05]"
                    : "text-faint border-transparent hover:text-ink"
                }`}
              >
                <span className="opacity-45">[</span>
                {label}
                <span className="opacity-45">]</span>
              </Link>
            );
          })}
        </div>
      </div>

      <div>{children}</div>
    </div>
  );
}
