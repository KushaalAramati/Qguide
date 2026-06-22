"""Tests for Step 4 -- functional outcome prediction."""
from qguide.app.schemas import DesiredOutcome, Guide, Strand
from qguide.core import outcome_prediction, scoring


def make_scored_guide(seq, distance=0):
    from qguide.core.guide_generator import gc_content
    g = Guide(
        guide_id="gRNA_test", sequence=seq, pam="AGG", strand=Strand.PLUS,
        position=0, end=len(seq), cut_site=len(seq) - 3,
        gc_content=gc_content(seq), distance_to_target=distance,
    )
    scoring.score_guide(g)
    return g


def test_probabilities_are_valid():
    g = make_scored_guide("ATGCAGTCAGTCGATCGTAC")
    outcome_prediction.predict_outcome(g, DesiredOutcome.KNOCKOUT.value)
    o = g.outcome
    for p in (o.frameshift_prob, o.in_frame_indel_prob, o.no_edit_prob,
              o.knockout_prob, o.exon_disruption_prob, o.functional_disruption_score):
        assert 0.0 <= p <= 1.0


def test_edit_components_sum_to_one():
    g = make_scored_guide("ATGCAGTCAGTCGATCGTAC")
    outcome_prediction.predict_outcome(g)
    o = g.outcome
    total = o.frameshift_prob + o.in_frame_indel_prob + o.no_edit_prob
    assert abs(total - 1.0) < 1e-6


def test_higher_on_target_raises_knockout():
    strong = make_scored_guide("ATGCAGTCAGTCGATCGTAC")   # balanced, clean
    weak = make_scored_guide("AAAAAAAAAAAAAAAAAAAA")      # poor
    outcome_prediction.predict_outcome(strong)
    outcome_prediction.predict_outcome(weak)
    assert strong.outcome.knockout_prob > weak.outcome.knockout_prob


def test_objective_changes_functional_score():
    g1 = make_scored_guide("ATGCAGTCAGTCGATCGTAC")
    g2 = make_scored_guide("ATGCAGTCAGTCGATCGTAC")
    outcome_prediction.predict_outcome(g1, DesiredOutcome.KNOCKOUT.value)
    outcome_prediction.predict_outcome(g2, DesiredOutcome.EXON_TARGETING.value)
    # different objectives weight the functional score differently
    assert g1.outcome.functional_disruption_score != g2.outcome.functional_disruption_score


def test_model_is_pluggable():
    model = outcome_prediction.RuleBasedOutcomeModel()
    g = make_scored_guide("ATGCAGTCAGTCGATCGTAC")
    pred = model.predict(g, DesiredOutcome.KNOCKOUT.value)
    assert pred.model == "rule_based_v1"
