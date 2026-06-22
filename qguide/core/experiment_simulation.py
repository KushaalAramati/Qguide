"""
Experiment outcome simulation.

Turns a single guide's predicted per-allele probabilities into a *predicted
experimental result*: a Monte-Carlo over a virtual diploid cell population that
estimates editing efficiency, biallelic-knockout rate (with a confidence band
from replicate-to-replicate biological variability), the genotype distribution
(WT / heterozygous / biallelic KO), and a plausible indel-size spectrum.

This works for ANY guide -- including the lowest-ranked one -- so a user can ask
"what would actually happen if I used this guide?" and get an answer with
uncertainty, not just a single number.

IMPORTANT: this predicts what the (rule-based V1) model expects, with simulated
biological noise. It is illustrative, not wet-lab-validated. Swapping the upstream
`OutcomeModel` for a trained predictor makes these results data-driven with no
change here.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from qguide.app.schemas import Guide


def _stable_seed(guide: Guide) -> int:
    """Deterministic per-guide seed so a given guide reproduces its prediction."""
    return (sum(ord(c) for c in guide.sequence) * 2654435761) & 0xFFFFFFFF


def _microhomology(seq: str) -> float:
    """Cheap MMEJ proxy in [0,1]: complementary flanks -> predictable deletions."""
    if len(seq) < 8:
        return 0.0
    left, right = seq[:len(seq) // 2], seq[len(seq) // 2:]
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    rc_right = "".join(comp.get(b, "N") for b in right[::-1])
    matches = sum(1 for a, b in zip(left[::-1], rc_right) if a == b)
    return min(1.0, matches / (len(seq) / 2.0))


def _indel_spectrum(seq: str) -> Dict[str, List]:
    """Synthesise an NHEJ/MMEJ indel-size distribution among EDITED alleles.

    Shape follows published priors: a dominant +1 bp insertion, a tail of small
    deletions, and a microhomology-driven deletion peak whose size scales with
    the spacer's internal complementarity.
    """
    sizes = list(range(-10, 4))               # -10 .. +3 bp
    mh = _microhomology(seq)
    weights = []
    mh_peak = -(3 + int(round(mh * 5)))       # MH pushes a larger predictable deletion
    for s in sizes:
        if s == 1:                            # +1 insertion: NHEJ signature
            w = 0.30
        elif s == 0:
            w = 0.0
        elif s > 0:                           # other insertions
            w = 0.05
        else:                                 # deletions: decay with size
            w = 0.16 * np.exp(s / 4.0)
        if s == mh_peak:                      # microhomology deletion bump
            w += 0.20 * mh
        weights.append(max(w, 0.0))
    total = sum(weights) or 1.0
    return {"sizes": sizes, "fraction": [round(w / total, 4) for w in weights]}


def simulate_experiment(
    guide: Guide,
    n_cells: int = 5000,
    replicates: int = 300,
    bio_cv: float = 0.12,
) -> Dict[str, object]:
    """Predict the experimental result of using `guide`.

    n_cells     -- diploid cells per simulated replicate dish
    replicates  -- independent replicate dishes (gives the confidence band)
    bio_cv      -- coefficient of variation of editing efficiency between replicates
    """
    o = guide.outcome
    p_fs, p_if, p_ne = o.frameshift_prob, o.in_frame_indel_prob, o.no_edit_prob
    s = (p_fs + p_if + p_ne) or 1.0
    p_fs, p_if, p_ne = p_fs / s, p_if / s, p_ne / s

    # Per-allele loss-of-function probability (mirrors the outcome model's KO defn).
    p_disrupt = p_fs + 0.20 * p_if
    p_allele_edit = 1.0 - p_ne

    rng = np.random.default_rng(_stable_seed(guide))

    # Replicate-to-replicate biological variability in editing efficiency.
    eff = np.clip(rng.normal(1.0, bio_cv, replicates), 0.3, 1.7)
    p_d_rep = np.clip(p_disrupt * eff, 0.0, 1.0)
    p_ed_rep = np.clip(p_allele_edit * eff, 0.0, 1.0)

    # Diploid cell-level probabilities per replicate.
    p_ko_cell = p_d_rep ** 2                       # both alleles disrupted
    p_edit_cell = 1.0 - (1.0 - p_ed_rep) ** 2      # >=1 allele edited

    ko_rate = rng.binomial(n_cells, p_ko_cell) / n_cells
    edit_rate = rng.binomial(n_cells, p_edit_cell) / n_cells

    def band(arr):
        lo, hi = np.percentile(arr, [2.5, 97.5])
        return {"mean": round(float(arr.mean()), 4),
                "ci_low": round(float(lo), 4),
                "ci_high": round(float(hi), 4),
                "std": round(float(arr.std()), 4)}

    # Mean genotype distribution (Hardy-Weinberg-style on disruption prob).
    pd_ = p_disrupt
    genotypes = {
        "wild_type": round((1 - pd_) ** 2, 4),
        "heterozygous": round(2 * pd_ * (1 - pd_), 4),
        "biallelic_ko": round(pd_ ** 2, 4),
    }

    ko = band(ko_rate)
    edit = band(edit_rate)
    verdict = _verdict(edit["mean"], ko["mean"])

    return {
        "guide_id": guide.guide_id,
        "sequence": guide.sequence,
        "n_cells": n_cells,
        "replicates": replicates,
        "editing_efficiency": edit,
        "knockout_rate": ko,
        "allele_outcomes": {"frameshift": round(p_fs, 4),
                            "in_frame_indel": round(p_if, 4),
                            "no_edit": round(p_ne, 4)},
        "genotypes": genotypes,
        "indel_spectrum": _indel_spectrum(guide.sequence),
        "ko_distribution": [round(float(x), 4) for x in ko_rate],
        "verdict": verdict,
        "model": "monte_carlo_v1 (rule-based outcome priors; not wet-lab validated)",
    }


def _verdict(edit_mean: float, ko_mean: float) -> str:
    if ko_mean >= 0.50:
        grade = "strong knockout — most cells biallelically disrupted"
    elif ko_mean >= 0.25:
        grade = "moderate knockout — a usable but mixed population"
    elif ko_mean >= 0.10:
        grade = "weak knockout — many cells retain a functional allele"
    else:
        grade = "poor knockout — the population stays largely wild-type"
    return (f"Predicted {edit_mean:.0%} of cells edited, {ko_mean:.0%} biallelic "
            f"knockout: {grade}.")


def compare_experiments(guides: List[Guide], **kw) -> List[Dict[str, object]]:
    """Predict results for several guides (e.g. best vs worst) for side-by-side."""
    out = []
    for g in guides:
        r = simulate_experiment(g, **kw)
        out.append({"guide_id": g.guide_id,
                    "edit_mean": r["editing_efficiency"]["mean"],
                    "ko_mean": r["knockout_rate"]["mean"],
                    "ko_ci_low": r["knockout_rate"]["ci_low"],
                    "ko_ci_high": r["knockout_rate"]["ci_high"],
                    "verdict": r["verdict"]})
    return out
