"""
Step 3 -- Off-target analysis.

V1 is a *heuristic* estimator: with no genome index available it infers off-target
risk from intrinsic properties of the spacer that correlate with promiscuity --
low sequence complexity, repetitive motifs, and a "seed" region (PAM-proximal
~10 nt) that is itself repetitive. It also synthesises a plausible mismatch
distribution so the dashboards have something concrete to render.

Extensibility: `OffTargetEngine` is an interface. Drop in a `BowtieEngine`,
`BlastEngine`, or `CrisporEngine` that returns the same `OffTargetReport` and the
rest of Q-Guide is unchanged.
"""
from __future__ import annotations

import math
from typing import List, Protocol

from qguide.app.schemas import (
    Guide,
    MismatchBin,
    OffTargetHit,
    OffTargetReport,
    RiskCategory,
)


class OffTargetEngine(Protocol):
    """Replaceable off-target backend (heuristic now, alignment-based later)."""
    def analyze(self, guide: Guide) -> OffTargetReport: ...


class GenomeAlignmentOffTargetEngine:
    """Interface for the real, genome-backed engine (Stage 4 / future).

    A production implementation would: build/load a genome index (BWA/Bowtie),
    enumerate near-matches with mismatches and bulges, filter by PAM, score each
    site with CFD/MIT, and annotate exon/promoter/enhancer/conserved overlap. Until
    an index is configured it returns a clear "not available" report rather than
    pretending — no fake genome hits.
    """

    method = "genome_alignment_v0"

    def __init__(self, genome_index_path: str | None = None):
        self.genome_index_path = genome_index_path

    def available(self) -> bool:
        return bool(self.genome_index_path)

    def analyze(self, guide: Guide) -> OffTargetReport:
        if not self.available():
            return OffTargetReport(
                genome_backed=False,
                warning=("Genome-backed off-target analysis requires a reference "
                         "genome index (BWA/Bowtie). None is configured, so no "
                         "genome-wide off-target search was performed."),
                method=self.method,
            )
        raise NotImplementedError(
            "Genome alignment backend not yet implemented — configure an aligner + index.")


def categorize(risk: float) -> RiskCategory:
    """Single source of truth for risk-score -> category thresholds."""
    if risk < 0.25:
        return RiskCategory.LOW
    if risk < 0.55:
        return RiskCategory.MODERATE
    return RiskCategory.HIGH


def _seed_repetitiveness(seq: str) -> float:
    """Fraction of repeated dinucleotides in the PAM-proximal seed (last 10 nt)."""
    seed = seq[-10:] if len(seq) >= 10 else seq
    if len(seed) < 2:
        return 0.0
    dinucs = [seed[i:i + 2] for i in range(len(seed) - 1)]
    unique = len(set(dinucs))
    return 1.0 - unique / len(dinucs)


def _low_complexity(seq: str) -> float:
    """1 - normalised entropy. High value = low complexity = more off-targets."""
    if not seq:
        return 1.0
    counts = {b: seq.count(b) for b in set(seq)}
    n = len(seq)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return 1.0 - min(1.0, entropy / 2.0)


def _repetitive_motifs(seq: str) -> float:
    """Detect tandem/short-period repeats that proliferate across a genome."""
    score = 0.0
    for period in (1, 2, 3):
        runs = _max_tandem_run(seq, period)
        if runs >= 3:
            score = max(score, min(1.0, (runs - 2) * 0.25))
    return score


class HeuristicOffTargetEngine:
    """Default V1 engine -- no external dependencies."""

    method = "heuristic_v1"

    def analyze(self, guide: Guide) -> OffTargetReport:
        seq = guide.sequence
        seed = _seed_repetitiveness(seq)
        lowc = _low_complexity(seq)
        rep = _repetitive_motifs(seq)

        # Weighted blend -> 0 (safe) .. 1 (dangerous). Seed weighted highest
        # because PAM-proximal mismatches dominate SpCas9 specificity.
        risk = min(1.0, 0.45 * seed + 0.35 * lowc + 0.20 * rep)
        category = categorize(risk)

        # Synthesise a count + mismatch distribution from the risk magnitude.
        count = int(round(risk * 40))
        distribution = self._mismatch_distribution(count, risk)
        regions = self._concerning_regions(guide, count, risk)
        hits = self._hits(guide, count, risk)
        burden = round(sum(h.cfd_score for h in hits) + 0.02 * count, 4)

        report = OffTargetReport(
            risk_score=round(risk, 4),
            risk_category=category,
            potential_off_target_count=count,
            mismatch_distribution=distribution,
            concerning_regions=regions,
            hits=hits,
            aggregate_burden=burden,
            genome_backed=False,
            warning=("Off-target sites are HEURISTIC estimates from intrinsic sequence "
                     "features, not a genome search. Full genome-backed off-target "
                     "analysis (BWA/Bowtie alignment + CFD/MIT scoring) requires a "
                     "reference genome index, which is not configured."),
            method=self.method,
        )
        return report

    @staticmethod
    def _hits(guide: Guide, count: int, risk: float) -> List[OffTargetHit]:
        """Synthetic per-hit report (clearly provisional). A genome-backed engine
        would replace this with real aligned sites + CFD scores + annotations."""
        if count == 0:
            return []
        strand = guide.strand if isinstance(guide.strand, str) else guide.strand.value
        # Illustrative annotations, cycled so the UI has something to render.
        annos = ["intergenic", "intron", "promoter", "exon", "enhancer"]
        hits: List[OffTargetHit] = []
        n = min(4, max(1, count // 6 + 1))
        for i in range(n):
            mm = i + 1                                   # 1,2,3,... mismatches
            cfd = round(max(0.0, risk * (1.0 - 0.28 * mm)), 3)
            sev = categorize(cfd)
            anno = annos[(hash(guide.guide_id) + i) % len(annos)]
            # coding/regulatory hits are more concerning than intergenic
            if anno in ("exon", "promoter") and sev == RiskCategory.LOW:
                sev = RiskCategory.MODERATE
            L = len(guide.sequence)
            mmpos = sorted({(i * 7 + 3) % L, (i * 5 + 11) % L}) if mm >= 1 else []
            hits.append(OffTargetHit(
                locus=f"chr?:synthetic_{i+1}", position=-1, strand=strand,
                mismatches=mm, mismatch_positions=mmpos[:mm], pam=guide.pam,
                cfd_score=cfd, annotation=anno, severity=sev,
                explanation=(f"{mm}-mismatch candidate in a {anno} region; "
                             f"heuristic CFD-style score {cfd:.2f}."),
                provisional=True,
            ))
        return hits

    @staticmethod
    def _mismatch_distribution(count: int, risk: float) -> List[MismatchBin]:
        """More 0-2 mismatch hits when risk is high (those are the dangerous ones)."""
        if count == 0:
            return [MismatchBin(mismatches=m, count=0) for m in range(5)]
        # weight toward low mismatch counts as risk rises
        raw = [risk ** 0.5, risk, 1.0, 1.4, 1.7]
        total = sum(raw)
        return [
            MismatchBin(mismatches=m, count=int(round(count * w / total)))
            for m, w in enumerate(raw)
        ]

    @staticmethod
    def _concerning_regions(guide: Guide, count: int, risk: float) -> list:
        if count == 0:
            return []
        # Top synthetic hits: closer mismatches + nearby loci are more concerning.
        n = min(3, count)
        regions = []
        for i in range(n):
            mm = i  # 0,1,2 mismatches
            regions.append({
                "locus": f"chr?:synthetic_{guide.guide_id}_{i+1}",
                "mismatches": mm,
                "predicted_activity": round(max(0.0, risk * (1.0 - 0.3 * mm)), 3),
                "strand": guide.strand if isinstance(guide.strand, str) else guide.strand.value,
            })
        return regions


# Default singleton engine used by the pipeline.
DEFAULT_ENGINE: OffTargetEngine = HeuristicOffTargetEngine()


def analyze_off_target(guide: Guide, engine: OffTargetEngine = DEFAULT_ENGINE) -> Guide:
    guide.off_target = engine.analyze(guide)
    if guide.off_target.risk_category == RiskCategory.HIGH:
        guide.warnings.append("High predicted off-target risk -- validate empirically.")
    return guide


def analyze_off_targets(guides, engine: OffTargetEngine = DEFAULT_ENGINE):
    return [analyze_off_target(g, engine) for g in guides]


def scale_report(report: OffTargetReport, factor: float) -> OffTargetReport:
    """Apply a context multiplier (enzyme fidelity + organism) to an off-target
    report, keeping risk, category, count and the mismatch distribution consistent.

    factor < 1 (e.g. a high-fidelity Cas variant) lowers predicted risk; factor > 1
    (e.g. a promiscuity-prone organism context) raises it.
    """
    if factor == 1.0:
        return report
    new_risk = max(0.0, min(1.0, report.risk_score * factor))
    new_count = max(0, int(round(report.potential_off_target_count * factor)))
    dist = [MismatchBin(mismatches=b.mismatches,
                        count=max(0, int(round(b.count * factor))))
            for b in report.mismatch_distribution]
    regions = []
    for r in report.concerning_regions:
        r2 = dict(r)
        if "predicted_activity" in r2:
            try:
                r2["predicted_activity"] = round(min(1.0, float(r2["predicted_activity"]) * factor), 3)
            except (TypeError, ValueError):
                pass
        regions.append(r2)
    # Scale per-hit CFD scores + severities so the detailed report stays consistent.
    hits = []
    for h in report.hits:
        cfd = round(min(1.0, h.cfd_score * factor), 3)
        hits.append(h.model_copy(update={"cfd_score": cfd, "severity": categorize(cfd)}))
    return OffTargetReport(
        risk_score=round(new_risk, 4),
        risk_category=categorize(new_risk),
        potential_off_target_count=new_count,
        mismatch_distribution=dist,
        concerning_regions=regions,
        hits=hits,
        aggregate_burden=round(report.aggregate_burden * factor, 4),
        genome_backed=report.genome_backed,
        warning=report.warning,
        method=report.method + "+context",
    )


# --------------------------------------------------------------------------- #
def _max_tandem_run(seq: str, period: int) -> int:
    """Longest run of a repeated `period`-mer (e.g. period=2 -> 'ATATAT' = 3)."""
    best = 0
    for i in range(len(seq) - period):
        unit = seq[i:i + period]
        run = 1
        j = i + period
        while seq[j:j + period] == unit and j + period <= len(seq):
            run += 1
            j += period
        best = max(best, run)
    return best
