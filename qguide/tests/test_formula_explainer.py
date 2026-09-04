"""Tests for the formula explanation layer (Part 6)."""
from qguide.app.schemas import DesignRequest
from qguide.core import formula_explainer as fx, pipeline, quantum_comparison_report as qcr

_SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
        "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _run(preset="max_specificity"):
    return pipeline.run_design(DesignRequest(sequence=_SEQ, set_size=3,
                                             optimizer_preset=preset, cell_type="hek293"))


def test_precision_explanation_structure():
    g = _run().guides[0]
    e = fx.explain_precision(g)
    assert e["guide_id"] == g.guide_id
    assert e["why_high"] and e["why_low"]
    assert e["validate"]
    assert set(m["key"] for m in e["missing_data"]) == set(g.precision.missing)
    assert "Precision Score" in e["text"]
    assert "validation" in e["text"].lower()


def test_precision_explanation_flags_missing_data():
    g = _run().guides[0]
    e = fx.explain_precision(g)
    # abstained biological variables are surfaced honestly, not hidden
    assert any(m["key"] == "domain_disruption" for m in e["missing_data"])


def test_set_explanation_structure():
    resp = _run()
    rep = qcr.compare_selection_strategies(resp.guides, resp.request, 3, "max_specificity")
    e = fx.explain_set(resp.guides, rep, preset="max_specificity")
    assert e["selected"] == rep["sets"]["classical_optimized"]["selected"]
    assert "tradeoff" in e and "character" in e
    assert e["text"]
    assert "quantum" in e["text"].lower()


def test_set_explanation_reports_exclusions_or_match():
    resp = _run()
    rep = qcr.compare_selection_strategies(resp.guides, resp.request, 3, "max_specificity")
    e = fx.explain_set(resp.guides, rep, preset="max_specificity")
    selected = set(e["selected"])
    topn = set(e["top_n_individual"])
    if selected != topn:
        # every excluded strong guide gets a stated reason
        assert set(e["excluded_strong_guides"]) == (topn - selected)
    else:
        assert "same guides" in e["text"].lower()
