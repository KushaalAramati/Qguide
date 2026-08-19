"""
Biological-context annotation layer (formula-upgrade brief, Part 2).

Most guide-RNA tools score a spacer from its sequence alone. QGuide wants to fold in
deeper biological variables -- exon importance, protein-domain disruption, transcript-
isoform coverage, conservation, variant/SNP conflict, chromatin accessibility and how
well the scoring model matches the user's cell type.

The honest problem: this repository has NO gene model, NO genome, NO variant database
and NO chromatin track. So the design mirrors ``off_target.GenomeAlignmentOffTargetEngine``:

  * ``AnnotationProvider`` is a clean interface.
  * The DEFAULT providers only populate fields they can DEFENSIBLY derive; every other
    field stays ``None`` (unknown). A ``None`` field is dropped from the Precision Score
    and instead *lowers confidence* -- QGuide never fabricates annotation it does not have.
  * Each populated field carries a ``source`` label: ``real`` (computed from inputs we
    trust), ``proxy`` (a clearly-labelled positional/heuristic stand-in) or ``unknown``.

Drop a real ``EnsemblAnnotationProvider`` / ``GencodeAnnotationProvider`` /
``dbSNPVariantProvider`` behind this interface later and the Precision Score, QUBO and
explanations all light up automatically -- nothing downstream changes.
"""
from __future__ import annotations

import math
from typing import List, Optional, Protocol

from qguide.app.schemas import BiologicalContext, DesignRequest, Guide


class AnnotationProvider(Protocol):
    """Replaceable biological-annotation backend."""
    name: str
    def annotate(self, guide: Guide, request: DesignRequest) -> BiologicalContext: ...


# --------------------------------------------------------------------------- #
# Null provider -- the fully honest default when nothing is configured         #
# --------------------------------------------------------------------------- #
class NullAnnotationProvider:
    """Populates nothing. Every biological-context field abstains (unknown).

    This is the maximally-honest baseline: with no gene model / variant DB / chromatin
    data, the Precision Score simply carries higher uncertainty. Use it when you want
    zero proxies in the score.
    """

    name = "null_v0"

    def annotate(self, guide: Guide, request: DesignRequest) -> BiologicalContext:
        fields = ["exon_importance", "domain_disruption", "transcript_coverage",
                  "conservation", "variant_conflict_risk", "chromatin_accessibility",
                  "cell_context_confidence"]
        return BiologicalContext(
            provider=self.name,
            available=False,
            sources={f: "unknown" for f in fields},
            notes=["No annotation source configured — all biological-context variables "
                   "are unknown and only lower confidence (never fabricated)."],
        )


# --------------------------------------------------------------------------- #
# Positional-proxy provider -- fills ONLY what it can honestly derive           #
# --------------------------------------------------------------------------- #
class PositionalProxyAnnotationProvider:
    """Derives the subset of biological-context variables that can be defended from the
    inputs we actually have (guide geometry + the request), and leaves the rest unknown.

    Honestly populated:
      * ``cell_context_confidence`` -- REAL: derived from whether a cell type was given
        and the fact that NO cell-type-specific model is installed.
      * ``exon_importance`` -- PROXY: proximity to the specified/implied target region
        (a positional stand-in, explicitly NOT true exon-rank annotation).

    Left UNKNOWN (need a real data source, so they abstain):
      * ``domain_disruption`` (protein-domain annotation)
      * ``transcript_coverage`` (isoform models)
      * ``conservation`` (phyloP/phastCons track)
      * ``variant_conflict_risk`` (dbSNP/gnomAD)
      * ``chromatin_accessibility`` (ATAC/DNase for the cell type)
    """

    name = "positional_proxy_v0"

    def annotate(self, guide: Guide, request: DesignRequest) -> BiologicalContext:
        sources: dict = {}
        notes: List[str] = []

        # --- cell_context_confidence (REAL, from request + known model coverage) --- #
        cell = getattr(request, "cell_type", None)
        if cell:
            cell_conf: Optional[float] = 0.5
            notes.append(f"cell_context_confidence: cell type '{cell}' provided, but no "
                         "cell-type-specific model is installed — generic model used "
                         "(medium confidence).")
        else:
            cell_conf = 0.2
            notes.append("cell_context_confidence: no cell type provided — low "
                         "context confidence.")
        sources["cell_context_confidence"] = "real"

        # --- exon_importance (PROXY: proximity to the target region) --------------- #
        prox = getattr(guide.scores, "distance_to_target", None)
        if not prox:  # scoring may not have run; fall back to the raw bp distance
            prox = math.exp(-abs(getattr(guide, "distance_to_target", 0)) / 50.0)
        exon_importance: Optional[float] = max(0.0, min(1.0, float(prox)))
        sources["exon_importance"] = "proxy"
        notes.append("exon_importance: POSITIONAL PROXY (proximity to the target "
                     "region) — not true exon-rank/constitutive-exon annotation.")

        # --- everything else: honestly unknown ------------------------------------ #
        for f in ("domain_disruption", "transcript_coverage", "conservation",
                  "variant_conflict_risk", "chromatin_accessibility"):
            sources[f] = "unknown"
        notes.append("domain_disruption, transcript_coverage, conservation, "
                     "variant_conflict_risk and chromatin_accessibility are UNKNOWN "
                     "(no gene model / variant DB / chromatin track) and abstain from "
                     "the score.")

        return BiologicalContext(
            exon_importance=exon_importance,
            domain_disruption=None,
            transcript_coverage=None,
            conservation=None,
            variant_conflict_risk=None,
            chromatin_accessibility=None,
            cell_context_confidence=cell_conf,
            sources=sources,
            notes=notes,
            provider=self.name,
            available=True,
        )


# Pipeline default: partial honest proxies (so the Precision Score is meaningful in a
# demo) while never fabricating domain/variant/chromatin annotation. Swap to
# NullAnnotationProvider() for a zero-proxy run.
DEFAULT_PROVIDER: AnnotationProvider = PositionalProxyAnnotationProvider()


def annotate_guide(guide: Guide, request: DesignRequest,
                   provider: AnnotationProvider = DEFAULT_PROVIDER) -> Guide:
    guide.bio_context = provider.annotate(guide, request)
    return guide


def annotate_guides(guides: List[Guide], request: DesignRequest,
                    provider: AnnotationProvider = DEFAULT_PROVIDER) -> List[Guide]:
    for g in guides:
        annotate_guide(g, request, provider)
    return guides
