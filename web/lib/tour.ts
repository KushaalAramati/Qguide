import { BRANDING } from "@/lib/branding";

/**
 * First-run walkthrough content. Pure data so the steps can be edited without
 * touching the tour component, and so Settings/Help can list them.
 */
export interface TourStep {
  title: string;
  body: string;
  /** Optional deep link offered as "Open …" on the step. */
  link?: { href: string; label: string };
  /** Sidebar entry to highlight while this step is shown. */
  highlight?: string;
  caveat?: string;
}

export const TOUR_STEPS: TourStep[] = [
  {
    title: `Welcome to ${BRANDING.APP_NAME}`,
    body: `${BRANDING.APP_NAME} designs and ranks CRISPR guide RNAs around the outcome you want — not just where the nuclease can cut. This short tour shows where things are. You can skip it now and replay it any time from Settings.`,
  },
  {
    title: "Your dashboard",
    body: "The dashboard summarises your projects, analyses and credits, and always offers the next sensible action. The sidebar on the left is your map: Dashboard, Projects, New Analysis, Billing and Settings. Collapse it with the « control when you want more room — it remembers your choice.",
    highlight: "/dashboard",
    link: { href: "/dashboard", label: "Open dashboard" },
  },
  {
    title: "Create a CRISPR project",
    body: "A project is one design run. Start from New Analysis, paste the target DNA sequence (FASTA headers are fine) and give the project a name — usually the gene. Each run costs a few credits and is saved automatically.",
    highlight: "/new",
    link: { href: "/new", label: "Open New Analysis" },
  },
  {
    title: "Choose organism, nuclease and experiment type",
    body: "Pick the Cas enzyme (this sets the PAM and guide length), the organism, and the outcome you are after — knockout, precise edit, base or prime editing, CRISPRi/a and more. Cell type, delivery method and temperature are optional but they change the context-aware scores.",
    highlight: "/new",
  },
  {
    title: "Guide RNA generation",
    body: "The pipeline scans both strands for PAM sites, extracts every candidate protospacer, and filters out guides with poor GC content, homopolymer runs or low complexity. What remains is scored individually, then combined into an optimised set.",
  },
  {
    title: "Understanding guide scores",
    body: "Every guide carries an on-target efficiency, an off-target risk, an outcome probability and a Precision Score that blends them with your risk tolerance. Each score is labelled with its provenance — real, heuristic or provisional — and the Ensemble view explains which components pushed a guide up or down.",
    caveat: "Scores are interpretable estimates, not wet-lab measurements. Treat a top rank as a hypothesis to validate.",
  },
  {
    title: "Off-target analysis",
    body: "The off-target report lists the highest-risk mismatch sites and a severity per hit, using a sequence-based heuristic calibrated to published GUIDE-seq behaviour. It does not perform a genome-wide alignment, so a low risk is a reason to test — not proof of specificity.",
    caveat: "Confirm candidate guides with a genome-wide method (GUIDE-seq, CIRCLE-seq, amplicon sequencing) before committing resources.",
  },
  {
    title: "Quantum-enhanced set optimisation",
    body: "Choosing the best set of guides is a combinatorial problem. The optimiser formulates it as a QUBO and solves it with classical annealing, a quantum-inspired sampler, or quantum hardware when configured. The Compare view shows how each strategy differs from simply taking the top N.",
    caveat: "Quantum methods change how guides are combined, not how accurate individual scores are.",
  },
  {
    title: "Saving and organising projects",
    body: "Runs are saved the moment they finish. The Projects page lists everything you own; use folders and subfolders to organise by gene, cell line or experiment, archive finished work, and rename or move projects from the ⋯ menu.",
    highlight: "/projects",
    link: { href: "/projects", label: "Open Projects" },
  },
  {
    title: "Collaborating with researchers",
    body: `Projects can be shared with other registered ${BRANDING.APP_NAME} users as viewers or editors from the project's Share control. Owners manage access; editors can re-run and annotate; viewers read only. Invitations show up in the bell at the top of the screen.`,
  },
  {
    title: "Exporting results",
    body: "From any project, Export results gives you the ranked guide table as CSV for spreadsheets or a full JSON bundle with inputs, every guide, the optimised set and provenance — enough to reproduce or cite the analysis. That is the tour; you can replay it from Settings › Onboarding.",
  },
];
