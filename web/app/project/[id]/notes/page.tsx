"use client";
// Experiment notes & metadata — the human annotations around a design run.
// Editors and owners can change it; viewers read it. Everything is saved to the
// project so collaborators and exports see the same record.
import { useEffect, useState } from "react";
import { Panel, Button } from "@/components/ui";
import { LoadingRows, ErrorState } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { useProject } from "@/lib/projectCtx";

type Citation = { label: string; url: string; doi: string };
interface Metadata {
  experiment_name: string | null; cell_line: string | null; target_gene: string | null;
  experiment_type: string | null; notes: string; tags: string[]; citations: Citation[];
  updated?: string | null; updated_by?: string | null;
}

export default function NotesPage() {
  const { id, req, access, members } = useProject();
  const canEdit = !!access?.can_edit;
  const [md, setMd] = useState<Metadata | null>(null);
  const [types, setTypes] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.projectMetadata(id)
      .then((r) => { setMd(r.metadata); setTypes(r.experiment_types); })
      .catch((e) => setErr(e.message || "Could not load notes."));
    api.researchTags().then((r) => setAllTags(r.tags)).catch(() => {});
  }, [id]);

  function set<K extends keyof Metadata>(k: K, v: Metadata[K]) {
    setMd((m) => (m ? { ...m, [k]: v } : m)); setDirty(true); setSaved("");
  }
  function addTag(t: string) {
    const v = t.trim().toLowerCase();
    if (!v || !md) return;
    if (!md.tags.includes(v)) set("tags", [...md.tags, v]);
    setTagInput("");
  }
  async function save() {
    if (!md) return;
    setBusy(true); setErr(""); setSaved("");
    try {
      const r = await api.patchProjectMetadata(id, {
        experiment_name: md.experiment_name || "", cell_line: md.cell_line || "", target_gene: md.target_gene || "",
        experiment_type: md.experiment_type || "", notes: md.notes, tags: md.tags, citations: md.citations,
      });
      setMd(r.metadata); setDirty(false); setSaved("Saved.");
    } catch (e: any) { setErr(e.message || "Save failed."); } finally { setBusy(false); }
  }

  if (err && !md) return <ErrorState message={err} />;
  if (!md) return <LoadingRows n={6} />;
  const owner = members.find((m) => m.role === "OWNER");
  const F = ({ label, k, placeholder }: { label: string; k: "experiment_name" | "cell_line" | "target_gene"; placeholder?: string }) => (
    <label className="block">
      <span className="label mb-1 block">{label}</span>
      <input className="input" value={md[k] || ""} placeholder={placeholder} disabled={!canEdit}
             onChange={(e) => set(k, e.target.value)} />
    </label>
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4 items-start">
      <div className="flex flex-col gap-4">
        <Panel title="experiment" meta={md.updated ? `updated ${md.updated} by ${md.updated_by}` : "not yet annotated"}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <F label="Experiment name" k="experiment_name" placeholder="e.g. BRCA1 knockout pilot" />
            <F label="Target gene" k="target_gene" placeholder={req?.gene_name || "e.g. BRCA1"} />
            <F label="Cell line" k="cell_line" placeholder="e.g. HEK293T" />
            <label className="block">
              <span className="label mb-1 block">Experiment type</span>
              <select className="input" value={md.experiment_type || ""} disabled={!canEdit} onChange={(e) => set("experiment_type", e.target.value)}>
                <option value="">—</option>
                {types.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-[11px]">
            {[["organism", req?.organism], ["nuclease", req?.cas_enzyme], ["outcome", req?.desired_outcome],
              ["created by", owner?.name || "—"]].map(([k, v]) => (
              <div key={k as string}><div className="label">{k}</div><div className="text-cell">{v as string}</div></div>
            ))}
          </div>
        </Panel>

        <Panel title="notes" meta={`${md.notes.length} chars`}>
          <textarea className="input h-48 font-prose text-[12.5px] leading-relaxed" value={md.notes} disabled={!canEdit}
                    placeholder="Protocol decisions, validation plans, observations…" onChange={(e) => set("notes", e.target.value)} />
        </Panel>
      </div>

      <div className="flex flex-col gap-4 lg:sticky lg:top-0">
        {canEdit && (
          <div className="flex items-center gap-3">
            <Button onClick={save} disabled={busy || !dirty}>{busy ? "Saving…" : "Save notes"}</Button>
            {saved && <span className="text-[11.5px] text-brand">{saved}</span>}
            {err && <span className="text-[11.5px] text-bad">{err}</span>}
            {dirty && !busy && <span className="text-[10.5px] text-faint">unsaved changes</span>}
          </div>
        )}
        {!canEdit && <div className="text-[10.5px] text-faint">Read-only — editors and the owner can annotate this project.</div>}

        <Panel title="tags" meta={`${md.tags.length}`}>
          <div className="flex flex-wrap gap-1.5 min-h-[22px]">
            {md.tags.map((t) => (
              <span key={t} className="tag-good font-normal flex items-center gap-1">
                {t}
                {canEdit && <button onClick={() => set("tags", md.tags.filter((x) => x !== t))} aria-label={`Remove tag ${t}`} className="hover:text-bad">✕</button>}
              </span>
            ))}
            {md.tags.length === 0 && <span className="text-[11px] text-faint">No tags yet.</span>}
          </div>
          {canEdit && (
            <div className="flex gap-2 mt-2">
              <input className="input" list="all-tags" value={tagInput} placeholder="add tag, press Enter"
                     onChange={(e) => setTagInput(e.target.value)}
                     onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(tagInput); } }} />
              <datalist id="all-tags">{allTags.map((t) => <option key={t} value={t} />)}</datalist>
              <button onClick={() => addTag(tagInput)} className="btn-ghost text-[12px]">Add</button>
            </div>
          )}
        </Panel>

        <Panel title="references" meta={`${md.citations.length}`}>
          {md.citations.length === 0 && <div className="text-[11px] text-faint mb-2">No references yet.</div>}
          <ul className="flex flex-col gap-2">
            {md.citations.map((c, i) => (
              <li key={i} className="flex items-start gap-2 text-[11.5px]">
                <span className="text-faint">{i + 1}.</span>
                <span className="min-w-0 flex-1">
                  {canEdit ? (
                    <span className="grid grid-cols-1 gap-1">
                      <input className="input !py-1" placeholder="Label (Author, Year)" value={c.label} onChange={(e) => set("citations", md.citations.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} />
                      <span className="grid grid-cols-2 gap-1">
                        <input className="input !py-1" placeholder="DOI" value={c.doi} onChange={(e) => set("citations", md.citations.map((x, j) => j === i ? { ...x, doi: e.target.value } : x))} />
                        <input className="input !py-1" placeholder="URL" value={c.url} onChange={(e) => set("citations", md.citations.map((x, j) => j === i ? { ...x, url: e.target.value } : x))} />
                      </span>
                    </span>
                  ) : (
                    <span>
                      <span className="text-ink">{c.label || c.doi || c.url}</span>
                      {c.doi && <a className="ml-2 text-brand hover:underline" href={`https://doi.org/${c.doi}`} target="_blank" rel="noreferrer">doi</a>}
                      {c.url && <a className="ml-2 text-brand hover:underline" href={c.url} target="_blank" rel="noreferrer">link</a>}
                    </span>
                  )}
                </span>
                {canEdit && <button onClick={() => set("citations", md.citations.filter((_, j) => j !== i))} aria-label="Remove reference" className="text-faint hover:text-bad">✕</button>}
              </li>
            ))}
          </ul>
          {canEdit && <button onClick={() => set("citations", [...md.citations, { label: "", url: "", doi: "" }])} className="btn-ghost text-[11.5px] mt-2">＋ Add reference</button>}
        </Panel>
      </div>
    </div>
  );
}
