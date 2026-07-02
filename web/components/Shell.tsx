"use client";
import { ReactNode, useEffect, useMemo, useState } from "react";
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
  const [q, setQ] = useState("");

  useEffect(() => {
    if (account) api.projects().then(setProjects).catch(() => {});
  }, [account, path]);

  const filtered = useMemo(
    () => projects.filter((p) => `${p.name} ${p.id}`.toLowerCase().includes(q.toLowerCase())),
    [projects, q]);

  if (!ready)
    return <div className="min-h-screen grid place-items-center text-muted">Loading…</div>;
  if (!account) return null;

  const low = account.credits < 5;
  const is = (href: string) => path === href;

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

        <div className="mt-3 px-1">
          <div className="text-[10px] font-bold tracking-wider text-slate-500 mb-1.5 px-1">PROJECTS</div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…"
            className="w-full rounded-md bg-white/5 border border-white/10 text-slate-200 placeholder:text-slate-500 text-xs px-2.5 py-1.5 outline-none focus:border-brand/60" />
        </div>
        <div className="flex flex-col gap-0.5 mt-1 overflow-auto flex-1 pr-0.5">
          {filtered.length === 0 && <div className="text-[11px] text-slate-500 px-3 py-2">No projects.</div>}
          {filtered.map((p) => (
            <Link key={p.id} href={`/project/${p.id}`}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition truncate
                ${path.startsWith(`/project/${p.id}`) ? "bg-brand/25 text-white" : "text-slate-300 hover:bg-white/5"}`}>
              {p.name} <span className="text-slate-500">· {p.id}</span>
            </Link>
          ))}
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
