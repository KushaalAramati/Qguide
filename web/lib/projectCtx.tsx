"use client";
// Shared project data + selected-guide state for all /project/[id]/* pages,
// fetched once in the layout so each feature page reads from context.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { useParams } from "next/navigation";
import { api, ProjectAccess, ProjectMember } from "@/lib/api";
import { cleanSeq } from "@/lib/dna";

export interface ProjectCtx {
  id: string; proj: any; resp: any; req: any; opt: any;
  guides: any[]; byId: Record<string, any>; fullSeq: string;
  err: string; loading: boolean;
  sel: string; setSel: (s: string) => void; g: any;
  access: ProjectAccess | null; members: ProjectMember[];
  reload: () => Promise<void>;
  setMembers: (m: ProjectMember[]) => void;
}
const Ctx = createContext<ProjectCtx | null>(null);

export function useProject(): ProjectCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useProject must be used within ProjectProvider");
  return c;
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const [proj, setProj] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState("");

  const reload = useCallback(async () => {
    try {
      const p = await api.project(id);
      setProj(p);
      setSel((cur) => cur || p.selected_guide || p.response.guides[0]?.guide_id);
      setErr("");
    } catch (e: any) {
      setErr(e.status === 404
        ? "This project does not exist or you do not have access to it."
        : e.message || "Failed to load project.");
    }
  }, [id]);

  useEffect(() => {
    setProj(null); setErr(""); setSel("");
    reload();
  }, [id, reload]);

  const setMembers = useCallback((members: ProjectMember[]) => {
    setProj((p: any) => (p ? { ...p, members } : p));
  }, []);

  const value = useMemo<ProjectCtx>(() => {
    const resp = proj?.response;
    const guides = resp?.guides ?? [];
    const byId: Record<string, any> = Object.fromEntries(guides.map((x: any) => [x.guide_id, x]));
    return {
      id, proj, resp, req: resp?.request, opt: resp?.optimized_set,
      guides, byId, fullSeq: resp?.request ? cleanSeq(resp.request.sequence) : "",
      err, loading: !proj && !err, sel, setSel, g: byId[sel] || guides[0],
      access: proj?.access ?? null, members: proj?.members ?? [], reload, setMembers,
    };
  }, [proj, err, sel, id, reload, setMembers]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
