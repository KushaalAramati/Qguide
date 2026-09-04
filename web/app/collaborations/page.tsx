"use client";
// Collaborations — projects shared with me, and my projects that I have shared.
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Shell } from "@/components/Shell";
import { Panel } from "@/components/ui";
import { PageHeader, EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api, ProjectMeta, projectHref } from "@/lib/api";
import { BRANDING } from "@/lib/branding";

export default function CollaborationsPage() {
  return <Shell><Collab /></Shell>;
}

function Collab() {
  const [rows, setRows] = useState<ProjectMeta[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setErr("");
    api.projects().then(setRows).catch((e) => { setErr(e.message || "Could not load projects."); setRows([]); });
  }, []);
  useEffect(() => { load(); }, [load]);

  const shared = (rows || []).filter((p) => p.shared);
  const mine = (rows || []).filter((p) => !p.shared && (p.n_collaborators || 0) > 0);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="team"
        title="Collaborations"
        description={`Projects other ${BRANDING.APP_NAME} researchers have shared with you, and the projects you have shared. Sharing is per project — open one and use Share to manage access.`}
      />
      {err && <ErrorState message={err} retry={load} />}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
        <Panel title="shared with me" meta={rows ? `${shared.length}` : ""} bodyClass="">
          {rows === null ? <LoadingRows n={4} /> : shared.length === 0 ? (
            <EmptyState
              title="Nothing shared with you yet."
              body="When a project owner adds you as a viewer or editor it will appear here, and you will get a notification."
            />
          ) : (
            <table className="dtable">
              <thead><tr><th>project</th><th>owner</th><th>your role</th><th>guides</th><th>created</th></tr></thead>
              <tbody>
                {shared.map((p) => (
                  <tr key={p.uid || p.id}>
                    <td><Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link></td>
                    <td className="text-muted">{p.owner_name || p.owner_email}</td>
                    <td><span className={p.role === "EDITOR" ? "tag-good" : "tag-warn"}>{p.role.toLowerCase()}</span></td>
                    <td className="tabular-nums">{p.n_guides ?? "—"}</td>
                    <td className="text-muted whitespace-nowrap">{p.created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="shared by me" meta={rows ? `${mine.length}` : ""} bodyClass="">
          {rows === null ? <LoadingRows n={4} /> : mine.length === 0 ? (
            <EmptyState
              title="You have not shared any projects."
              body="Open a project and choose Share to invite a registered user by email as a viewer or editor."
              action={<Link href="/projects" className="btn-ghost text-[12px]">Go to projects</Link>}
            />
          ) : (
            <table className="dtable">
              <thead><tr><th>project</th><th>collaborators</th><th>guides</th><th>created</th></tr></thead>
              <tbody>
                {mine.map((p) => (
                  <tr key={p.id}>
                    <td><Link href={projectHref(p)} className="text-brand hover:underline">{p.name}</Link><span className="ml-2 text-faint text-[10.5px]">{p.id}</span></td>
                    <td className="tabular-nums">{p.n_collaborators}</td>
                    <td className="tabular-nums">{p.n_guides ?? "—"}</td>
                    <td className="text-muted whitespace-nowrap">{p.created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <Panel title="how access works">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[11.5px]">
          <div><div className="tag-good mb-1">owner</div><div className="text-muted">Full access. Invites and removes collaborators, changes their permission, organises the project in folders, deletes it.</div></div>
          <div><div className="tag-good mb-1">editor</div><div className="text-muted">Opens the project, renames it, saves the selected guide and re-runs the analysis in place (using their own credits).</div></div>
          <div><div className="tag-warn mb-1">viewer</div><div className="text-muted">Read-only: explores every view and exports results, but cannot change anything.</div></div>
        </div>
        <div className="text-[10.5px] text-faint mt-3">Access is checked by the server on every request; a project link only works for people on the project.</div>
      </Panel>
    </div>
  );
}
