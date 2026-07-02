"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { Card, CardTitle, Button } from "@/components/ui";
import { Dna } from "@/components/Dna";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const EXAMPLE =
  "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT" +
  "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC" +
  "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG";

const STEPS = ["Input sequence", "Generate candidates", "Score guides", "Run optimization", "Review results"];

function Stepper({ active }: { active: number }) {
  return (
    <div className="flex items-center my-2">
      {STEPS.map((s, i) => {
        const n = i + 1;
        const state = n < active ? "done" : n === active ? "active" : "todo";
        return (
          <div key={s} className="flex items-center">
            <div className="flex items-center gap-2">
              <div className={`w-7 h-7 rounded-full grid place-items-center text-sm font-extrabold border-2
                ${state === "active" ? "bg-brand border-brand text-white" :
                  state === "done" ? "bg-brand-light border-brand-light text-brand-dark" :
                  "bg-white border-border text-muted"}`}>{state === "done" ? "✓" : n}</div>
              <div className={`text-sm font-bold ${state === "todo" ? "text-muted" : "text-ink"} whitespace-nowrap`}>{s}</div>
            </div>
            {i < STEPS.length - 1 && <div className="h-0.5 bg-border w-6 mx-2" />}
          </div>
        );
      })}
    </div>
  );
}

export default function NewProject() {
  return <Shell><NewForm /></Shell>;
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3">{children}</div>;
}

function NewForm() {
  const router = useRouter();
  const { account, refresh } = useAuth();
  const [enzymes, setEnzymes] = useState<string[]>(["SpCas9"]);
  const [seq, setSeq] = useState(EXAMPLE);
  const [gene, setGene] = useState("DEMO1");
  const [cas, setCas] = useState("SpCas9");
  const [organism, setOrganism] = useState("human");
  const [outcome, setOutcome] = useState("knockout");
  const [cell, setCell] = useState("");
  const [delivery, setDelivery] = useState("");
  const [temp, setTemp] = useState(37);
  const [setSize, setSetSize] = useState(3);
  const [risk, setRisk] = useState("balanced");
  const [optMode, setOptMode] = useState("classical");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { api.enzymes().then((e) => setEnzymes(Object.keys(e))).catch(() => {}); }, []);

  const seqLen = seq.replace(/[^ACGTNacgtn]/g, "").length;
  const credits = account?.credits ?? 0;
  const canRun = credits >= 5;

  async function run() {
    setErr(""); setBusy(true);
    try {
      const res = await api.run({
        sequence: seq, gene_name: gene || null, cas_enzyme: cas, organism,
        desired_outcome: outcome, cell_type: cell || null, delivery_method: delivery || null,
        temperature: temp, set_size: setSize, risk_tolerance: risk, optimizer_mode: optMode,
      });
      await refresh();
      router.push(`/project/${res.project_id}`);
    } catch (e: any) {
      setErr(e.status === 402 ? "Insufficient credits — buy more to run." : (e.message || "Run failed."));
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="font-display font-extrabold text-3xl">New Project</div>
      <div className="text-muted font-medium">Configure a CRISPR design run, review the summary, then run the pipeline.</div>
      <Dna width={1000} height={64} turns={6} />
      <Stepper active={1} />

      <div className="grid grid-cols-[2.3fr_1fr] gap-5 mt-2">
        <div className="flex flex-col gap-4">
          <Card>
            <CardTitle>🧬 Sequence Input</CardTitle>
            <textarea className="input font-mono text-sm h-36" value={seq} onChange={(e) => setSeq(e.target.value)} />
            <div className="mt-3"><div className="label mb-1">Project / gene name</div>
              <input className="input" value={gene} onChange={(e) => setGene(e.target.value)} /></div>
          </Card>

          <Card>
            <CardTitle>⚙️ CRISPR System</CardTitle>
            <Row>
              <div><div className="label mb-1">Cas enzyme</div>
                <select className="input" value={cas} onChange={(e) => setCas(e.target.value)}>
                  {enzymes.map((x) => <option key={x}>{x}</option>)}</select></div>
              <div><div className="label mb-1">Organism</div>
                <select className="input" value={organism} onChange={(e) => setOrganism(e.target.value)}>
                  {["human", "mouse", "zebrafish", "yeast", "e_coli"].map((x) => <option key={x}>{x}</option>)}</select></div>
            </Row>
          </Card>

          <Card>
            <CardTitle>🧪 Experimental Context</CardTitle>
            <Row>
              <div><div className="label mb-1">Desired outcome</div>
                <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                  {["knockout", "precise_edit", "base_edit", "prime_edit", "crispri", "crispra", "screen", "gene_disruption", "exon_targeting", "deletion", "custom"].map((x) => <option key={x}>{x}</option>)}</select></div>
              <div><div className="label mb-1">Cell type (optional)</div>
                <select className="input" value={cell} onChange={(e) => setCell(e.target.value)}>
                  {["", "stem_cell", "neuron", "hek293", "primary_t", "cancer_line"].map((x) => <option key={x} value={x}>{x || "—"}</option>)}</select></div>
            </Row>
            <div className="mt-3"><Row>
              <div><div className="label mb-1">Delivery (optional)</div>
                <select className="input" value={delivery} onChange={(e) => setDelivery(e.target.value)}>
                  {["", "rnp", "plasmid", "lentivirus", "aav", "electroporation"].map((x) => <option key={x} value={x}>{x || "—"}</option>)}</select></div>
              <div><div className="label mb-1">Temperature °C</div>
                <input className="input" type="number" value={temp} onChange={(e) => setTemp(parseFloat(e.target.value))} /></div>
            </Row></div>
          </Card>

          <Card>
            <CardTitle>🎯 Optimization Settings</CardTitle>
            <div className="label mb-1">Optimized set size (N): {setSize}</div>
            <input type="range" min={1} max={6} value={setSize} onChange={(e) => setSetSize(parseInt(e.target.value))} className="w-full accent-brand" />
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div><div className="label mb-1">Risk tolerance</div>
                <select className="input" value={risk} onChange={(e) => setRisk(e.target.value)}>
                  {["low", "balanced", "high"].map((x) => <option key={x}>{x}</option>)}</select></div>
              <div><div className="label mb-1">Optimizer</div>
                <select className="input" value={optMode} onChange={(e) => setOptMode(e.target.value)}>
                  <option value="classical">Classical (annealing)</option>
                  <option value="quantum_inspired">Quantum-inspired (QUBO)</option>
                  <option value="quantum_hardware">Quantum hardware (experimental)</option>
                </select></div>
            </div>
            <div className="text-xs text-muted mt-2">Quantum-inspired optimization searches guide
              combinations. Biological scoring stays classical bioinformatics/ML — quantum does
              not change prediction accuracy.</div>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardTitle>📋 Project Summary</CardTitle>
            {[["Project", gene || "—"], ["Sequence length", `${seqLen} bp`], ["Cas enzyme", cas],
              ["Organism", organism], ["Desired outcome", outcome], ["Guide set size", String(setSize)]].map(([k, v]) => (
              <div key={k} className="flex justify-between py-1.5 border-b border-dashed border-border text-sm last:border-0">
                <span className="text-muted font-semibold">{k}</span><span className="font-bold">{v}</span></div>
            ))}
          </Card>
          <Card>
            <div className="text-sm text-muted">💎 This run costs <b className="text-ink">5 credits</b> · balance <b className="text-ink">{credits}</b></div>
            {err && <div className="text-bad text-sm font-semibold mt-2">{err}</div>}
            <div className="mt-3">
              {canRun ? (
                <Button onClick={run} disabled={busy} full>{busy ? "Running…" : "🚀 Run Optimization"}</Button>
              ) : (
                <Button onClick={() => router.push("/buy")} full>💳 Buy Credits</Button>
              )}
            </div>
          </Card>
          <Card>
            <CardTitle>Input requirements</CardTitle>
            <div className="text-sm text-muted">• DNA only (A/C/G/T/N)<br />• ≥ ~25 bp so PAMs have room<br />• FASTA headers ignored<br />• Pick a Cas enzyme + outcome</div>
          </Card>
        </div>
      </div>
    </div>
  );
}
