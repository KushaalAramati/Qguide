"""Tests for the model-adapter registry (Stage A) and its honesty guarantees."""
from qguide.app.schemas import DesignRequest
from qguide.core import models, pipeline


def _guide():
    req = DesignRequest(sequence="ACGT" * 30 + "TGG" + "ACGT" * 10,
                        gene_name="t", max_guides=8, set_size=3)
    return pipeline.run_design(req).guides[0]


def test_registry_has_named_models_across_tasks():
    tasks = {m.task for m in models.ALL_MODELS}
    assert tasks == {models.ON_TARGET, models.SPECIFICITY, models.REPAIR}
    names = {m.name for m in models.ALL_MODELS}
    for expected in ("Azimuth / Rule Set 2", "CRISPRon", "CFD (genome)",
                     "MIT specificity", "inDelphi", "Lindel", "FORECasT"):
        assert expected in names


def test_available_models_score_unavailable_abstain():
    g = _guide()
    for m in models.ALL_MODELS:
        s = m.score(g)
        if m.available:
            assert s is not None and 0.0 <= s <= 1.0, m.name
        else:
            # honesty: an unavailable model MUST NOT fabricate a number
            assert s is None, m.name


def test_kinds_are_honest():
    # every unavailable external model is labelled provisional (never 'real')
    for m in models.ALL_MODELS:
        if not m.available:
            assert m.kind == models.PROVISIONAL, m.name
        else:
            assert m.kind in (models.REAL, models.HEURISTIC), m.name


def test_on_target_agreement_uses_available_models():
    g = _guide()
    agr = models.on_target_agreement(g)
    n_avail = sum(1 for m in models.ON_TARGET_MODELS if m.score(g) is not None)
    assert n_avail >= 2                      # two heuristic on-target models ship today
    assert agr is not None and 0.0 <= agr <= 1.0


def test_report_and_limitations_shape():
    g = _guide()
    rows = models.model_report(g)
    assert rows and {"name", "task", "kind", "available", "score"} <= set(rows[0])
    lims = models.limitations(g)
    assert any("not installed" in l.lower() or "abstain" in l.lower() for l in lims)


def test_ensemble_embeds_model_scores_and_rationale():
    e = _guide().ensemble
    assert len(e.model_scores) == len(models.ALL_MODELS)
    assert e.rationale and "validation" in e.rationale.lower()
    assert e.limitations
