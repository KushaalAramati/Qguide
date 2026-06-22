"""Tests for the experiment outcome simulator."""
from qguide.app.schemas import DesignRequest, DesiredOutcome
from qguide.core import experiment_simulation as expsim, pipeline


EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _guides():
    req = DesignRequest(sequence=EXAMPLE, desired_outcome=DesiredOutcome.KNOCKOUT, set_size=3)
    return pipeline.run_design(req).guides


def test_result_shape_and_ranges():
    g = _guides()[0]
    r = expsim.simulate_experiment(g, n_cells=2000, replicates=100)
    for key in ("editing_efficiency", "knockout_rate", "genotypes",
                "indel_spectrum", "verdict"):
        assert key in r
    k = r["knockout_rate"]
    assert 0.0 <= k["ci_low"] <= k["mean"] <= k["ci_high"] <= 1.0


def test_genotypes_sum_to_one():
    g = _guides()[0]
    r = expsim.simulate_experiment(g)
    geno = r["genotypes"]
    total = geno["wild_type"] + geno["heterozygous"] + geno["biallelic_ko"]
    assert abs(total - 1.0) < 1e-3


def test_indel_spectrum_normalised():
    g = _guides()[0]
    r = expsim.simulate_experiment(g)
    assert abs(sum(r["indel_spectrum"]["fraction"]) - 1.0) < 1e-3


def test_best_guide_beats_worst():
    guides = _guides()
    best = expsim.simulate_experiment(guides[0])
    worst = expsim.simulate_experiment(guides[-1])
    assert best["knockout_rate"]["mean"] >= worst["knockout_rate"]["mean"]


def test_deterministic_for_same_guide():
    g = _guides()[0]
    a = expsim.simulate_experiment(g)
    b = expsim.simulate_experiment(g)
    assert a["knockout_rate"]["mean"] == b["knockout_rate"]["mean"]


def test_compare_experiments_rows():
    guides = _guides()
    rows = expsim.compare_experiments([guides[0], guides[-1]])
    assert len(rows) == 2
    assert all("ko_mean" in r and "verdict" in r for r in rows)
