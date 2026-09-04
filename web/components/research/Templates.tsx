"use client";
import { useCallback, useEffect, useState } from "react";
import { Panel, Button } from "@/components/ui";
import { EmptyState, LoadingRows, ErrorState } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { ParamsForm, DesignParams, DEFAULT_PARAMS, paramsSummary } from "./ParamsForm";

export interface Template { id: number; name: string; description: string; params: DesignParams; created: string; updated: string }

export function Templates({ onUse }: { onUse?: (t: Template) => void }) {
  const [rows, setRows] = useState<Template[] | null>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<Partial<Template> | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setErr("");
    api.templates().then((r) => setRows(r.templates)).catch((e) => { setErr(e.message || "Could not load templates."); setRows([]); });
  }, []);
  useEffect(() => { load(); }, [load]);

  async function save() {
    if (!editing?.name?.trim()) return;
    setBusy(true); setErr("");
    try {
      if (editing.id) await api.updateTemplate(editing.id, { name: editing.name, description: editing.description || "", params: editing.params || {} });
      else await api.createTemplate(editing.name, editing.description || "", editing.params || DEFAULT_PARAMS);
      setEditing(null); load();
    } catch (e: any) { setErr(e.message || "Save failed."); } finally { setBusy(false); }
  }
  async function remove(t: Template) {
    if (!window.confirm(`Delete template "${t.name}"?`)) return;
    try { await api.deleteTemplate(t.id); load(); } catch (e: any) { setErr(e.message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <div className="text-[11.5px] text-muted flex-1">Save a validated configuration once, then apply it to new targets or batch runs. Templates never store sequences.</div>
        {!editing && <Button onClick={() => setEditing({ name: "", description: "", params: { ...DEFAULT_PARAMS } })}>New template</Button>}
      </div>
      {err && <ErrorState message={err} />}

      {editing && (
        <Panel title={editing.id ? "edit template" : "new template"}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
            <label className="block"><span className="label mb-1 block">Name</span>
              <input className="input" value={editing.name || ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })} placeholder="e.g. Therapeutic-grade SpCas9, low risk" /></label>
            <label className="block"><span className="label mb-1 block">Description</span>
              <input className="input" value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} placeholder="When to use it" /></label>
          </div>
          <ParamsForm value={editing.params || {}} onChange={(p) => setEditing({ ...editing, params: p })} />
          <div className="flex items-center gap-2 mt-3">
            <Button onClick={save} disabled={busy || !editing.name?.trim()}>{busy ? "Saving…" : "Save template"}</Button>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
          </div>
        </Panel>
      )}

      <Panel title="saved templates" meta={rows ? `${rows.length}` : ""} bodyClass="">
        {rows === null ? <LoadingRows /> : rows.length === 0 ? (
          <EmptyState title="No templates yet." body="Create one to reuse a nuclease / outcome / risk configuration across targets." />
        ) : (
          <table className="dtable">
            <thead><tr><th>name</th><th>configuration</th><th>updated</th><th /></tr></thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td><div className="text-ink">{t.name}</div>{t.description && <div className="text-[10.5px] text-faint">{t.description}</div>}</td>
                  <td className="text-muted">{paramsSummary(t.params)}</td>
                  <td className="text-muted whitespace-nowrap">{t.updated}</td>
                  <td className="whitespace-nowrap text-right">
                    {onUse && <button onClick={() => onUse(t)} className="text-brand hover:underline mr-3">use in batch</button>}
                    <button onClick={() => setEditing({ ...t })} className="text-muted hover:text-ink mr-3">edit</button>
                    <button onClick={() => remove(t)} className="text-faint hover:text-bad">delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
