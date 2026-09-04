"use client";
// Persistent project header + sub-navigation (Feature 7). Gates rendering on the
// shared project load so each feature page can assume data is present.
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useState } from "react";
import { useProject } from "@/lib/projectCtx";
import { exportGuidesCsv, exportProjectJson, downloadText, safeName } from "@/lib/exports";
import { ShareDialog } from "@/components/ShareDialog";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const NAV: [string, string][] = [
  ["", "basic"],
  ["/rankings", "rankings"],
  ["/best-set", "best_set"],
  ["/outcome", "outcome"],
  ["/compare", "compare"],
  ["/visualize", "3d"],
  ["/simulation", "simulation"],
  ["/ensemble", "ensemble"],
  ["/notes", "notes"],
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
  const { id, proj, req, opt, err, loading, guides, sel, setSel, g, access, members, reload, setMembers } = useProject();
  const path = usePathname();
  const router = useRouter();
  const { refresh } = useAuth();
  const [exportOpen, setExportOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");

  async function saveSelection() {
    if (!access?.can_edit || !sel) return;
    setBusy("select"); setNote("");
    try { await api.patchProject(id, { selected_guide: sel }); await reload(); setNote(`Saved ${sel} as the selected guide.`); }
    catch (e: any) { setNote(e.message || "Could not save selection."); }
    finally { setBusy(""); }
  }
  async function rename() {
    if (!access?.can_edit) return;
    const name = window.prompt("Rename project:", proj.name);
    if (!name || name.trim() === proj.name) return;
    setBusy("rename"); setNote("");
    try { await api.patchProject(id, { name: name.trim() }); await reload(); }
    catch (e: any) { setNote(e.message || "Could not rename."); }
    finally { setBusy(""); }
  }
  async function rerun() {
    if (!access?.can_run) return;
    if (!window.confirm("Re-run the analysis with the stored inputs? This costs 5 credits and replaces the stored results for everyone on the project.")) return;
    setBusy("rerun"); setNote("");
    try {
      const r = await api.rerunProject(id);
      await reload(); await refresh();
      setNote(`Re-analysed: ${r.n_guides} guides in ${r.elapsed}s.`);
    } catch (e: any) {
      setNote(e.status === 402 ? "Not enough credits to re-run — add credits first." : e.message || "Re-run failed.");
    } finally { setBusy(""); }
  }

  if (err) {
    return (
      <div className="panel max-w-xl">
        <div className="panel-head">project unavailable</div>
        <div className="panel-body text-[12px] text-muted">
          {err}
          <div className="mt-3"><Link href="/projects" className="btn-ghost text-[12px]">‹ Back to projects</Link></div>
        </div>
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
        <Link href="/projects" className="text-[10.5px] text-faint hover:text-brand">‹ projects</Link>
        <div className="flex items-start justify-between gap-4 flex-wrap mt-1">
          <div className="min-w-0">
            <h1 className="text-[20px] leading-tight font-medium text-title tracking-tightest flex items-center flex-wrap gap-x-2.5">
              <span>{proj.name}</span>
              <span className="text-[11.5px] text-faint font-normal">{access?.is_owner ? proj.id : ""}</span>
              {access && !access.is_owner && (
                <span className={access.role === "EDITOR" ? "tag-good" : "tag-warn"} title={`Shared by ${proj.owner_email}`}>
                  {access.role.toLowerCase()} · shared by {members.find((m) => m.role === "OWNER")?.name || proj.owner_email}
                </span>
              )}
              {access?.can_edit && (
                <button onClick={rename} disabled={!!busy} className="text-[11px] text-faint hover:text-brand font-normal" title="Rename project">✎</button>
              )}
            </h1>
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-2 text-[10.5px]">
              <Fact k="nuclease" v={`${req.cas_enzyme}/${g.pam}`} />
              <Fact k="outcome" v={req.desired_outcome} />
              <Fact k="organism" v={req.organism} />
              <Fact k="optimizer" v={opt?.method ?? "—"} />
              <Fact k="guides" v={guides.length} />
              <Fact k="created" v={proj.created} />
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
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
            {access?.can_edit && sel && sel !== proj.selected_guide && (
              <button onClick={saveSelection} disabled={busy === "select"} className="btn-ghost text-[12px]" title="Store this guide as the project's selected guide">
                {busy === "select" ? "Saving…" : "Save selection"}
              </button>
            )}
            {access?.can_run && (
              <button onClick={rerun} disabled={busy === "rerun"} className="btn-ghost text-[12px]" title="Re-run the pipeline with the stored inputs (5 credits)">
                {busy === "rerun" ? "Running…" : "Re-run analysis"}
              </button>
            )}
            <button onClick={() => setShareOpen(true)} className="btn-ghost text-[12px]" title={access?.can_share ? "Invite collaborators and manage access" : "See who has access"}>
              {access?.can_share ? (members.length > 1 ? `Share · ${members.length - 1}` : "Share") : "Access"}
            </button>
            <div className="relative">
              <button onClick={() => setExportOpen((v) => !v)} className="btn-primary text-[12px]" aria-haspopup="menu" aria-expanded={exportOpen}>
                Export results ▾
              </button>
              {exportOpen && (
                <div role="menu" className="absolute right-0 z-20 mt-0.5 w-56 bg-surface border border-border p-1 text-[11.5px]" onMouseLeave={() => setExportOpen(false)}>
                  <button role="menuitem" onClick={() => { exportGuidesCsv(proj, id, guides, opt); setExportOpen(false); }} className="w-full text-left px-2 py-1.5 text-ink hover:bg-brand/[0.08] hover:text-brand">
                    Guide table (CSV)
                    <span className="block text-[10.5px] text-faint">ranked guides with scores and set membership</span>
                  </button>
                  <button role="menuitem" onClick={() => { exportProjectJson(proj, id); setExportOpen(false); }} className="w-full text-left px-2 py-1.5 text-ink hover:bg-brand/[0.08] hover:text-brand">
                    Full project (JSON)
                    <span className="block text-[10.5px] text-faint">inputs, all guides, optimised set, provenance</span>
                  </button>
                  <div className="border-t border-divider my-1" />
                  <button role="menuitem" onClick={async () => { setExportOpen(false); try { downloadText(`${safeName(proj.name)}_${id}_report.md`, await api.projectReportMarkdown(id), "text/markdown"); } catch (e: any) { setNote(e.message); } }} className="w-full text-left px-2 py-1.5 text-ink hover:bg-brand/[0.08] hover:text-brand">
                    Scientific report (Markdown)
                    <span className="block text-[10.5px] text-faint">inputs, selected set, limitations, notes, reproducibility</span>
                  </button>
                  <button role="menuitem" onClick={async () => { setExportOpen(false); try { const r = await api.projectReport(id); downloadText(`${safeName(proj.name)}_${id}_report.json`, JSON.stringify(r, null, 2), "application/json"); } catch (e: any) { setNote(e.message); } }} className="w-full text-left px-2 py-1.5 text-ink hover:bg-brand/[0.08] hover:text-brand">
                    Scientific report (JSON)
                    <span className="block text-[10.5px] text-faint">same report as structured data</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {note && <div className="mt-2 text-[11px] text-muted" role="status">{note}</div>}
        {access && !access.can_edit && (
          <div className="mt-2 text-[10.5px] text-faint">Read-only: you can explore and export this project but not change it.</div>
        )}

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

      {shareOpen && access && (
        <ShareDialog
          projectId={access.uid || id}
          projectName={proj.name}
          access={access}
          members={members}
          onMembers={setMembers}
          onClose={() => setShareOpen(false)}
          onLeft={() => router.replace("/projects")}
        />
      )}
    </div>
  );
}
