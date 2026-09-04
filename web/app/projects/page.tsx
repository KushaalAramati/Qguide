"use client";
// Projects — every project the user can reach, organised by folder. The folder
// tree that used to live in the shell sidebar lives here now, with room to
// breathe; project pages link back with "‹ projects".
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Panel } from "@/components/ui";
import { PageHeader, EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api, ProjectMeta, projectHref } from "@/lib/api";

export default function ProjectsPage() {
  return <Shell><ProjectsView /></Shell>;
}

type Folder = { id: string; name: string; parent_id: string | null };

function ProjectsView() {
  const [projects, setProjects] = useState<ProjectMeta[] | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [folder, setFolder] = useState<string | null | "all">("all");
  const [showArch, setShowArch] = useState(false);
  const [menu, setMenu] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setErr("");
    try {
      const [p, f] = await Promise.all([api.projects(), api.folders()]);
      setProjects(p || []); setFolders(f || []);
    } catch (e: any) { setErr(e.message || "Could not load projects."); setProjects([]); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const byId = useMemo(() => Object.fromEntries(folders.map((f) => [f.id, f])), [folders]);
  const depth = (fid: string | null) => { let d = 0, c = fid; while (c && byId[c]) { d++; c = byId[c].parent_id; if (d > 8) break; } return d; };
  const folderPath = (fid: string | null) => { const parts: string[] = []; let c = fid; while (c && byId[c]) { parts.unshift(byId[c].name); c = byId[c].parent_id; if (parts.length > 8) break; } return parts.join(" / "); };

  const all = (projects || []).filter((p) => !p.shared);
  const nShared = (projects || []).filter((p) => p.shared).length;
  const match = (p: any) => `${p.name} ${p.id} ${p.best_guide || ""}`.toLowerCase().includes(q.trim().toLowerCase());
  const shown = all
    .filter((p) => (showArch ? p.archived : !p.archived))
    .filter((p) => folder === "all" || (p.folder_id || null) === folder)
    .filter(match)
    .sort((a, b) => (b.created || "").localeCompare(a.created || ""));
  const count = (fid: string | null | "all") => all.filter((p) => !p.archived && (fid === "all" || (p.folder_id || null) === fid)).length;
  const nArchived = all.filter((p) => p.archived).length;

  async function act(fn: () => Promise<any>) {
    setMenu(null); setBusy(true); setErr("");
    try { await fn(); await refresh(); } catch (e: any) { setErr(e.message || "Action failed."); } finally { setBusy(false); }
  }
  const newFolder = () => { const n = window.prompt("New folder name:"); if (n) act(() => api.createFolder(n)); };
  const subFolder = (parent: string) => { const n = window.prompt("New subfolder name:"); if (n) act(() => api.createFolder(n, parent)); };
  const renameFolder = (f: Folder) => { const n = window.prompt("Rename folder:", f.name); if (n) act(() => api.renameFolder(f.id, n)); };
  const delFolder = (f: Folder) => { if (window.confirm(`Delete folder "${f.name}"? Its projects move to the parent folder.`)) act(() => api.deleteFolder(f.id)); };
  const renameProj = (p: any) => { const n = window.prompt("Rename project:", p.name); if (n) act(() => api.patchProject(p.id, { name: n })); };
  const delProj = (p: any) => { if (window.confirm(`Delete "${p.name}"? This cannot be undone.`)) act(() => api.deleteProject(p.id)); };

  const FolderRow = ({ f }: { f: Folder }) => (
    <div className="group flex items-center gap-1" style={{ paddingLeft: depth(f.id) * 10 }}>
      <button
        onClick={() => setFolder(f.id)}
        aria-current={folder === f.id ? "true" : undefined}
        className={`flex-1 min-w-0 flex items-center gap-1.5 px-2 py-1 text-[11.5px] truncate ${folder === f.id ? "text-brand bg-brand/[0.08]" : "text-muted hover:text-ink"}`}
      >
        <span className="text-faint">▸</span><span className="truncate">{f.name}</span>
        <span className="ml-auto text-[10px] text-faint tabular-nums">{count(f.id)}</span>
      </button>
      <button onClick={() => subFolder(f.id)} title="New subfolder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-ink text-[11px]">＋</button>
      <button onClick={() => renameFolder(f)} title="Rename folder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-ink text-[11px]">✎</button>
      <button onClick={() => delFolder(f)} title="Delete folder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-bad text-[11px]">✕</button>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="library"
        title="Projects"
        description="Every design run you own, organised by folder. Open a project to inspect rankings, guide sets, outcomes and exports."
        primary={<Link href="/new" className="btn-primary text-[12px]">＋ Create project</Link>}
        actions={<button onClick={newFolder} className="btn-ghost text-[12px]">New folder</button>}
      />
      {err && <ErrorState message={err} retry={refresh} />}

      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-4 items-start">
        {/* ---- folders ---- */}
        <Panel title="folders" bodyClass="py-1.5 px-1">
          <button onClick={() => setFolder("all")} className={`w-full flex items-center px-2 py-1 text-[11.5px] ${folder === "all" ? "text-brand bg-brand/[0.08]" : "text-muted hover:text-ink"}`}>
            all projects <span className="ml-auto text-[10px] text-faint tabular-nums">{count("all")}</span>
          </button>
          <button onClick={() => setFolder(null)} className={`w-full flex items-center px-2 py-1 text-[11.5px] ${folder === null ? "text-brand bg-brand/[0.08]" : "text-muted hover:text-ink"}`}>
            unfiled <span className="ml-auto text-[10px] text-faint tabular-nums">{count(null)}</span>
          </button>
          {folders.length > 0 && <div className="border-t border-divider my-1" />}
          {folders.map((f) => <FolderRow key={f.id} f={f} />)}
          {folders.length === 0 && <div className="px-2 py-1.5 text-[10.5px] text-faint">No folders yet — use “New folder” to organise projects.</div>}
          {nShared > 0 && (
            <>
              <div className="border-t border-divider my-1" />
              <Link href="/collaborations" className="w-full flex items-center px-2 py-1 text-[11.5px] text-muted hover:text-ink">
                shared with me <span className="ml-auto text-[10px] text-faint tabular-nums">{nShared}</span>
              </Link>
            </>
          )}
          {nArchived > 0 && (
            <>
              <div className="border-t border-divider my-1" />
              <button onClick={() => setShowArch((v) => !v)} className={`w-full flex items-center px-2 py-1 text-[11.5px] ${showArch ? "text-brand bg-brand/[0.08]" : "text-muted hover:text-ink"}`}>
                archived <span className="ml-auto text-[10px] text-faint tabular-nums">{nArchived}</span>
              </button>
            </>
          )}
        </Panel>

        {/* ---- list ---- */}
        <Panel
          title={showArch ? "archived projects" : folder === "all" ? "all projects" : folder === null ? "unfiled" : folderPath(folder)}
          meta={
            <span className="flex items-center gap-1.5 border border-border bg-well px-2 py-0.5">
              <span className="text-brand">/</span>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter" aria-label="Filter projects"
                     className="w-32 bg-transparent border-0 outline-none text-[11px] text-ink placeholder:text-faint" />
            </span>
          }
          bodyClass=""
        >
          {projects === null ? <LoadingRows n={6} /> : shown.length === 0 ? (
            <EmptyState
              title={all.length === 0 ? "No projects yet." : "Nothing here."}
              body={all.length === 0 ? "Create a project to design and rank guide RNAs for a target sequence." : "Try another folder or clear the filter."}
              action={all.length === 0 ? <Link href="/new" className="btn-primary text-[12px]">Create your first project</Link> : undefined}
            />
          ) : (
            <table className="dtable">
              <thead><tr><th>project</th><th>guides</th><th>best guide</th><th>folder</th><th>created</th><th /></tr></thead>
              <tbody>
                {shown.map((p) => (
                  <tr key={p.id} className={p.archived ? "opacity-60" : ""}>
                    <td>
                      <Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link>
                      <span className="ml-2 text-faint text-[10.5px] tabular-nums">{p.id}</span>
                      {(p.n_collaborators || 0) > 0 && <span className="ml-2 text-[10px] text-faint" title="collaborators">◎ {p.n_collaborators}</span>}
                    </td>
                    <td className="tabular-nums">{p.n_guides ?? "—"}</td>
                    <td className="seqtext text-[11px]">{p.best_guide || "—"}</td>
                    <td className="text-muted truncate max-w-[160px]">{folderPath(p.folder_id) || "—"}</td>
                    <td className="text-muted whitespace-nowrap">{p.created}</td>
                    <td className="relative text-right">
                      <button onClick={() => setMenu(menu === p.id ? null : p.id)} aria-label={`Actions for ${p.name}`} disabled={busy}
                              className="text-faint hover:text-ink px-1 text-[14px] leading-none">⋯</button>
                      {menu === p.id && (
                        <div className="absolute right-0 z-20 mt-0.5 w-48 bg-surface border border-border p-1 text-[11px] text-left" onMouseLeave={() => setMenu(null)}>
                          <Link href={projectHref(p)} className="block px-2 py-1 text-ink hover:bg-brand/[0.08] hover:text-brand">open</Link>
                          <div className="px-2 py-1 label">move to</div>
                          <button onClick={() => act(() => api.patchProject(p.id, { folder_id: null }))} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">unfiled</button>
                          {folders.map((f) => (
                            <button key={f.id} onClick={() => act(() => api.patchProject(p.id, { folder_id: f.id }))} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand truncate">{folderPath(f.id)}</button>
                          ))}
                          <div className="border-t border-divider my-1" />
                          <button onClick={() => renameProj(p)} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">rename</button>
                          <button onClick={() => act(() => api.patchProject(p.id, { archived: !p.archived }))} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">{p.archived ? "unarchive" : "archive"}</button>
                          <button onClick={() => delProj(p)} className="w-full text-left px-2 py-1 text-bad hover:bg-bad/10">delete</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}
