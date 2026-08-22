"use client";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ValidationBanner } from "@/components/ValidationBanner";

/**
 * Application chrome — icon rail, project explorer, command bar, status bar.
 *
 * The rail carries destinations, the explorer carries content. Splitting them
 * means the project tree keeps its full height instead of competing with
 * navigation for one 240px column.
 */

type RailItem = { href: string; glyph: string; label: string };

function Rail({ items, path, name }: { items: RailItem[]; path: string; name: string }) {
  return (
    <nav className="w-[46px] flex-none bg-chrome border-r border-border flex flex-col items-center py-2 gap-0.5">
      <div className="w-[26px] h-[26px] mb-2.5 grid place-items-center border border-brand bg-brand/[0.12] text-brand text-[13px] font-semibold">
        Q
      </div>
      {items.map((it) => {
        const on = it.href === "/dashboard" ? path === it.href : path.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            title={it.label}
            aria-label={it.label}
            aria-current={on ? "page" : undefined}
            className={`w-[30px] h-[30px] grid place-items-center text-[13px] transition-colors ${
              on
                ? "text-brand bg-brand/[0.08] shadow-[inset_0_0_0_1px_rgb(var(--qg-accent)/0.22)]"
                : "text-faint hover:text-ink"
            }`}
          >
            {it.glyph}
          </Link>
        );
      })}
      <div className="flex-1" />
      <ThemeToggle compact />
      <div className="w-[26px] h-[26px] grid place-items-center text-[11px] text-faint" title={name}>
        {name[0]?.toUpperCase()}
      </div>
    </nav>
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

  // The command bar echoes the current route as the call that produced the view.
  const commandLine = useMemo(() => {
    if (path.startsWith("/project/")) {
      const [, , id, tab] = path.split("/");
      return `open --project ${id}${tab ? ` --view ${tab}` : ""}`;
    }
    if (path === "/new") return "design --new";
    if (path === "/account") return "account --show";
    if (path === "/buy") return "credits --purchase";
    if (path === "/admin") return "admin --console";
    return "ls --projects --sort last_run";
  }, [path]);

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

  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center bg-bg text-faint text-[12px] tracking-[0.14em] uppercase">
        loading&hellip;
      </div>
    );
  }
  if (!account) return null;
  const low = account.credits < 5;

  const railItems: RailItem[] = [
    { href: "/dashboard", glyph: "▦", label: "Dashboard" },
    { href: "/new", glyph: "＋", label: "New design run" },
    { href: "/account", glyph: "◷", label: "Account" },
    { href: "/buy", glyph: "◈", label: "Credits" },
    ...(account.is_admin ? [{ href: "/admin", glyph: "⌗", label: "Admin" }] : []),
  ];

  function ProjectRow({ p }: { p: any }) {
    const on = path.startsWith(`/project/${p.id}`);
    return (
      <div className="relative">
        <div className={`group flex items-center pr-1 ${on ? "bg-brand/[0.08] shadow-[inset_2px_0_0_rgb(var(--qg-accent))]" : "hover:bg-brand/5"}`}>
          <Link
            href={`/project/${p.id}`}
            className={`flex-1 min-w-0 flex items-center gap-1.5 px-2 py-1 text-[11.5px] truncate ${on ? "text-brand" : "text-muted"}`}
          >
            <span className={on ? "text-brand" : "text-faint"}>{on ? "›" : "·"}</span>
            <span className="truncate">{p.name}</span>
            <span className="ml-auto pl-2 text-[9.5px] text-faint tabular-nums">{p.id}</span>
          </Link>
          <button
            onClick={() => setMenu(menu === p.id ? null : p.id)}
            aria-label={`Actions for ${p.name}`}
            className="text-faint hover:text-ink px-1 text-[13px] leading-none"
          >
            ⋯
          </button>
        </div>
        {menu === p.id && (
          <div className="absolute right-1 z-20 mt-0.5 w-44 bg-surface border border-border p-1 text-[11px]">
            <div className="px-2 py-1 label">move to</div>
            <button onClick={() => moveProj(p.id, null)} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">unfiled</button>
            {folders.map((f) => (
              <button key={f.id} onClick={() => moveProj(p.id, f.id)} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand truncate">{f.name}</button>
            ))}
            <div className="border-t border-divider my-1" />
            <button onClick={() => renameProj(p.id, p.name)} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">rename</button>
            <button onClick={() => archiveProj(p.id, !p.archived)} className="w-full text-left px-2 py-1 text-muted hover:bg-brand/[0.08] hover:text-brand">{p.archived ? "unarchive" : "archive"}</button>
            <button onClick={() => delProj(p.id)} className="w-full text-left px-2 py-1 text-bad hover:bg-bad/10">delete</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen h-screen flex bg-bg text-ink overflow-hidden">
      <Rail items={railItems} path={path} name={account.name} />

      {/* ---- project explorer ---- */}
      <aside className="w-[224px] flex-none bg-surface border-r border-border flex flex-col">
        <div className="px-3 py-2 border-b border-border flex items-center">
          <span className="label">project explorer</span>
          <button onClick={newFolder} title="New folder" aria-label="New folder"
            className="ml-auto text-faint hover:text-brand text-[13px] leading-none">＋</button>
        </div>

        <div className="px-2 pt-2">
          <div className="flex items-center gap-1.5 border border-border bg-well px-2 py-1">
            <span className="text-brand text-[11px]">/</span>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="filter"
              aria-label="Filter projects"
              className="w-full bg-transparent border-0 outline-none text-[11px] text-ink placeholder:text-faint"
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto px-1.5 pt-1" onClick={() => menu && setMenu(null)}>
          {inFolder(null).map((p) => <ProjectRow key={p.id} p={p} />)}

          {folders.map((f) => {
            const kids = inFolder(f.id);
            const open = openF[f.id] ?? true;
            return (
              <div key={f.id} style={{ marginLeft: depth(f.id) * 8 }}>
                <div className="group flex items-center gap-1 mt-1.5">
                  <button
                    onClick={() => setOpenF((o) => ({ ...o, [f.id]: !open }))}
                    className="flex-1 min-w-0 flex items-center gap-1.5 px-1.5 py-1 text-[9.5px] tracking-[0.14em] uppercase text-faint hover:text-ink"
                  >
                    <span>{open ? "▾" : "▸"}</span>
                    <span className="truncate">{f.name}</span>
                    <span className="ml-auto">{kids.length}</span>
                  </button>
                  <button onClick={() => subFolder(f.id)} title="New subfolder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-ink text-[11px]">＋</button>
                  <button onClick={() => renameFolder(f.id, f.name)} title="Rename folder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-ink text-[11px]">✎</button>
                  <button onClick={() => delFolder(f.id)} title="Delete folder" className="opacity-0 group-hover:opacity-100 text-faint hover:text-bad text-[11px]">✕</button>
                </div>
                {open && kids.map((p) => <ProjectRow key={p.id} p={p} />)}
              </div>
            );
          })}

          {active.length === 0 && (
            <div className="px-2 py-2 text-[11px] text-faint">no projects.</div>
          )}

          {archived.length > 0 && (
            <div className="mt-2 border-t border-divider pt-2">
              <button
                onClick={() => setShowArch((v) => !v)}
                className="px-1.5 py-1 text-[9.5px] tracking-[0.14em] uppercase text-faint hover:text-ink"
              >
                {showArch ? "▾" : "▸"} archived {archived.length}
              </button>
              {showArch && archived.map((p) => (
                <div key={p.id} className="opacity-60"><ProjectRow p={p} /></div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-border px-3 py-2 flex items-center gap-2 text-[10px] text-faint">
          <span>credits</span>
          <b className={low ? "text-bad" : "text-brand"}>{account.credits}</b>
          <span className="ml-auto truncate" title={account.name}>{account.name}</span>
          <button onClick={signOut} title="Log out" aria-label="Log out" className="hover:text-ink">⏻</button>
        </div>
      </aside>

      {/* ---- main column ---- */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="h-[34px] flex-none bg-surface border-b border-border flex items-center gap-2 px-3 text-[11.5px]">
          <span className="text-brand">qguide ›</span>
          <span className="text-ink truncate">{commandLine}</span>
          <span className="inline-block w-[7px] h-[14px] bg-brand opacity-70" aria-hidden />
          <span className="flex-1" />
          {low && <span className="text-bad text-[10.5px]">! {account.credits} credits remaining</span>}
          <span className="text-faint text-[10.5px]">{account.plan}</span>
        </div>

        <ValidationBanner />

        <main className="flex-1 min-h-0 overflow-auto p-3">{children}</main>

        <div className="h-[22px] flex-none bg-chrome border-t border-border flex items-center gap-4 px-3 text-[10px] text-faint">
          <span className="text-brand">● api ok</span>
          <span>projects <b className="text-muted font-normal">{projects.length}</b></span>
          <span>db <b className="text-muted font-normal">postgres</b></span>
          <span className="flex-1" />
          <span>GRCh38</span>
          <span>credits <b className={low ? "text-bad font-normal" : "text-muted font-normal"}>{account.credits}</b></span>
          <span className="hidden lg:inline">/ filter · ? help</span>
        </div>
      </div>
    </div>
  );
}
