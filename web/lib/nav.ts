import type { Account } from "@/lib/api";

/**
 * Primary navigation. One list, consumed by the sidebar (expanded + collapsed)
 * and the mobile drawer, so destinations can never drift between them.
 *
 * `glyph` is a typographic mark, not an icon font — the interface is mono-first.
 * Items are only listed once their page exists; nothing here is a placeholder.
 */
export interface NavItem {
  href: string;
  label: string;
  glyph: string;
  /** Matches when the path starts with `href` (default) or equals it exactly. */
  exact?: boolean;
  /** Only shown (and only reachable server-side) for administrators. */
  admin?: boolean;
  /** Short helper shown as the tooltip's second line when collapsed. */
  hint?: string;
}

export const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", glyph: "▦", exact: true, hint: "Overview and recent work" },
  { href: "/projects", label: "Projects", glyph: "▤", hint: "All projects and folders" },
  { href: "/new", label: "New Analysis", glyph: "＋", hint: "Design guides for a sequence" },
  { href: "/collaborations", label: "Collaborations", glyph: "◎", hint: "Projects shared with you" },
  { href: "/research", label: "Research Tools", glyph: "⌬", hint: "Batch runs, templates, comparison, history" },
  { href: "/buy", label: "Billing", glyph: "◈", hint: "Credits and purchases" },
  { href: "/account", label: "Settings", glyph: "◷", hint: "Profile, security, notifications" },
  { href: "/admin", label: "Admin Dashboard", glyph: "⌗", admin: true, hint: "Users, roles, system health" },
];

export function visibleNav(account: Account | null): NavItem[] {
  return NAV.filter((n) => !n.admin || account?.is_admin);
}

export function isActive(item: NavItem, path: string): boolean {
  return item.exact ? path === item.href : path === item.href || path.startsWith(item.href + "/");
}
