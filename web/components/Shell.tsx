"use client";
import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Dna } from "./Dna";

function NavLink({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link href={href}
      className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition
        ${active ? "bg-brand text-white shadow" : "text-[#DCEAE5] hover:bg-white/10"}`}>
      <span>{icon}</span>{label}
    </Link>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { account, ready } = useRequireAuth();
  const { signOut } = useAuth();
  const path = usePathname();
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    if (account) api.projects().then(setProjects).catch(() => {});
  }, [account, path]);

  if (!ready)
    return <div className="min-h-screen grid place-items-center text-muted">Loading…</div>;
  if (!account) return null;

  const low = account.credits < 5;

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 shrink-0 p-4 flex flex-col gap-2"
        style={{ background: "linear-gradient(180deg,#3A1B57,#28123D)" }}>
        <div className="flex items-center gap-2">
          <span className="text-2xl">🧬</span>
          <div>
            <div className="font-display font-extrabold text-xl bg-gradient-to-r from-brand-light to-[#EAD7FA] bg-clip-text text-transparent">Q-Guide</div>
            <div className="text-[10px] tracking-wider font-semibold text-[#A892BE]">QUANTUM-ASSISTED gRNA DESIGN</div>
          </div>
        </div>
        <Dna width={220} height={40} turns={3.2} s1="#C49AE0" s2="#EAD7FA" />

        <div className="rounded-2xl border border-brand-light/20 bg-white/5 p-3 my-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full grid place-items-center font-extrabold text-white"
              style={{ background: "linear-gradient(135deg,#7A33A6,#C49AE0)" }}>{account.name[0]?.toUpperCase()}</div>
            <div>
              <div className="text-sm font-bold text-[#F1E8FA]">{account.name}</div>
              <div className="text-[11px] font-semibold text-[#A892BE]">{account.plan}</div>
            </div>
          </div>
          <div className={`mt-2 rounded-lg px-2 py-1 text-sm font-extrabold flex justify-between ${low ? "bg-bad/25 text-[#FFD9E2]" : "bg-brand-light/20 text-[#EAD7FA]"}`}>
            <span>💎 {account.credits} credits</span><span className="text-[11px] font-semibold opacity-80">5/run</span>
          </div>
        </div>

        <NavLink href="/buy" icon="💳" label="Buy Credits" active={path === "/buy"} />
        <NavLink href="/new" icon="➕" label="New Project" active={path === "/new"} />
        <NavLink href="/account" icon="👤" label="Account" active={path === "/account"} />
        {account.is_admin && <NavLink href="/admin" icon="🛡️" label="Admin" active={path === "/admin"} />}

        {projects.length > 0 && (
          <div className="mt-2">
            <div className="text-[10px] font-bold tracking-wider text-[#A892BE] px-1 mb-1">PROJECTS</div>
            <div className="flex flex-col gap-1 max-h-60 overflow-auto">
              {projects.map((p) => (
                <Link key={p.id} href={`/project/${p.id}`}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition truncate
                    ${path === `/project/${p.id}` ? "bg-brand text-white" : "text-[#DCEAE5] hover:bg-white/10"}`}>
                  📁 {p.name} · {p.id}
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto pt-2">
          <button onClick={signOut} className="w-full rounded-xl px-3 py-2 text-sm font-semibold text-[#DCEAE5] hover:bg-white/10 text-left">↪ Log out</button>
          <div className="text-[10px] text-[#A892BE] px-1 mt-1">Q-Guide v1.0 (prototype)</div>
        </div>
      </aside>

      <main className="flex-1 p-6 max-w-[1500px]">{children}</main>
    </div>
  );
}
