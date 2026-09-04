"""Tests for the biological-context annotation layer (Part 2, honest abstain)."""
from qguide.app.schemas import DesignRequest
from qguide.core import biological_context as bc, guide_generator, scoring

_SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC")


def _guides():
    gs = guide_generator.generate_guides(_SEQ, max_guides=10)
    scoring.score_guides(gs)
    return gs


def test_null_provider_abstains_everywhere():
    gs = _guides()
    bc.annotate_guides(gs, DesignRequest(sequence=_SEQ),
                       provider=bc.NullAnnotationProvider())
    c = gs[0].bio_context
    assert c.available is False
    assert all(getattr(c, f) is None for f in
               ("exon_importance", "domain_disruption", "transcript_coverage",
                "conservation", "variant_conflict_risk", "chromatin_accessibility",
                "cell_context_confidence"))
    assert all(v == "unknown" for v in c.sources.values())


def test_proxy_provider_fills_only_defensible_fields():
    gs = _guides()
    bc.annotate_guides(gs, DesignRequest(sequence=_SEQ, cell_type="neuron"))
    c = gs[0].bio_context
    assert c.available is True
    # honestly derivable:
    assert c.cell_context_confidence is not None and c.sources["cell_context_confidence"] == "real"
    assert c.exon_importance is not None and c.sources["exon_importance"] == "proxy"
    # genuinely unknown -> abstain:
    for f in ("domain_disruption", "transcript_coverage", "conservation",
              "variant_conflict_risk", "chromatin_accessibility"):
        assert getattr(c, f) is None and c.sources[f] == "unknown"


def test_cell_type_raises_context_confidence():
    gs = _guides()
    with_cell = bc.PositionalProxyAnnotationProvider().annotate(
        gs[0], DesignRequest(sequence=_SEQ, cell_type="hek293"))
    no_cell = bc.PositionalProxyAnnotationProvider().annotate(
        gs[0], DesignRequest(sequence=_SEQ))
    assert with_cell.cell_context_confidence > no_cell.cell_context_confidence


def test_exon_importance_in_unit_range():
    gs = _guides()
    bc.annotate_guides(gs, DesignRequest(sequence=_SEQ))
    for g in gs:
        v = g.bio_context.exon_importance
        assert v is None or 0.0 <= v <= 1.0
