"""Feature 2 — QUBO folds in every scoring variable; presets are configurable."""
from qguide.app.schemas import DesignRequest
from qguide.core import optimization, pipeline

_SEQ = ("ATGCGTACGTTAGCACGTGGACGTACGATCGTAGGCTAGCTAGGACGTACGTAGCTAGCTGG"
        "CATCGATCGTAGCTAGCGGATCGATCGATGGCTAGCTAGCTAGGCATCGTAGCTGG")


def _guides(preset="balanced", set_size=3):
    req = DesignRequest(sequence=_SEQ, gene_name="t", max_guides=30,
                        set_size=set_size, optimizer_preset=preset)
    return pipeline.run_design(req)


def test_seven_presets_exist():
    assert set(optimization.PRESETS) == {
        "balanced", "max_knockout", "max_specificity", "min_uncertainty",
        "broad_coverage", "therapeutic_safety", "screening_library"}
    for name in optimization.PRESETS:
        assert name in optimization.PRESET_INFO


def test_quality_and_risk_in_unit_range():
    guides = _guides().guides
    w = optimization.get_weights("balanced")
    for g in guides:
        assert 0.0 <= optimization.quality_i(g, w) <= 1.0
        assert 0.0 <= optimization.risk_i(g, w) <= 1.0


def test_redundancy_symmetric_and_bounded():
    guides = _guides().guides
    w = optimization.get_weights("balanced")
    a, b = guides[0], guides[1]
    r = optimization.redundancy_ij(a, b, w)
    assert 0.0 <= r <= 1.0
    assert abs(r - optimization.redundancy_ij(b, a, w)) < 1e-9


def test_qubo_energy_still_matches_manual_with_weights():
    guides = _guides().guides[:6]
    qubo = optimization.build_qubo(guides, set_size=2,
                                   weights=optimization.get_weights("max_specificity"))
    x = [1, 1, 0, 0, 0, 0]
    manual = sum(q * x[i] * x[j] for (i, j), q in qubo.linear_quadratic.items())
    assert abs(qubo.energy(x) - manual) < 1e-9


def test_guide_count_constraint_respected():
    for n in (2, 3, 4):
        r = _guides(set_size=n)
        assert len(r.optimized_set.selected_guide_ids) == n


def test_result_records_preset_weights_and_set_metrics():
    o = _guides(preset="therapeutic_safety").optimized_set
    assert o.preset == "therapeutic_safety"
    assert o.weights and o.weights["r_off_target"] == 2.0    # therapeutic preset
    for m in (o.set_expected_outcome, o.set_off_target_burden,
              o.set_diversity, o.set_uncertainty):
        assert 0.0 <= m <= 1.0
    assert o.quality_by_guide and o.risk_by_guide


def test_presets_change_weights():
    spec = optimization.get_weights("max_specificity")
    ko = optimization.get_weights("max_knockout")
    assert spec.r_off_target > ko.r_off_target          # specificity penalises off-target more
    assert ko.q_knockout > spec.q_knockout              # knockout preset rewards KO more


def test_unknown_preset_falls_back_to_balanced():
    assert optimization.get_weights("nonsense") is optimization.PRESETS["balanced"]
