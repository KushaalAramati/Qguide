"""Tests for the classical-vs-quantum-inspired comparison report (Part 5)."""
from qguide.app.schemas import DesignRequest
from qguide.core import optimization, pipeline, quantum_comparison_report as qcr

_SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
        "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _rep(preset="balanced", set_size=3):
    resp = pipeline.run_design(DesignRequest(sequence=_SEQ, set_size=set_size,
                                             optimizer_preset=preset, cell_type="hek293"))
    return qcr.compare_selection_strategies(resp.guides, resp.request, set_size, preset)


def test_three_strategies_each_correct_size():
    rep = _rep(set_size=3)
    for key in ("top_n_individual", "classical_optimized", "quantum_inspired_optimized"):
        assert len(rep["sets"][key]["selected"]) == 3


def test_verdict_keys_present():
    v = _rep()["verdict"]
    for k in ("set_optimization_beats_topn", "quantum_inspired_meaningful_improvement",
              "classical_equals_quantum", "energy_gap_quantum_minus_classical", "text"):
        assert k in v


def test_metrics_in_range():
    rep = _rep()
    for s in rep["sets"].values():
        assert 0.0 <= s["off_target_burden"] <= 1.0
        assert 0.0 <= s["diversity"] <= 1.0
        assert 0.0 <= s["combined_outcome"] <= 1.0


def test_honesty_when_backend_absent():
    """If dimod isn't installed, quantum-inspired must fall back and say so honestly."""
    rep = _rep()
    assert rep["quantum_backend_installed"] == optimization.quantum_available()
    if not optimization.quantum_available():
        assert rep["verdict"]["classical_equals_quantum"] is True
        assert rep["verdict"]["quantum_inspired_meaningful_improvement"] is False
        assert "not installed" in rep["verdict"]["text"].lower()


def test_empty_guides_handled():
    rep = qcr.compare_selection_strategies([], None, 3)
    assert "error" in rep
