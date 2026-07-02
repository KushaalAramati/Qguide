"use client";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

function NavLink({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link href={href}
      className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition
        ${active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}>
      <span className="w-4 text-center opacity-90">{icon}</span>{label}
    </Link>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { account, ready } = useRequireAuth();
  const { signOut } = useAuth();
  const path = usePathname();
  const [projects, setProjects] = useState<any[]>([]);
  const [folders, setFolders] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [openF, setOpenF] = useState<Record<string, boolean>>({});
  const [menu, setMenu] = useState<string | null>(null);
  const [showArch, setShowArch] = useState(false);

  const refresh = useCallback(() => {
    if (!account) return;
    api.projects().then(setProjects).catch(() => {});
    api.folders().then(setFolders).catch(() => {});
  }, [account]);

  useEffect(() => { refresh(); }, [refresh, path]);

  const depth = useCallback((fid: string | null): number => {
    let d = 0, cur = fid;
    const by: Record<string, any> = Object.fromEntries(folders.map((f) => [f.id, f]));
    while (cur && by[cur]) { d++; cur = by[cur].parent_id; if (d > 8) break; }
    return d;
  }, [folders]);

  const match = (p: any) => `${p.name} ${p.id}`.toLowerCase().includes(q.toLowerCase());
  const active = projects.filter((p) => !p.archived && match(p));
  const archived = projects.filter((p) => p.archived && match(p));
  const inFolder = (fid: string | null) => active.filter((p) => (p.folder_id || null) === fid);

  async function newFolder() {
    const name = window.prompt("New folder name:");
    if (name) { await api.createFolder(name); refresh(); }
  }
  async function subFolder(parent: string) {
    const name = window.prompt("New subfolder name:");
    if (name) { await api.createFolder(name, parent); refresh(); }
  }
  async function renameFolder(fid: string, cur: string) {
    const name = window.prompt("Rename folder:", cur);
    if (name) { await api.renameFolder(fid, name); refresh(); }
  }
  async function delFolder(fid: string) {
    if (window.confirm("Delete this folder? Its projects move to the parent.")) { await api.deleteFolder(fid); refresh(); }
  }
  async function moveProj(pid: string, fid: string | null) { setMenu(null); await api.patchProject(pid, { folder_id: fid }); refresh(); }
  async function renameProj(pid: string, cur: string) {
    setMenu(null); const name = window.prompt("Rename project:", cur);
    if (name) { await api.patchProject(pid, { name }); refresh(); }
  }
  async function archiveProj(pid: string, val: boolean) { setMenu(null); await api.patchProject(pid, { archived: val }); refresh(); }
  async function delProj(pid: string) {
    setMenu(null);
    if (window.confirm("Delete this project? This cannot be undone.")) { await api.deleteProject(pid); refresh(); }
  }

  if (!ready) return <div className="min-h-screen grid place-items-center text-muted">Loading…</div>;
  if (!account) return null;
  const low = account.credits < 5;
  const is = (href: string) => path === href;

  function ProjectRow({ p }: { p: any }) {
    const on = path.startsWith(`/project/${p.id}`);
    return (
      <div className="relative">
        <div className={`group flex items-center rounded-md pr-1 ${on ? "bg-brand/25" : "hover:bg-white/5"}`}>
          <Link href={`/project/${p.id}`}
            className={`flex-1 min-w-0 px-2.5 py-1.5 text-xs font-medium truncate ${on ? "text-white" : "text-slate-300"}`}>
            {p.name} <span className="text-slate-500">· {p.id}</span>
          </Link>
          <button onClick={() => setMenu(menu === p.id ? null : p.id)}
            className="text-slate-400 hover:text-white px-1 text-sm">⋯</button>
        </div>
        {menu === p.id && (
          <div className="absolute right-1 z-20 mt-1 w-44 rounded-lg bg-[#20263a] border border-white/10 shadow-lg p-1 text-xs">
            <div className="px-2 py-1 text-slate-500">Move to…</div>
            <button onClick={() => moveProj(p.id, null)} className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-slate-200">Unfiled</button>
            {folders.map((f) => (
              <button key={f.id} onClick={() => moveProj(p.id, f.id)} className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-slate-200 truncate">{f.name}</button>
            ))}
            <div className="border-t border-white/10 my-1" />
            <button onClick={() => renameProj(p.id, p.name)} className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-slate-200">Rename</button>
            <button onClick={() => archiveProj(p.id, !p.archived)} className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-slate-200">{p.archived ? "Unarchive" : "Archive"}</button>
            <button onClick={() => delProj(p.id)} className="w-full text-left px-2 py-1 rounded hover:bg-white/10 text-rose-300">Delete</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-bg">
      <aside className="w-60 shrink-0 flex flex-col gap-1 p-3 bg-sidebar sticky top-0 h-screen">
        <div className="flex items-center gap-2 px-2 py-2">
          <span className="grid place-items-center w-8 h-8 rounded-lg bg-brand text-white font-display font-extrabold">Q</span>
          <div>
            <div className="font-display font-extrabold text-[15px] text-white leading-none">QGuide</div>
            <div className="text-[9px] tracking-[0.14em] font-semibold text-slate-400 mt-1">GUIDE-RNA DESIGN</div>
          </div>
        </div>

        <div className="mt-1 flex flex-col gap-0.5">
          <NavLink href="/dashboard" icon="◧" label="Dashboard" active={is("/dashboard")} />
          <NavLink href="/new" icon="＋" label="New project" active={is("/new")} />
          <NavLink href="/account" icon="◔" label="Account" active={is("/account")} />
          <NavLink href="/buy" icon="◈" label="Credits" active={is("/buy")} />
          {account.is_admin && <NavLink href="/admin" icon="⚙" label="Admin" active={is("/admin")} />}
        </div>

        <div className="mt-3 flex items-center justify-between px-1">
          <div className="text-[10px] font-bold tracking-wider text-slate-500">PROJECTS</div>
          <button onClick={newFolder} title="New folder" className="text-slate-400 hover:text-white text-sm leading-none">＋⌸</button>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…"
          className="w-full rounded-md bg-white/5 border border-white/10 text-slate-200 placeholder:text-slate-500 text-xs px-2.5 py-1.5 outline-none focus:border-brand/60 mt-1" />

        <div className="flex flex-col gap-0.5 mt-2 overflow-auto flex-1 pr-0.5" onClick={() => menu && setMenu(null)}>
          {/* unfiled */}
          {inFolder(null).map((p) => <ProjectRow key={p.id} p={p} />)}

          {/* folders */}
          {folders.map((f) => {
            const kids = inFolder(f.id);
            const open = openF[f.id] ?? true;
            return (
              <div key={f.id} style={{ marginLeft: depth(f.id) * 8 }}>
                <div className="group flex items-center gap-1 mt-1">
                  <button onClick={() => setOpenF((o) => ({ ...o, [f.id]: !open }))}
                    className="flex-1 min-w-0 flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-white px-1 py-1">
                    <span>{open ? "▾" : "▸"}</span><span className="truncate">{f.name}</span>
                    <span className="text-slate-600">({kids.length})</span>
                  </button>
                  <button onClick={() => subFolder(f.id)} title="Subfolder" className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-white text-xs">＋</button>
                  <button onClick={() => renameFolder(f.id, f.name)} title="Rename" className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-white text-xs">✎</button>
                  <button onClick={() => delFolder(f.id)} title="Delete" className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-300 text-xs">✕</button>
                </div>
                {open && kids.map((p) => <div key={p.id} className="ml-2"><ProjectRow p={p} /></div>)}
              </div>
            );
          })}

          {active.length === 0 && <div className="text-[11px] text-slate-500 px-3 py-2">No projects.</div>}

          {/* archived */}
          {archived.length > 0 && (
            <div className="mt-2 border-t border-white/10 pt-2">
              <button onClick={() => setShowArch((v) => !v)} className="text-[10px] font-bold tracking-wider text-slate-500 hover:text-slate-300 px-1">
                {showArch ? "▾" : "▸"} ARCHIVED ({archived.length})
              </button>
              {showArch && archived.map((p) => <div key={p.id} className="opacity-70"><ProjectRow p={p} /></div>)}
            </div>
          )}
        </div>

        <div className="mt-2 pt-2 border-t border-white/10">
          <div className={`rounded-lg px-3 py-2 text-sm font-semibold flex items-center justify-between ${low ? "bg-bad/20 text-rose-200" : "bg-white/5 text-slate-200"}`}>
            <span>◈ {account.credits}</span><span className="text-[10px] font-medium opacity-70">credits</span>
          </div>
          <div className="flex items-center gap-2 mt-2 px-1">
            <div className="w-7 h-7 rounded-full grid place-items-center text-xs font-bold text-white bg-brand">{account.name[0]?.toUpperCase()}</div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-slate-100 truncate">{account.name}</div>
              <div className="text-[10px] text-slate-500 truncate">{account.plan}</div>
            </div>
            <button onClick={signOut} title="Log out" className="text-slate-400 hover:text-white text-sm px-1">⏻</button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 p-6 max-w-[1500px]">{children}</main>
    </div>
  );
}
