"""Tests for the QGuide Precision Score (formula-upgrade brief, Part 1)."""
from qguide.app.schemas import DesignRequest
from qguide.core import biological_context, pipeline, precision_score

_SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
        "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _run(**kw):
    req = DesignRequest(sequence=_SEQ, gene_name="T", set_size=3, **kw)
    return pipeline.run_design(req)


def test_precision_in_unit_range_and_attached():
    for g in _run(cell_type="hek293").guides:
        assert 0.0 <= g.precision.score <= 1.0
        assert g.precision.components               # breakdown attached
        assert g.precision.confidence_label in {"high", "medium", "low"}


def test_score_reconstructs_from_components():
    """Score == clamp((positive - penalty) / positive_mass) from the stored breakdown."""
    g = _run().guides[0]
    p = g.precision
    pos = sum(c.contribution for c in p.components if c.group == "positive" and c.available)
    pen = -sum(c.contribution for c in p.components if c.group == "penalty" and c.available)
    expected = max(0.0, min(1.0, (pos - pen) / max(p.positive_mass, 1e-9)))
    assert abs(expected - p.score) < 1e-3


def test_unavailable_components_abstain_not_fabricated():
    g = _run().guides[0]                      # default proxy provider
    # transcript/domain/conservation/variant have no data source -> abstain
    missing = set(g.precision.missing)
    assert {"transcript_coverage", "domain_disruption", "conservation",
            "variant_conflict"} <= missing
    for c in g.precision.components:
        if not c.available:
            assert c.raw is None and c.source == "unknown"
    assert g.precision.data_completeness < 1.0


def test_null_provider_lowers_completeness():
    """With NO annotation proxies, more components abstain and completeness drops."""
    resp = _run(cell_type="hek293")
    g = resp.guides[0]
    proxy_complete = g.precision.data_completeness
    biological_context.annotate_guides(resp.guides, resp.request,
                                       provider=biological_context.NullAnnotationProvider())
    precision_score.compute_precision_scores(resp.guides, resp.request)
    assert resp.guides[0].precision.data_completeness < proxy_complete


def test_nine_presets_change_score():
    resp = _run(cell_type="hek293")
    names = precision_score.preset_names()
    assert len(names) >= 9
    scores = {}
    for name in names:
        precision_score.compute_precision_scores(resp.guides, resp.request, preset=name)
        scores[name] = resp.guides[0].precision.score
    # presets must not all collapse to one value
    assert len(set(round(s, 4) for s in scores.values())) > 1
    assert set(scores) >= {"balanced", "max_knockout", "max_specificity",
                           "max_confidence", "low_off_target_risk", "broad_coverage",
                           "screening_library", "therapeutic_safety",
                           "experimental_discovery"}


def test_missing_repair_model_is_penalised():
    """No trained repair model is installed -> the structural penalty fires."""
    g = _run().guides[0]
    comp = next(c for c in g.precision.components if c.key == "no_repair_model_support")
    assert comp.available and comp.raw is not None and comp.raw > 0.0


def test_no_genome_index_penalty_present():
    g = _run().guides[0]
    comp = next(c for c in g.precision.components if c.key == "no_genome_index")
    assert comp.raw == 1.0                     # off-target is heuristic (no genome)


def test_unknown_preset_falls_back():
    w = precision_score.get_weights("nonsense-preset")
    assert w.positive and "on_target" in w.positive
