"""Edge cases for the formula upgrade: no PAMs, missing genome/off-target data."""
from qguide.app.schemas import DesignRequest
from qguide.core import (biological_context, off_target, pipeline, precision_score,
                         quantum_comparison_report as qcr)


def test_no_pam_sequence_yields_no_guides_and_no_crash():
    resp = pipeline.run_design(DesignRequest(sequence="AAAAAAAAAA"))  # no NGG PAM
    assert resp.guides == []
    assert resp.warnings
    # comparison + annotation on empty inputs must not crash
    assert "error" in qcr.compare_selection_strategies([], resp.request, 3)
    biological_context.annotate_guides([], resp.request)
    precision_score.compute_precision_scores([], resp.request)


def test_missing_genome_engine_reports_unavailable():
    engine = off_target.GenomeAlignmentOffTargetEngine(genome_index_path=None)
    assert engine.available() is False
    from qguide.tests.test_scoring import make_guide
    rep = engine.analyze(make_guide("ACGTACGTACGTACGTACGT"))
    assert rep.genome_backed is False and rep.warning


def test_severity_on_empty_report_is_zero_and_provisional():
    from qguide.app.schemas import OffTargetReport
    s = off_target.severity_profile(OffTargetReport(hits=[], genome_backed=False))
    assert s.severity_score == 0.0
    assert s.provisional is True
    assert s.essential_gene_hits is None


def test_precision_handles_no_bio_annotation():
    """If bio-context was never populated (defaults), precision still computes in range."""
    resp = pipeline.run_design(DesignRequest(sequence=(
        "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"), set_size=2))
    g = resp.guides[0]
    # overwrite bio-context with the empty default and recompute
    from qguide.app.schemas import BiologicalContext
    g.bio_context = BiologicalContext()
    p = precision_score.compute_precision(g, resp.request)
    assert 0.0 <= p.score <= 1.0
