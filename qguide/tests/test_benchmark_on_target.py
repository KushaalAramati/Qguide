"""Tests for the on-target accuracy benchmark harness (roadmap Task B)."""
from qguide.benchmarks import on_target_benchmark as B


def test_correlation_math():
    assert abs(B.spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(B.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(B._pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9


def test_spacer_from_context():
    thirty = "AAAA" + "G" * 20 + "TGG" + "CCC"
    spacer, pam = B.spacer_from_context(thirty)
    assert spacer == "G" * 20 and pam == "TGG"
    sp2, pam2 = B.spacer_from_context("ACGT" * 5)   # 20-mer path
    assert len(sp2) == 20


def test_on_target_uses_real_scoring_and_is_bounded():
    s = B.on_target_score("GACGATCGATCGTAGCTAGC", "AGG")
    assert 0.0 <= s <= 1.0


def test_evaluate_and_selftest_run():
    res = B.evaluate(["ACGT" * 5, "GGGG" + "ACGT" * 4], [0.1, 0.9])
    assert res["n"] == 2 and "spearman" in res and "pearson" in res
    assert B.selftest() == 0
