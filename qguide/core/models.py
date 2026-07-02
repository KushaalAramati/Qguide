"""
Model-adapter layer (Stage A).

A registry of *named* scoring models sitting behind one clean interface, so real
trained / genome-aligned models can be dropped in later without touching the pipeline.

SCIENTIFIC HONESTY (Part 12 of the product brief):
  - Every adapter declares its ``kind``:
        REAL        deterministic computation we stand behind (not ML, but exact)
        HEURISTIC   interpretable heuristic, honestly labelled as such
        PROVISIONAL a placeholder for a real model that is NOT yet wired in
  - Unavailable external ML models ABSTAIN: ``available=False`` and ``score() -> None``.
    They are never given a fabricated number and are never disguised as a validated
    ML prediction. The ensemble computes agreement only over models that actually ran.

This is exactly what the brief asks for: "If a model is unavailable: create a clean
adapter/interface, label the score as provisional, do not disguise heuristic output as a
validated ML prediction."
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Callable, Dict, List, Optional

from qguide.app.schemas import Guide

# --- kinds ------------------------------------------------------------------ #
REAL = "real"
HEURISTIC = "heuristic"
PROVISIONAL = "provisional"

# --- tasks ------------------------------------------------------------------ #
ON_TARGET = "on_target"
SPECIFICITY = "specificity"
REPAIR = "repair"


@dataclass(frozen=True)
class ModelSpec:
    """One named model behind the common interface."""
    name: str
    task: str
    kind: str
    available: bool
    citation: str = ""
    note: str = ""
    fn: Optional[Callable[[Guide], float]] = None

    def score(self, guide: Guide) -> Optional[float]:
        """Return a 0..1 score, or ``None`` if this model is unavailable (abstains)."""
        if not self.available or self.fn is None:
            return None
        try:
            return max(0.0, min(1.0, float(self.fn(guide))))
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Available adapters (honest heuristics / deterministic computations)          #
# --------------------------------------------------------------------------- #
def _qguide_on_target(g: Guide) -> float:
    """The transparent QGuide composite on-target score (already computed in scoring.py)."""
    return g.scores.on_target


def _positional_on_target(g: Guide) -> float:
    """A *different*, transparent positional-preference heuristic for spacer activity.

    Deliberately independent of the QGuide composite so that agreement/disagreement
    between the two carries real information. Preferences are Rule-Set-*style* (G
    enrichment near the PAM, moderate seed GC, poly-T disfavoured) but are hand-set,
    interpretable weights -- NOT the published Azimuth/Rule Set 2 coefficients.
    """
    s = (g.sequence or "").upper()
    if not s:
        return 0.0
    score = 0.5
    prox = s[-4:]                       # PAM-proximal 4 nt
    score += 0.05 * prox.count("G")     # G near PAM tends to help SpCas9 activity
    score -= 0.04 * prox.count("T")
    seed = s[-8:]                        # seed region GC, moderate is best
    gc = (seed.count("G") + seed.count("C")) / max(1, len(seed))
    score += 0.15 * (1.0 - abs(gc - 0.55) / 0.55)
    if "TTTT" in s:                      # Pol-III terminator
        score -= 0.15
    return max(0.0, min(1.0, score))


def _qguide_specificity(g: Guide) -> float:
    """Heuristic specificity = 1 - aggregate heuristic off-target risk (no genome)."""
    return max(0.0, min(1.0, 1.0 - g.off_target.risk_score))


def _qguide_repair(g: Guide) -> float:
    """Heuristic repair-outcome proxy from the rule-based outcome model."""
    return max(0.0, min(1.0, g.outcome.functional_disruption_score))


# --------------------------------------------------------------------------- #
# Registry                                                                      #
# --------------------------------------------------------------------------- #
# NOTE: the external ML models below are declared but NOT installed. They abstain
# (available=False, score()->None) until real weights / a service / a genome index
# are wired in through this same interface.
ON_TARGET_MODELS: List[ModelSpec] = [
    ModelSpec("QGuide-OT (composite)", ON_TARGET, HEURISTIC, True,
              citation="QGuide internal", note="Transparent weighted composite of GC/PAM/complexity/quality minus penalties.",
              fn=_qguide_on_target),
    ModelSpec("Positional-preference", ON_TARGET, HEURISTIC, True,
              citation="QGuide internal", note="Independent positional heuristic; illustrative weights, not published coefficients.",
              fn=_positional_on_target),
    ModelSpec("Azimuth / Rule Set 2", ON_TARGET, PROVISIONAL, False,
              citation="Doench et al. 2016", note="Requires the Azimuth boosted-model weights; not installed."),
    ModelSpec("Rule Set 3", ON_TARGET, PROVISIONAL, False,
              citation="DeWeirdt et al. 2022", note="Requires model weights/service; not installed."),
    ModelSpec("CRISPRon", ON_TARGET, PROVISIONAL, False,
              citation="Xiang et al. 2021", note="Requires the CRISPRon deep model; not installed."),
    ModelSpec("DeepSpCas9", ON_TARGET, PROVISIONAL, False,
              citation="Kim et al. 2019", note="Requires the DeepSpCas9 weights; not installed."),
]

SPECIFICITY_MODELS: List[ModelSpec] = [
    ModelSpec("QGuide-Spec (heuristic)", SPECIFICITY, HEURISTIC, True,
              citation="QGuide internal", note="1 - aggregate heuristic off-target risk (no genome alignment).",
              fn=_qguide_specificity),
    ModelSpec("CFD (genome)", SPECIFICITY, PROVISIONAL, False,
              citation="Doench et al. 2016", note="Requires genome-wide off-target enumeration + CFD matrix; not installed."),
    ModelSpec("MIT specificity", SPECIFICITY, PROVISIONAL, False,
              citation="Hsu et al. 2013", note="Requires genome-wide off-target sites; not installed."),
]

REPAIR_MODELS: List[ModelSpec] = [
    ModelSpec("QGuide-Repair (rule-based)", REPAIR, HEURISTIC, True,
              citation="QGuide internal", note="Rule-based NHEJ outcome proxy (frameshift/functional disruption).",
              fn=_qguide_repair),
    ModelSpec("inDelphi", REPAIR, PROVISIONAL, False,
              citation="Shen et al. 2018", note="Requires the inDelphi model; not installed."),
    ModelSpec("Lindel", REPAIR, PROVISIONAL, False,
              citation="Chen et al. 2019", note="Requires the Lindel model; not installed."),
    ModelSpec("FORECasT", REPAIR, PROVISIONAL, False,
              citation="Allen et al. 2019", note="Requires the FORECasT model; not installed."),
]

ALL_MODELS: List[ModelSpec] = ON_TARGET_MODELS + SPECIFICITY_MODELS + REPAIR_MODELS


def model_report(guide: Guide) -> List[Dict]:
    """Per-model rows for a guide (serialisable dicts for the API/UI)."""
    rows: List[Dict] = []
    for spec in ALL_MODELS:
        sc = spec.score(guide)
        rows.append({
            "name": spec.name,
            "task": spec.task,
            "kind": spec.kind,
            "available": spec.available,
            "score": None if sc is None else round(sc, 4),
            "citation": spec.citation,
            "note": spec.note,
        })
    return rows


def _available_scores(guide: Guide, task: str) -> List[float]:
    return [s for m in ALL_MODELS if m.task == task and (s := m.score(guide)) is not None]


def on_target_agreement(guide: Guide) -> Optional[float]:
    """Real agreement across *available* on-target models: 1 - normalised spread.

    Returns ``None`` when fewer than two models actually produced a score (so the
    ensemble can fall back and flag lower confidence instead of inventing agreement).
    """
    vals = _available_scores(guide, ON_TARGET)
    if len(vals) < 2:
        return None
    return max(0.0, min(1.0, 1.0 - 2.0 * pstdev(vals)))


def disagreements(guide: Guide, threshold: float = 0.2) -> List[str]:
    """Human-readable notes where two available on-target models disagree materially."""
    scored = [(m.name, m.score(guide)) for m in ON_TARGET_MODELS]
    scored = [(n, s) for n, s in scored if s is not None]
    out: List[str] = []
    for i in range(len(scored)):
        for j in range(i + 1, len(scored)):
            (na, sa), (nb, sb) = scored[i], scored[j]
            if abs(sa - sb) >= threshold:
                out.append(f"{na} ({sa:.2f}) vs {nb} ({sb:.2f}) differ by {abs(sa - sb):.2f}")
    return out


def limitations(guide: Guide) -> List[str]:
    """Honest limitations: which named models are unavailable and why it matters."""
    unavailable = [m.name for m in ALL_MODELS if not m.available]
    out: List[str] = []
    if unavailable:
        out.append("Validated ML models not installed (scores abstain): " + ", ".join(unavailable) + ".")
    out.append("Specificity/off-target is heuristic — no genome alignment or real CFD.")
    if on_target_agreement(guide) is None:
        out.append("Only one on-target model available, so cross-model agreement is not meaningful.")
    return out
