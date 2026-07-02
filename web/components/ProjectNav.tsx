"use client";
// Persistent project header + sub-navigation (Feature 7). Gates rendering on the
// shared project load so each feature page can assume data is present.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { useProject } from "@/lib/projectCtx";

const NAV: [string, string][] = [
  ["", "Basic Results"],
  ["/rankings", "Guide Rankings"],
  ["/best-set", "Best Guide Set"],
  ["/outcome", "Outcome"],
  ["/compare", "Compare"],
  ["/visualize", "3D Visualizer"],
  ["/simulation", "Simulation"],
  ["/ensemble", "Ensemble"],
];

export function ProjectFrame({ children }: { children: ReactNode }) {
  const { id, proj, req, opt, err, loading, guides, sel, setSel, g } = useProject();
  const path = usePathname();
  if (err) return <div className="text-bad font-semibold">{err}</div>;
  if (loading || !g) return <div className="text-muted">Loading project…</div>;
  const base = `/project/${id}`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-start gap-3 flex-wrap">
        <div>
          <div className="font-display font-extrabold text-2xl">{proj.name}</div>
          <div className="text-muted text-sm">{req.cas_enzyme} ({g.pam}) · {req.desired_outcome} · {req.organism} · {opt?.method}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="label">Guide</span>
          <select className="input !w-auto py-1.5" value={sel} onChange={(e) => setSel(e.target.value)}>
            {guides.map((x: any) => <option key={x.guide_id}>{x.guide_id}</option>)}
          </select>
        </div>
      </div>

      <div className="flex gap-1 border-b border-border overflow-x-auto">
        {NAV.map(([slug, label]) => {
          const href = base + slug;
          const active = path === href;
          return (
            <Link key={label} href={href}
              className={`px-3 py-2 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition
                ${active ? "text-brand border-brand" : "text-muted border-transparent hover:text-ink"}`}>
              {label}
            </Link>
          );
        })}
      </div>

      <div>{children}</div>
    </div>
  );
}
