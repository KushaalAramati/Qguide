"""Tests for the ensemble scoring layer (Stage 2)."""
from qguide.app.schemas import DesignRequest
from qguide.core import pipeline

EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _run(**kw):
    return pipeline.run_design(DesignRequest(sequence=EXAMPLE, **kw))


def test_ensemble_components_in_range():
    g = _run(desired_outcome="knockout").guides[0]
    e = g.ensemble
    for v in (e.on_target_score, e.off_target_score, e.specificity_score,
              e.desired_outcome_score, e.repair_outcome_score, e.genomic_context_score,
              e.cell_context_score, e.model_agreement_score, e.uncertainty_score,
              e.final_qguide_score):
        assert 0.0 <= v <= 1.0
    assert e.weights and e.contributions
    assert e.confidence_label in ("high", "medium", "low")
    assert e.goal_profile.startswith("knockout")


def test_provisional_components_are_flagged_honestly():
    e = _run(desired_outcome="knockout").guides[0].ensemble
    # these are placeholders today and must be advertised as provisional
    assert "genomic_context_score" in e.provisional
    assert "model_agreement_score" in e.provisional


def test_risk_tolerance_changes_penalty_weights():
    low = _run(risk_tolerance="low").guides[0].ensemble
    high = _run(risk_tolerance="high").guides[0].ensemble
    # low risk tolerance must weight off-target + uncertainty penalties more heavily
    assert low.weights["off_target"] > high.weights["off_target"]
    assert low.weights["uncertainty"] > high.weights["uncertainty"]


def test_all_outcome_modes_supported():
    for mode in ("knockout", "precise_edit", "base_edit", "prime_edit",
                 "crispri", "crispra", "screen"):
        resp = _run(desired_outcome=mode)
        assert resp.guides, mode
        assert 0.0 <= resp.guides[0].ensemble.final_qguide_score <= 1.0


def test_goal_profile_reflects_outcome():
    assert _run(desired_outcome="base_edit").guides[0].ensemble.goal_profile.startswith("base_edit")
    assert _run(desired_outcome="crispri").guides[0].ensemble.goal_profile.startswith("regulation")
    assert _run(desired_outcome="screen").guides[0].ensemble.goal_profile.startswith("screen")


def test_missing_cell_type_raises_uncertainty():
    with_cell = _run(cell_type="hek293").guides[0].ensemble
    no_cell = _run().guides[0].ensemble
    assert no_cell.uncertainty_score >= with_cell.uncertainty_score
    assert "cell_context_score" in no_cell.provisional


def test_badges_present():
    e = _run(desired_outcome="knockout").guides[0].ensemble
    assert any("confidence" in b.lower() for b in e.badges)
