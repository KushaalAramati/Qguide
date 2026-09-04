"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api, Notification } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const POLL_MS = 60_000;

const GLYPH: Record<string, string> = {
  project_invite: "◎", project_role_changed: "◎", project_access_removed: "◎", collaborator_left: "◎",
  project_renamed: "▤", project_updated: "▤", analysis_completed: "▦", project_deleted: "▤",
  security: "⚿", account: "◷", billing: "◈", subscription: "◈",
};

/**
 * Notification bell. Unread count is polled (and refreshed on navigation);
 * opening the panel loads the latest items. Clicking an item marks it read and
 * follows its deep link.
 */
export function NotificationBell() {
  const { account } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[] | null>(null);
  const [err, setErr] = useState("");
  const wrap = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(() => {
    if (!account) return;
    api.unreadCount().then((r) => setUnread(r.unread)).catch(() => {});
  }, [account]);

  useEffect(() => { refreshCount(); }, [refreshCount, path]);
  useEffect(() => {
    const t = setInterval(refreshCount, POLL_MS);
    return () => clearInterval(t);
  }, [refreshCount]);

  async function load() {
    setErr("");
    try { const r = await api.notifications(30); setItems(r.items); setUnread(r.unread); }
    catch (e: any) { setErr(e.message || "Could not load notifications."); setItems([]); }
  }
  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) load();
  }
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc); window.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); window.removeEventListener("keydown", onKey); };
  }, [open]);

  async function openItem(n: Notification) {
    if (!n.read) {
      setItems((it) => it?.map((x) => (x.id === n.id ? { ...x, read: true } : x)) ?? it);
      api.markRead(n.id).then((r) => setUnread(r.unread)).catch(() => {});
    }
    setOpen(false);
    if (n.link) router.push(n.link);
  }
  async function toggleRead(n: Notification, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const r = n.read ? await api.markUnread(n.id) : await api.markRead(n.id);
      setUnread(r.unread);
      setItems((it) => it?.map((x) => (x.id === n.id ? { ...x, read: !n.read } : x)) ?? it);
    } catch {}
  }
  async function allRead() {
    try { await api.markAllRead(); setUnread(0); setItems((it) => it?.map((x) => ({ ...x, read: true })) ?? it); } catch {}
  }

  if (!account) return null;

  return (
    <div ref={wrap} className="relative">
      <button
        onClick={toggle}
        aria-label={unread ? `${unread} unread notifications` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Notifications"
        className={`relative h-[28px] min-w-[28px] px-1 grid place-items-center text-[15px] ${open ? "text-brand" : unread ? "text-ink" : "text-muted hover:text-ink"}`}
      >
        ◔
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 grid place-items-center bg-brand text-bg text-[9px] leading-none tabular-nums">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div role="dialog" aria-label="Notifications" className="absolute right-0 z-40 mt-1 w-[360px] max-w-[calc(100vw-24px)] bg-surface border border-border">
          <div className="panel-head">
            <span>notifications</span>
            <span className="meta">
              {unread > 0 && <button onClick={allRead} className="text-brand hover:underline mr-3">mark all read</button>}
              <Link href="/account?section=Notifications" onClick={() => setOpen(false)} className="hover:text-ink">settings</Link>
            </span>
          </div>
          <div className="max-h-[420px] overflow-auto">
            {err && <div className="px-3 py-2 text-[11.5px] text-bad">{err}</div>}
            {items === null && !err && <div className="px-3 py-3 text-[11px] text-faint">loading…</div>}
            {items && items.length === 0 && (
              <div className="px-3 py-6 text-center text-[11.5px] text-muted">
                No notifications yet.
                <div className="text-[10.5px] text-faint mt-1">Invitations, collaborator activity and account alerts will appear here.</div>
              </div>
            )}
            {items?.map((n) => (
              <div
                key={n.id}
                role="button"
                tabIndex={0}
                onClick={() => openItem(n)}
                onKeyDown={(e) => e.key === "Enter" && openItem(n)}
                className={`flex items-start gap-2.5 px-3 py-2 border-b border-divider last:border-b-0 cursor-pointer hover:bg-brand/[0.05] ${n.read ? "" : "bg-brand/[0.04]"}`}
              >
                <span className={`mt-0.5 w-4 text-center text-[12px] ${n.read ? "text-faint" : "text-brand"}`} aria-hidden>{GLYPH[n.type] || "•"}</span>
                <span className="min-w-0 flex-1">
                  <span className={`block text-[11.5px] leading-snug ${n.read ? "text-muted" : "text-ink"}`}>{n.title}</span>
                  {n.message && <span className="block text-[10.5px] text-faint leading-snug mt-0.5">{n.message}</span>}
                  <span className="block text-[10px] text-faint mt-1">{n.created}{n.link ? " · open →" : ""}</span>
                </span>
                <button
                  onClick={(e) => toggleRead(n, e)}
                  title={n.read ? "Mark unread" : "Mark read"}
                  aria-label={n.read ? "Mark unread" : "Mark read"}
                  className={`mt-1 w-2.5 h-2.5 flex-none border ${n.read ? "border-border" : "bg-brand border-brand"}`}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
