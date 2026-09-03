"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { visibleNav, isActive } from "@/lib/nav";
import { LogoMark } from "@/components/Brand";
import { BRANDING } from "@/lib/branding";
import { ThemeToggle } from "@/components/ThemeToggle";

const STORAGE_KEY = "qg-sidebar";          // "expanded" | "collapsed"
const AUTO_COLLAPSE_BELOW = 1024;          // px — laptops keep labels, tablets collapse

/**
 * Sidebar state. The user's explicit choice wins and is remembered; without one
 * the sidebar collapses on narrow viewports and expands on wide ones.
 */
export function useSidebarState() {
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch {}
    if (stored === "collapsed" || stored === "expanded") setCollapsed(stored === "collapsed");
    else setCollapsed(window.innerWidth < AUTO_COLLAPSE_BELOW);
    setReady(true);

    // Follow viewport changes only while the user has not chosen explicitly.
    const onResize = () => {
      let s: string | null = null;
      try { s = localStorage.getItem(STORAGE_KEY); } catch {}
      if (!s) setCollapsed(window.innerWidth < AUTO_COLLAPSE_BELOW);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      try { localStorage.setItem(STORAGE_KEY, next ? "collapsed" : "expanded"); } catch {}
      return next;
    });
  }
  return { collapsed, toggle, ready };
}

export function Sidebar({
  collapsed, onToggle, onNavigate, drawer = false,
}: {
  collapsed: boolean; onToggle: () => void; onNavigate?: () => void;
  /** Rendered inside the mobile drawer: always expanded, no collapse control. */
  drawer?: boolean;
}) {
  const { account, signOut } = useAuth();
  const path = usePathname();
  const items = visibleNav(account);
  const slim = collapsed && !drawer;
  const width = slim ? "w-[52px]" : "w-[220px]";

  return (
    <nav
      aria-label="Primary"
      className={`${width} h-full flex-none bg-chrome border-r border-border flex flex-col transition-[width] duration-150 ease-out overflow-hidden`}
    >
      {/* ---- brand ---- */}
      <Link
        href="/dashboard"
        className={`flex items-center gap-2.5 h-[46px] px-[13px] border-b border-border ${slim ? "justify-center px-0" : ""}`}
        title={BRANDING.APP_NAME}
      >
        <LogoMark size={26} />
        {!slim && <span className="text-[13.5px] font-medium text-title tracking-tightest truncate">{BRANDING.APP_NAME}</span>}
      </Link>

      {/* ---- destinations ---- */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-2">
        {items.map((it) => {
          const on = isActive(it, path);
          return (
            <div key={it.href} className="relative group px-1.5 py-px">
              <Link
                href={it.href}
                onClick={onNavigate}
                aria-current={on ? "page" : undefined}
                aria-label={slim ? it.label : undefined}
                className={`flex items-center gap-2.5 h-[32px] px-2 text-[12px] whitespace-nowrap transition-colors ${
                  slim ? "justify-center px-0" : ""
                } ${
                  on
                    ? "text-brand bg-brand/[0.10] shadow-[inset_2px_0_0_rgb(var(--qg-accent))]"
                    : "text-muted hover:text-ink hover:bg-brand/[0.05]"
                }`}
              >
                <span className={`w-[18px] text-center text-[13px] leading-none ${on ? "text-brand" : "text-faint group-hover:text-ink"}`} aria-hidden>
                  {it.glyph}
                </span>
                {!slim && <span className="truncate">{it.label}</span>}
                {!slim && it.admin && <span className="ml-auto text-[9px] tracking-[0.12em] uppercase text-faint">admin</span>}
              </Link>
              {slim && (
                <span role="tooltip" className="nav-tip">
                  <span className="text-ink">{it.label}</span>
                  {it.hint && <span className="block text-faint">{it.hint}</span>}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ---- account + controls ---- */}
      <div className="border-t border-border p-1.5 flex flex-col gap-px">
        <div className={`flex items-center gap-2 h-[32px] px-2 ${slim ? "justify-center px-0" : ""}`} title={`${account?.name} · ${account?.email}`}>
          <span className="w-[22px] h-[22px] flex-none grid place-items-center border border-border bg-surface text-[11px] text-muted">
            {account?.name?.[0]?.toUpperCase()}
          </span>
          {!slim && (
            <span className="min-w-0 leading-tight">
              <span className="block text-[11.5px] text-ink truncate">{account?.name}</span>
              <span className="block text-[10px] text-faint truncate">{account?.plan}{account?.is_admin ? " · admin" : ""}</span>
            </span>
          )}
        </div>

        <div className={`flex items-center ${slim ? "flex-col gap-px" : "gap-px"}`}>
          <ThemeToggle compact />
          <button
            onClick={signOut}
            title="Sign out"
            aria-label="Sign out"
            className="h-[30px] w-[30px] grid place-items-center text-faint hover:text-ink text-[13px]"
          >
            ⏻
          </button>
          {!drawer && (
            <button
              onClick={onToggle}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              className={`h-[30px] grid place-items-center text-faint hover:text-brand text-[13px] ${slim ? "w-[30px]" : "ml-auto w-[30px]"}`}
            >
              {collapsed ? "»" : "«"}
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
