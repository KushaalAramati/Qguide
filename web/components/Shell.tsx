"use client";
import { ReactNode, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { ValidationBanner } from "@/components/ValidationBanner";
import { Sidebar, useSidebarState } from "@/components/Sidebar";
import { OnboardingTour } from "@/components/Onboarding";
import { LogoMark, LegalFooter } from "@/components/Brand";
import { APP_SLUG, BRANDING } from "@/lib/branding";

/**
 * Application chrome — collapsible sidebar, command bar, status bar.
 *
 * Laptop/desktop: the sidebar is a column that collapses to icons (with
 * tooltips) and remembers the choice. Below the `md` breakpoint it becomes a
 * drawer opened from the command bar so the content keeps the full width.
 */
export function Shell({ children }: { children: ReactNode }) {
  const { account, ready } = useRequireAuth();
  const { signOut } = useAuth();
  const path = usePathname();
  const { collapsed, toggle } = useSidebarState();
  const [drawer, setDrawer] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [nProjects, setNProjects] = useState<number | null>(null);

  useEffect(() => { setDrawer(false); }, [path]);
  useEffect(() => {
    if (!account) return;
    api.health().then(() => setApiOk(true)).catch(() => setApiOk(false));
    api.projects().then((p) => setNProjects((p || []).filter((x: any) => !x.archived).length)).catch(() => {});
  }, [account, path]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  // The command bar echoes the current route as the call that produced the view.
  const commandLine = useMemo(() => {
    if (path.startsWith("/project/")) {
      const [, , id, tab] = path.split("/");
      return `open --project ${id}${tab ? ` --view ${tab}` : ""}`;
    }
    const map: Record<string, string> = {
      "/new": "design --new", "/projects": "ls --projects", "/account": "settings --show",
      "/buy": "credits --purchase", "/admin": "admin --console", "/dashboard": "status --overview",
    };
    return map[path] || map[Object.keys(map).find((k) => path.startsWith(k + "/")) || ""] || "status --overview";
  }, [path]);

  if (!ready) {
    return (
      <div className="min-h-screen grid place-items-center bg-bg text-faint text-[12px] tracking-[0.14em] uppercase">
        loading&hellip;
      </div>
    );
  }
  if (!account) return null;
  const low = account.credits < 5;

  return (
    <div className="h-screen flex bg-bg text-ink overflow-hidden">
      <OnboardingTour />
      {/* ---- sidebar (laptop / desktop) ---- */}
      <div className="hidden md:flex h-full">
        <Sidebar collapsed={collapsed} onToggle={toggle} />
      </div>

      {/* ---- drawer (mobile) ---- */}
      {drawer && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div className="h-full shadow-[1px_0_0_rgb(var(--qg-line))]">
            <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => setDrawer(false)} drawer />
          </div>
          <button aria-label="Close navigation" className="flex-1 bg-black/40" onClick={() => setDrawer(false)} />
        </div>
      )}

      {/* ---- main column ---- */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="h-[46px] md:h-[34px] flex-none bg-surface border-b border-border flex items-center gap-2 px-3 text-[11.5px]">
          <button
            onClick={() => setDrawer(true)}
            aria-label="Open navigation"
            className="md:hidden w-[30px] h-[30px] grid place-items-center text-muted hover:text-ink -ml-1.5"
          >
            ☰
          </button>
          <span className="md:hidden"><LogoMark size={22} /></span>
          <span className="text-brand hidden sm:inline">{APP_SLUG} ›</span>
          <span className="text-ink truncate hidden sm:inline">{commandLine}</span>
          <span className="hidden sm:inline-block w-[7px] h-[14px] bg-brand opacity-70" aria-hidden />
          <span className="flex-1" />
          {low && (
            <Link href="/buy" className="text-bad text-[10.5px] hover:underline">
              ! {account.credits} credits remaining
            </Link>
          )}
          <span className="text-faint text-[10.5px] hidden sm:inline">{account.plan}</span>
          <button onClick={signOut} className="md:hidden text-faint hover:text-ink" title="Sign out" aria-label="Sign out">⏻</button>
        </div>

        <ValidationBanner />

        <main className="flex-1 min-h-0 overflow-auto">
          <div className="p-3 md:p-4 max-w-[1400px]">{children}</div>
          <div className="px-3 md:px-4 pb-3">
            <LegalFooter className="pt-3 border-t border-divider" />
          </div>
        </main>

        <div className="h-[22px] flex-none bg-chrome border-t border-border hidden sm:flex items-center gap-4 px-3 text-[10px] text-faint">
          <span className={apiOk === false ? "text-bad" : apiOk ? "text-brand" : ""}>
            ● api {apiOk === null ? "…" : apiOk ? "ok" : "unreachable"}
          </span>
          {nProjects !== null && <span>projects <b className="text-muted font-normal">{nProjects}</b></span>}
          <span className="flex-1" />
          <span className="truncate hidden lg:inline">research use only — not validated clinical advice</span>
          <span>credits <b className={low ? "text-bad font-normal" : "text-muted font-normal"}>{account.credits}</b></span>
          <span className="hidden xl:inline">{BRANDING.APP_NAME}</span>
        </div>
      </div>
    </div>
  );
}
