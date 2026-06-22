"""
Step 2 -- Biological scoring.

Each scoring component is a small pure function `(Guide) -> float in [0,1]`,
registered in `COMPONENTS`. To replace a component (e.g. swap the heuristic
GC term for a learned model) you register a new callable under the same key --
nothing else in the pipeline changes.

Penalty components return *higher = worse*; everything else returns *higher = better*.
The composite `on_target` score is assembled from the components with explicit
weights so the contribution of each term is fully transparent (Step 10).
"""
from __future__ import annotations

import math
from typing import Callable, Dict

from qguide.app.schemas import Guide

ScoreFn = Callable[[Guide], float]


# --------------------------------------------------------------------------- #
# Individual components                                                         #
# --------------------------------------------------------------------------- #
def gc_content_score(guide: Guide) -> float:
    """Triangular preference centred on 50% GC (40-60% is the sweet spot)."""
    gc = guide.gc_content
    return max(0.0, 1.0 - abs(gc - 0.5) / 0.5)


def pam_score(guide: Guide) -> float:
    """SpCas9 prefers an extended NGG; a 3rd G (NGGG-like context proxy) helps.

    Heuristic: reward canonical GG, lightly penalise non-canonical PAMs.
    """
    pam = guide.pam.upper()
    if pam.endswith("GG"):
        return 1.0
    if pam.endswith("AG"):
        return 0.6          # NAG is a weak SpCas9 PAM
    return 0.4


def complexity_score(guide: Guide) -> float:
    """Shannon entropy of the spacer, normalised to [0,1] (max entropy = 2 bits)."""
    seq = guide.sequence
    if not seq:
        return 0.0
    counts = {b: seq.count(b) for b in set(seq)}
    n = len(seq)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return min(1.0, entropy / 2.0)


def homopolymer_penalty(guide: Guide) -> float:
    """Penalty for runs of the same base (esp. poly-T which terminates Pol-III)."""
    seq = guide.sequence
    longest = _longest_run(seq)
    poly_t = "TTTT" in seq
    penalty = 0.0
    if longest >= 4:
        penalty += min(1.0, (longest - 3) * 0.25)
    if poly_t:
        penalty = min(1.0, penalty + 0.3)
    return penalty


def secondary_structure_penalty(guide: Guide) -> float:
    """Cheap proxy for self-folding: count complementary k-mer palindromic pairs.

    A real implementation would call ViennaRNA; this heuristic estimates how much
    the spacer can base-pair with itself, which impairs sgRNA folding/loading.
    """
    seq = guide.sequence
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    k = 4
    if len(seq) < 2 * k:
        return 0.0
    kmers = [seq[i:i + k] for i in range(len(seq) - k + 1)]
    rc_set = set("".join(comp.get(b, "N") for b in km[::-1]) for km in kmers)
    pairs = sum(1 for km in kmers if km in rc_set)
    return min(1.0, pairs / (2.0 * len(kmers)))


def distance_to_target_score(guide: Guide) -> float:
    """Exponential decay with distance from the target centre (~50 bp scale)."""
    return math.exp(-guide.distance_to_target / 50.0)


def sequence_quality_score(guide: Guide) -> float:
    """Composite 'is this a clean, well-behaved spacer' term.

    Combines absence of N, avoidance of extreme GC and absence of long runs.
    """
    seq = guide.sequence
    if not seq or "N" in seq:
        return 0.0
    gc = guide.gc_content
    gc_ok = 1.0 if 0.30 <= gc <= 0.80 else 0.5
    run_ok = 1.0 if _longest_run(seq) < 5 else 0.5
    return gc_ok * run_ok


# Registry -- swap any entry to replace a component without touching the pipeline.
COMPONENTS: Dict[str, ScoreFn] = {
    "gc_content": gc_content_score,
    "pam": pam_score,
    "complexity": complexity_score,
    "homopolymer_penalty": homopolymer_penalty,
    "secondary_structure_penalty": secondary_structure_penalty,
    "distance_to_target": distance_to_target_score,
    "sequence_quality": sequence_quality_score,
}

# Weights for assembling the composite on-target score. Penalties subtract.
ON_TARGET_WEIGHTS = {
    "gc_content": 0.20,
    "pam": 0.20,
    "complexity": 0.15,
    "distance_to_target": 0.15,
    "sequence_quality": 0.30,
    "homopolymer_penalty": -0.25,
    "secondary_structure_penalty": -0.20,
}


def score_guide(guide: Guide) -> Guide:
    """Populate `guide.scores` (mutates and returns the guide)."""
    values = {name: fn(guide) for name, fn in COMPONENTS.items()}

    raw = sum(ON_TARGET_WEIGHTS[name] * values[name] for name in ON_TARGET_WEIGHTS)
    pos_weight = sum(w for w in ON_TARGET_WEIGHTS.values() if w > 0)
    on_target = max(0.0, min(1.0, raw / pos_weight))

    guide.scores.gc_content = values["gc_content"]
    guide.scores.pam = values["pam"]
    guide.scores.complexity = values["complexity"]
    guide.scores.homopolymer_penalty = values["homopolymer_penalty"]
    guide.scores.secondary_structure_penalty = values["secondary_structure_penalty"]
    guide.scores.distance_to_target = values["distance_to_target"]
    guide.scores.sequence_quality = values["sequence_quality"]
    guide.scores.on_target = on_target

    if values["homopolymer_penalty"] >= 0.5:
        guide.warnings.append("Long homopolymer run may reduce expression/cutting.")
    if "TTTT" in guide.sequence:
        guide.warnings.append("Poly-T tract can prematurely terminate Pol-III transcription.")
    return guide


def score_guides(guides):
    return [score_guide(g) for g in guides]


# --------------------------------------------------------------------------- #
def _longest_run(seq: str) -> int:
    best = run = 0
    prev = ""
    for b in seq:
        run = run + 1 if b == prev else 1
        best = max(best, run)
        prev = b
    return best
