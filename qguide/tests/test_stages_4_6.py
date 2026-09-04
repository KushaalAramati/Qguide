"""Tests for Stage 4 (off-target report), Stage 5 (optimizer modes + comparison),
and Stage 6 (benchmark + report)."""
from qguide.app.schemas import DesignRequest
from qguide.core import benchmark, off_target, optimization, pipeline, report

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _resp(**kw):
    return pipeline.run_design(DesignRequest(sequence=EXAMPLE, **kw))


# --- Stage 4: off-target report ------------------------------------------- #
def test_offtarget_report_has_hits_and_warning():
    g = _resp().guides[0]
    ot = g.off_target
    assert ot.genome_backed is False
    assert "genome" in ot.warning.lower()
    for h in ot.hits:
        assert h.mismatches >= 1
        assert 0.0 <= h.cfd_score <= 1.0
        assert h.annotation
        assert h.provisional is True
        assert getattr(h.severity, "value", h.severity) in ("low", "moderate", "high")


def test_genome_engine_reports_unavailable():
    eng = off_target.GenomeAlignmentOffTargetEngine()
    assert eng.available() is False
    rep = eng.analyze(_resp().guides[0])
    assert rep.genome_backed is False and "index" in rep.warning.lower()


# --- Stage 5: optimizer modes + comparison -------------------------------- #
def test_optimizer_modes_registry():
    assert set(optimization.OPTIMIZER_MODES) == {"classical", "quantum_inspired", "quantum_hardware"}


def test_quantum_hardware_falls_back_honestly():
    opt, mode, notes = optimization.make_optimizer_for_mode("quantum_hardware")
    assert mode in ("classical", "quantum_inspired")   # no token -> falls back
    assert any("hardware" in n.lower() for n in notes)


def test_top_n_vs_set_comparison_present():
    opt = _resp(set_size=3).optimized_set
    assert len(opt.top_n_individual) == 3
    assert opt.comparison_note
    assert opt.mode in ("classical", "quantum_inspired", "quantum_hardware")


# --- Stage 6: benchmark + report ------------------------------------------ #
def test_benchmark_structure_and_honesty():
    b = benchmark.benchmark(_resp().guides)
    assert b["provisional"] is True
    assert "qguide_outcome" in b["rankings"]
    assert "chopchop_like" in b["comparison"]
    # each comparison entry has overlap + spearman vs qguide
    c = b["comparison"]["crispor_like"]
    assert 0.0 <= c["top_k_overlap_with_qguide"] <= 1.0
    assert -1.0 <= c["spearman_vs_qguide"] <= 1.0


def test_report_structure():
    r = report.build_report(_resp(gene_name="DEMO1"))
    for key in ("inputs", "candidate_guides", "selected_set", "off_target_limitations",
                "confidence_limitations", "validation_note", "assumptions"):
        assert key in r
    assert r["candidate_guides"][0]["components"]["on_target"] >= 0
    assert "validation" in r["validation_note"].lower()
    # no cell type -> a confidence limitation should be flagged
    assert any("cell" in c.lower() for c in r["confidence_limitations"])
