"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** Design parameters shared by templates and batch runs (never the sequence). */
export interface DesignParams {
  cas_enzyme?: string; organism?: string; desired_outcome?: string; cell_type?: string;
  delivery_method?: string; temperature?: number; risk_tolerance?: string; set_size?: number;
  optimizer_mode?: string; optimizer_preset?: string;
}

export const DEFAULT_PARAMS: DesignParams = {
  cas_enzyme: "SpCas9", organism: "human", desired_outcome: "knockout", risk_tolerance: "balanced",
  set_size: 3, optimizer_mode: "classical",
};

export const OUTCOMES = ["knockout", "precise_edit", "base_edit", "prime_edit", "crispri", "crispra", "screen", "gene_disruption", "exon_targeting", "deletion", "custom"];
export const ORGANISMS = ["human", "mouse", "zebrafish", "yeast", "e_coli"];
export const CELLS = ["", "stem_cell", "neuron", "hek293", "primary_t", "cancer_line"];
export const DELIVERY = ["", "rnp", "plasmid", "lentivirus", "aav", "electroporation"];

export function ParamsForm({ value, onChange, compact = false }: { value: DesignParams; onChange: (p: DesignParams) => void; compact?: boolean }) {
  const [enzymes, setEnzymes] = useState<string[]>(["SpCas9"]);
  useEffect(() => { api.enzymes().then((e) => setEnzymes(Object.keys(e))).catch(() => {}); }, []);
  const set = (k: keyof DesignParams, v: any) => onChange({ ...value, [k]: v === "" ? undefined : v });
  const Sel = ({ k, label, opts }: { k: keyof DesignParams; label: string; opts: string[] }) => (
    <label className="block">
      <span className="label mb-1 block">{label}</span>
      <select className="input" value={(value[k] as string) ?? ""} onChange={(e) => set(k, e.target.value)}>
        {opts.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </label>
  );
  return (
    <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-4"}`}>
      <Sel k="cas_enzyme" label="Cas enzyme" opts={enzymes} />
      <Sel k="organism" label="Organism" opts={ORGANISMS} />
      <Sel k="desired_outcome" label="Desired outcome" opts={OUTCOMES} />
      <Sel k="risk_tolerance" label="Risk tolerance" opts={["low", "balanced", "high"]} />
      <Sel k="cell_type" label="Cell type" opts={CELLS} />
      <Sel k="delivery_method" label="Delivery" opts={DELIVERY} />
      <label className="block"><span className="label mb-1 block">Set size</span>
        <input type="number" min={1} max={6} className="input" value={value.set_size ?? 3} onChange={(e) => set("set_size", parseInt(e.target.value) || 3)} /></label>
      <label className="block"><span className="label mb-1 block">Optimizer</span>
        <select className="input" value={value.optimizer_mode ?? "classical"} onChange={(e) => set("optimizer_mode", e.target.value)}>
          <option value="classical">Classical (annealing)</option>
          <option value="quantum_inspired">Quantum-inspired (QUBO)</option>
          <option value="quantum_hardware">Quantum hardware (experimental)</option>
        </select></label>
    </div>
  );
}

export function paramsSummary(p: DesignParams) {
  return [p.cas_enzyme, p.organism, p.desired_outcome, p.risk_tolerance && `${p.risk_tolerance} risk`, p.set_size && `set ${p.set_size}`, p.optimizer_mode?.replace("_", " ")]
    .filter(Boolean).join(" · ");
}
