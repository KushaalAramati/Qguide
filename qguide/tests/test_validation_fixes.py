"""Regression tests for the two defects found by the GUIDE-seq (Tsai 2015) validation:
  1. generator dropped guides at overlapping NGG PAMs (EMX1 canonical guide missed);
  2. off-target heuristic ranked the promiscuous VEGFA-site-1 guide as SAFER than EMX1.
Both are locked here so they can't silently regress.
"""
from qguide.app.schemas import DesignRequest, Guide, Strand
from qguide.core import (guide_generator as gen, scoring, off_target, context_adjustment,
                         outcome_prediction, ensemble, biological_context, precision_score, optimization)

# Real EMX1 genomic window (hg38 chr2:72,933,800-72,933,920); the published EMX1 guide
# (GAGTCCGAGCAGAAGAAGAA / GGG) sits inside it.
EMX1_WIN = ("CCAGAACCGGAGGACAAAGTACAAACGGCAGAAGCTGGAGGAGGAAGGGCCTGAGTCCGAGCAGAAGAAGAAGGG"
            "CTCCCATCACATCAACCGGTGGCGCATTGCCACGAAGCAGGCCAA")
EMX1_SPACER = "GAGTCCGAGCAGAAGAAGAA"
VEGFA1_SPACER = "GGGTGGGGGGAGTTTGCTCC"


def _score(spacer, pam, gene):
    req = DesignRequest(sequence=spacer, gene_name=gene, cas_enzyme="SpCas9", organism="human",
                        cell_type="hek293", delivery_method="electroporation",
                        desired_outcome="knockout", set_size=1)
    g = Guide(guide_id=gene, sequence=spacer, pam=pam, strand=Strand.PLUS, position=0,
              end=len(spacer), cut_site=len(spacer) - 3, gc_content=gen.gc_content(spacer),
              distance_to_target=0)
    scoring.score_guide(g)
    off_target.analyze_off_target(g)
    context_adjustment.apply_context_to_guides([g], req)
    outcome_prediction.predict_outcome(g, "knockout", efficiency=g.context.multiplier)
    g.final_score, g.final_breakdown = optimization.compute_final_score(g)
    g.ensemble = ensemble.score_guide(g, req)
    biological_context.annotate_guide(g, req)
    g.precision = precision_score.compute_precision(g, req)
    return g


# --- Fix 1: overlapping-NGG PAM handling ---------------------------------- #
def test_generator_returns_canonical_emx1_guide():
    guides = gen.generate_guides(EMX1_WIN, cas_enzyme="SpCas9")
    exact = [g for g in guides if g.sequence == EMX1_SPACER]
    assert exact, "generator must emit the published EMX1 guide (overlapping GGG PAM)"
    assert exact[0].pam.endswith("GG") and exact[0].strand == Strand.PLUS


def test_overlapping_pams_both_kept():
    # an AGGG context contains overlapping AGG and GGG PAMs -> both guides should appear
    guides = gen.generate_guides(EMX1_WIN, cas_enzyme="SpCas9")
    pams_near = {g.pam for g in guides if g.strand == Strand.PLUS}
    assert "GGG" in pams_near and "AGG" in pams_near


# --- Fix 2: off-target ordering matches GUIDE-seq ------------------------- #
def test_offtarget_ranks_vegfa1_above_emx1():
    """GUIDE-seq: VEGFA site 1 is the most promiscuous guide (>150 sites); EMX1 far fewer.
    QGuide's heuristic risk must now order them the same way."""
    emx = _score(EMX1_SPACER, "GGG", "EMX1")
    veg = _score(VEGFA1_SPACER, "TGG", "VEGFA1")
    assert veg.off_target.risk_score > emx.off_target.risk_score
    assert veg.off_target.severity.severity_score > emx.off_target.severity.severity_score


def test_gc_content_still_exact():
    assert _score(EMX1_SPACER, "GGG", "EMX1").gc_content == 0.50
    assert _score(VEGFA1_SPACER, "TGG", "VEGFA1").gc_content == 0.70


def test_gc_rich_polyG_raises_offtarget_risk():
    """The two new promiscuity correlates fire on a GC-rich poly-G spacer."""
    assert off_target._gc_richness("GGGGGGGGGGCCCCCCCCCC") > 0.5
    assert off_target._homopolymer_risk("GGGGGGGAGTTTGCTCCTAA") > 0.0
    assert off_target._homopolymer_risk("GAGTCCGAGCAGAAGAAGAA") == 0.0
