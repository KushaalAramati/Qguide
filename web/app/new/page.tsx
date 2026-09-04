"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/Shell";
import { Panel, Button } from "@/components/ui";
import { PageHeader } from "@/components/PageHeader";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const EXAMPLE =
  "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT" +
  "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC" +
  "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG";

const STEPS = ["Input sequence", "Generate candidates", "Score guides", "Run optimization", "Review results"];

function Stepper({ active }: { active: number }) {
  return (
    <ol className="flex items-center flex-wrap gap-y-1 text-[11px]" aria-label="Design workflow">
      {STEPS.map((st, i) => {
        const n = i + 1;
        const state = n < active ? "done" : n === active ? "active" : "todo";
        return (
          <li key={st} className="flex items-center">
            <span className={`w-5 h-5 grid place-items-center border text-[10px] tabular-nums ${
              state === "active" ? "bg-brand border-brand text-bg" :
              state === "done" ? "border-brand text-brand" : "border-border text-faint"}`}>
              {state === "done" ? "✓" : n}
            </span>
            <span className={`ml-1.5 whitespace-nowrap ${state === "active" ? "text-ink" : "text-faint"}`}>{st}</span>
            {i < STEPS.length - 1 && <span className="h-px w-5 bg-border mx-2.5" aria-hidden />}
          </li>
        );
      })}
    </ol>
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

  const Field = ({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) => (
    <label className="block">
      <span className="label mb-1 block">{label}</span>
      {children}
      {hint && <span className="block text-[10.5px] text-faint mt-1">{hint}</span>}
    </label>
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="design"
        title="New analysis"
        description="Paste a target sequence, choose the nuclease and experimental context, then run the pipeline. One run creates one project."
        primary={
          canRun
            ? <Button onClick={run} disabled={busy || seqLen < 25}>{busy ? "Running analysis…" : "Run analysis"}</Button>
            : <Button onClick={() => router.push("/buy")}>Add credits to run</Button>
        }
        actions={<span className="text-[11px] text-faint">5 credits · balance {credits}</span>}
      >
        <Stepper active={1} />
      </PageHeader>

      <div className="grid grid-cols-1 lg:grid-cols-[2.2fr_1fr] gap-4 items-start">
        <div className="flex flex-col gap-4">
          <Panel title="1 · target sequence" meta={`${seqLen} bp`}>
            <textarea
              className="input seqtext text-[12px] h-36"
              value={seq}
              onChange={(e) => setSeq(e.target.value)}
              aria-label="Target DNA sequence"
              spellCheck={false}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <Field label="Project / gene name" hint="Used as the project title.">
                <input className="input" value={gene} onChange={(e) => setGene(e.target.value)} />
              </Field>
              <div className="text-[10.5px] text-faint self-end pb-1">
                DNA only (A/C/G/T/N) · at least ~25 bp so PAMs have room · FASTA headers are ignored.
              </div>
            </div>
          </Panel>

          <Panel title="2 · crispr system">
            <Row>
              <Field label="Cas enzyme">
                <select className="input" value={cas} onChange={(e) => setCas(e.target.value)}>
                  {enzymes.map((x) => <option key={x}>{x}</option>)}</select>
              </Field>
              <Field label="Organism">
                <select className="input" value={organism} onChange={(e) => setOrganism(e.target.value)}>
                  {["human", "mouse", "zebrafish", "yeast", "e_coli"].map((x) => <option key={x}>{x}</option>)}</select>
              </Field>
            </Row>
          </Panel>

          <Panel title="3 · experimental context">
            <Row>
              <Field label="Desired outcome">
                <select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                  {["knockout", "precise_edit", "base_edit", "prime_edit", "crispri", "crispra", "screen", "gene_disruption", "exon_targeting", "deletion", "custom"].map((x) => <option key={x}>{x}</option>)}</select>
              </Field>
              <Field label="Cell type (optional)">
                <select className="input" value={cell} onChange={(e) => setCell(e.target.value)}>
                  {["", "stem_cell", "neuron", "hek293", "primary_t", "cancer_line"].map((x) => <option key={x} value={x}>{x || "—"}</option>)}</select>
              </Field>
            </Row>
            <div className="mt-3"><Row>
              <Field label="Delivery (optional)">
                <select className="input" value={delivery} onChange={(e) => setDelivery(e.target.value)}>
                  {["", "rnp", "plasmid", "lentivirus", "aav", "electroporation"].map((x) => <option key={x} value={x}>{x || "—"}</option>)}</select>
              </Field>
              <Field label="Temperature °C">
                <input className="input" type="number" value={temp} onChange={(e) => setTemp(parseFloat(e.target.value))} />
              </Field>
            </Row></div>
          </Panel>

          <Panel title="4 · optimisation">
            <Field label={`Optimised set size (N): ${setSize}`}>
              <input type="range" min={1} max={6} value={setSize} onChange={(e) => setSetSize(parseInt(e.target.value))} className="w-full accent-brand" />
            </Field>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <Field label="Risk tolerance">
                <select className="input" value={risk} onChange={(e) => setRisk(e.target.value)}>
                  {["low", "balanced", "high"].map((x) => <option key={x}>{x}</option>)}</select>
              </Field>
              <Field label="Optimizer">
                <select className="input" value={optMode} onChange={(e) => setOptMode(e.target.value)}>
                  <option value="classical">Classical (annealing)</option>
                  <option value="quantum_inspired">Quantum-inspired (QUBO)</option>
                  <option value="quantum_hardware">Quantum hardware (experimental)</option>
                </select>
              </Field>
            </div>
            <div className="caveat mt-3 -mx-3 -mb-3">
              Quantum-inspired optimisation searches guide <em>combinations</em>. Biological scoring stays
              classical — the optimizer does not change prediction accuracy.
            </div>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 lg:sticky lg:top-0">
          <Panel title="run summary">
            {[["Project", gene || "—"], ["Sequence length", `${seqLen} bp`], ["Cas enzyme", cas],
              ["Organism", organism], ["Desired outcome", outcome], ["Guide set size", String(setSize)],
              ["Optimizer", optMode.replace("_", " ")]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 py-1.5 border-b border-divider text-[11.5px] last:border-0">
                <span className="text-faint">{k}</span><span className="text-ink text-right truncate">{v}</span></div>
            ))}
            <div className="mt-3 pt-3 border-t border-border">
              <div className="text-[11px] text-muted mb-2">
                This run costs <b className="text-ink font-medium">5 credits</b> · balance <b className={`font-medium ${canRun ? "text-ink" : "text-bad"}`}>{credits}</b>
              </div>
              {err && <div role="alert" className="border border-bad/40 bg-bad/[0.06] text-bad text-[11.5px] px-2.5 py-2 mb-2">{err}</div>}
              {canRun ? (
                <Button onClick={run} disabled={busy || seqLen < 25} full>{busy ? "Running analysis…" : "Run analysis"}</Button>
              ) : (
                <Button onClick={() => router.push("/buy")} full>Add credits to run</Button>
              )}
              {seqLen < 25 && <div className="text-[10.5px] text-warn mt-1.5">Sequence is too short — paste at least ~25 bp.</div>}
            </div>
          </Panel>
          <Panel title="what you get">
            <ul className="text-[11px] text-muted leading-relaxed list-none flex flex-col gap-1">
              <li>› Ranked candidate guides with on-target, off-target and outcome scores</li>
              <li>› An optimised guide <em>set</em> for your set size and risk tolerance</li>
              <li>› Plain-language explanations of why each guide ranks where it does</li>
              <li>› CSV / JSON export from the project page</li>
            </ul>
            <div className="caveat mt-3 -mx-3 -mb-3">Scores are computational estimates for research use — validate experimentally.</div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
