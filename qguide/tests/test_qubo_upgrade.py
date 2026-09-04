"""Tests for the upgraded QUBO: new reward/penalty terms + pairwise synergy (Part 4)."""
from dataclasses import asdict

from qguide.app.schemas import DesignRequest, Guide, Strand
from qguide.core import optimization, pipeline

_SEQ = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
        "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
        "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _guides(preset="balanced"):
    return pipeline.run_design(
        DesignRequest(sequence=_SEQ, set_size=3, optimizer_preset=preset,
                      cell_type="hek293")).guides


def test_new_weight_fields_present():
    w = optimization.QuboWeights()
    d = asdict(w)
    for f in ("q_precision", "q_exon_importance", "q_transcript_coverage",
              "r_severity", "r_missing_data", "r_variant", "r_practicality",
              "d_correlated_uncertainty", "d_isoform",
              "b_region_diversity", "b_exon_diversity", "b_domain_diversity",
              "b_eff_spec_balance", "b_uncertainty_decorrelation",
              "b_offtarget_decorrelation"):
        assert f in d


def test_quality_and_risk_unit_range_with_new_signals():
    w = optimization.get_weights("balanced")
    for g in _guides():
        assert 0.0 <= optimization.quality_i(g, w) <= 1.0
        assert 0.0 <= optimization.risk_i(g, w) <= 1.0


def test_quality_degrades_gracefully_on_bare_guide():
    """quality_i / risk_i must stay valid when ensemble/precision/bio are absent."""
    g = Guide(guide_id="g", sequence="ACGTACGTACGTACGTACGT", pam="AGG",
              strand=Strand.PLUS, position=0, end=20, cut_site=17,
              gc_content=0.5, distance_to_target=0)
    w = optimization.get_weights("balanced")
    assert 0.0 <= optimization.quality_i(g, w) <= 1.0
    assert 0.0 <= optimization.risk_i(g, w) <= 1.0


def test_synergy_symmetric_and_bounded():
    gs = _guides()
    w = optimization.get_weights("broad_coverage")
    a, b = gs[0], gs[1]
    s = optimization.synergy_ij(a, b, w)
    assert 0.0 <= s <= 1.0
    assert abs(s - optimization.synergy_ij(b, a, w)) < 1e-9


def test_redundancy_symmetric_and_bounded():
    gs = _guides()
    w = optimization.get_weights("balanced")
    a, b = gs[0], gs[1]
    r = optimization.redundancy_ij(a, b, w)
    assert 0.0 <= r <= 1.0
    assert abs(r - optimization.redundancy_ij(b, a, w)) < 1e-9


def test_cardinality_diagonal_matches_formula():
    gs = _guides()[:5]
    k = 2
    w = optimization.get_weights("balanced")
    qubo = optimization.build_qubo(gs, set_size=k, weights=w)
    P = w.cardinality_penalty
    for i, g in enumerate(gs):
        qi = optimization.quality_i(g, w)
        ri = optimization.risk_i(g, w)
        expected = (-w.quality_scale * qi) + (w.risk_scale * ri) + P * (1 - 2 * k)
        assert abs(qubo.linear_quadratic[(i, i)] - expected) < 1e-9


def test_diversity_bonus_rewards_synergy_in_offdiagonal():
    """Turning up diversity_bonus lowers (rewards) the off-diagonal for a synergistic pair."""
    gs = _guides()[:4]
    w0 = optimization.QuboWeights(diversity_bonus=0.0)
    w1 = optimization.QuboWeights(diversity_bonus=1.0)
    q0 = optimization.build_qubo(gs, 2, w0)
    q1 = optimization.build_qubo(gs, 2, w1)
    # at least one off-diagonal must decrease when synergy is rewarded
    decreased = any(q1.linear_quadratic[(i, j)] < q0.linear_quadratic[(i, j)] - 1e-9
                    for i in range(len(gs)) for j in range(i + 1, len(gs)))
    assert decreased


def test_guide_count_constraint_respected():
    for n in (2, 3, 4):
        resp = pipeline.run_design(DesignRequest(sequence=_SEQ, set_size=n))
        assert len(resp.optimized_set.selected_guide_ids) == n
