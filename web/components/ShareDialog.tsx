"use client";
import { useEffect, useRef, useState } from "react";
import { api, ProjectMember, ProjectAccess } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BRANDING } from "@/lib/branding";

/**
 * Share / Manage access dialog.
 *
 * Owners invite registered users by email (exact match, with a live lookup so
 * a typo is caught before "Send invite"), change roles and remove people.
 * Collaborators see the same list read-only and can leave. Every action here
 * is re-checked by the server; the dialog just mirrors `access.can_share`.
 */
export function ShareDialog({
  projectId, projectName, access, members, onMembers, onClose, onLeft,
}: {
  projectId: string; projectName: string; access: ProjectAccess;
  members: ProjectMember[]; onMembers: (m: ProjectMember[]) => void;
  onClose: () => void; onLeft?: () => void;
}) {
  const { account } = useAuth();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"EDITOR" | "VIEWER">("VIEWER");
  const [lookup, setLookup] = useState<{ found: boolean; user: any } | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const canShare = access.can_share;

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Debounced exact-match lookup as the owner types.
  useEffect(() => {
    setLookup(null);
    const v = email.trim().toLowerCase();
    if (!canShare || !/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(v)) return;
    const t = setTimeout(() => {
      api.lookupUser(v).then(setLookup).catch(() => setLookup(null));
    }, 350);
    return () => clearTimeout(t);
  }, [email, canShare]);

  async function run(key: string, fn: () => Promise<any>, done: string) {
    setBusy(key); setErr(""); setOk("");
    try {
      const res = await fn();
      if (res?.members) onMembers(res.members);
      setOk(done);
    } catch (e: any) {
      setErr(e.message || "Something went wrong.");
    } finally {
      setBusy("");
    }
  }

  const invite = () =>
    run("invite", () => api.inviteMember(projectId, email.trim(), role), `Shared with ${email.trim()} as ${role.toLowerCase()}.`)
      .then(() => { setEmail(""); setLookup(null); });

  const alreadyMember = members.find((m) => m.email === email.trim().toLowerCase());

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/45" role="dialog" aria-modal aria-labelledby="share-title" onClick={onClose}>
      <div className="w-full max-w-lg bg-surface border border-border" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <span>{canShare ? "share project" : "project access"}</span>
          <span className="meta truncate max-w-[50%]" title={projectName}>{projectName}</span>
          <button onClick={onClose} aria-label="Close" className="ml-2 text-faint hover:text-ink">✕</button>
        </div>

        {canShare && (
          <div className="p-4 border-b border-border">
            <div className="label mb-1.5">invite a collaborator</div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                ref={inputRef}
                className="input flex-1"
                type="email"
                placeholder="researcher@example.org"
                aria-label="Collaborator email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErr(""); setOk(""); }}
                onKeyDown={(e) => e.key === "Enter" && lookup?.found && !alreadyMember && invite()}
              />
              <select
                className="border border-border bg-well px-2 py-1.5 text-[12px] text-ink outline-none focus:border-brand"
                value={role}
                aria-label="Permission"
                onChange={(e) => setRole(e.target.value as any)}
              >
                <option value="VIEWER">Viewer</option>
                <option value="EDITOR">Editor</option>
              </select>
              <button
                onClick={invite}
                disabled={busy === "invite" || !email.trim() || !lookup?.found || !!alreadyMember}
                className="btn-primary text-[12px] whitespace-nowrap"
              >
                {busy === "invite" ? "Sending…" : alreadyMember ? "Already added" : "Send invite"}
              </button>
            </div>
            <div className="text-[10.5px] mt-1.5 min-h-[14px]">
              {lookup?.found && !alreadyMember && (
                <span className="text-brand">✓ {lookup.user.name}{lookup.user.institution ? ` · ${lookup.user.institution}` : ""} — registered {BRANDING.APP_NAME} user</span>
              )}
              {lookup && !lookup.found && (
                <span className="text-warn">No {BRANDING.APP_NAME} account for that address yet. They need to sign up before you can invite them.</span>
              )}
              {!lookup && (
                <span className="text-faint">
                  Viewers can open and export the project. Editors can also rename it, save a selected guide and re-run the analysis.
                </span>
              )}
            </div>
          </div>
        )}

        <div className="p-4">
          <div className="flex items-center mb-2">
            <span className="label">people with access</span>
            <span className="ml-auto text-[10.5px] text-faint">{members.length}</span>
          </div>
          <ul className="divide-y divide-divider">
            {members.map((m) => {
              const me = m.email === account?.email;
              const isOwner = m.role === "OWNER";
              return (
                <li key={m.email} className="flex items-center gap-3 py-2 text-[11.5px]">
                  <span className="w-[22px] h-[22px] flex-none grid place-items-center border border-border bg-well text-[10.5px] text-muted">
                    {m.name?.[0]?.toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-ink truncate">{m.name}{me && <span className="text-faint"> (you)</span>}</span>
                    <span className="block text-[10.5px] text-faint truncate">{m.email}</span>
                  </span>
                  {isOwner ? (
                    <span className="tag-good">owner</span>
                  ) : canShare ? (
                    <>
                      <select
                        value={m.role}
                        disabled={busy === m.email}
                        aria-label={`Role for ${m.email}`}
                        onChange={(e) => run(m.email, () => api.setMemberRole(projectId, m.email, e.target.value as any), `${m.name} is now ${e.target.value.toLowerCase()}.`)}
                        className="border border-border bg-well px-1.5 py-0.5 text-[11px] text-ink outline-none focus:border-brand"
                      >
                        <option value="VIEWER">Viewer</option>
                        <option value="EDITOR">Editor</option>
                      </select>
                      <button
                        disabled={busy === m.email}
                        onClick={() => window.confirm(`Remove ${m.name} from "${projectName}"?`) && run(m.email, () => api.removeMember(projectId, m.email), `${m.name} removed.`)}
                        className="text-faint hover:text-bad text-[12px]"
                        title="Remove access"
                        aria-label={`Remove ${m.email}`}
                      >✕</button>
                    </>
                  ) : (
                    <span className="text-muted">{m.role.toLowerCase()}</span>
                  )}
                </li>
              );
            })}
          </ul>
          {members.length <= 1 && canShare && (
            <div className="text-[11px] text-faint mt-2">No collaborators yet — invite someone above.</div>
          )}

          {(err || ok) && (
            <div className={`mt-3 text-[11.5px] ${err ? "text-bad" : "text-brand"}`} role="status">{err || ok}</div>
          )}

          {!access.is_owner && (
            <div className="mt-4 pt-3 border-t border-divider flex items-center gap-3">
              <span className="text-[11px] text-faint flex-1">You have {access.role.toLowerCase()} access, granted by the owner.</span>
              <button
                disabled={busy === "leave"}
                onClick={() => {
                  if (!account || !window.confirm(`Leave "${projectName}"? You will lose access until the owner re-invites you.`)) return;
                  run("leave", () => api.removeMember(projectId, account.email), "Left project.").then(() => onLeft?.());
                }}
                className="btn-ghost text-[11.5px]"
              >
                Leave project
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
