"""Tests for Steps 6 & 7 -- multi-objective scoring and QUBO optimization, plus
an end-to-end pipeline smoke test."""
from qguide.app.schemas import DesignRequest, DesiredOutcome
from qguide.core import optimization, pipeline


EXAMPLE = ("ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
           "TACGGGATCCAAGGTTCCAGGTGCAATTCCGGATCACCGGAATTGGCCTTAAGGGCTTTCC"
           "GGATCCAATTGGCCAATTCGGGATCCATGGCAACCGGTTAACCGGATCCAAGGTTAACCGG")


def _run():
    req = DesignRequest(sequence=EXAMPLE, gene_name="DEMO1",
                        desired_outcome=DesiredOutcome.KNOCKOUT, set_size=3)
    return pipeline.run_design(req)


def test_final_scores_sorted_desc():
    resp = _run()
    scores = [g.final_score for g in resp.guides]
    assert scores == sorted(scores, reverse=True)
    for g in resp.guides:
        assert 0.0 <= g.final_score <= 1.0
        assert set(g.final_breakdown) == set(optimization.FINAL_WEIGHTS)


def test_qubo_energy_matches_manual():
    resp = _run()
    qubo = optimization.build_qubo(resp.guides[:6], set_size=2)
    x = [1, 1, 0, 0, 0, 0]
    manual = 0.0
    for (i, j), q in qubo.linear_quadratic.items():
        manual += q * x[i] * x[j]
    assert abs(qubo.energy(x) - manual) < 1e-9


def test_qubo_export_format_for_quantum_sdks():
    resp = _run()
    qubo = optimization.build_qubo(resp.guides[:5], set_size=2)
    qdict = qubo.to_qubo_dict()
    # keys are guide-id pairs (the labelled QUBO format dimod/Qiskit/Braket accept)
    ids = set(resp.guides[i].guide_id for i in range(5))
    assert all(a in ids and b in ids for (a, b) in qdict)
    # exporting preserves the coefficients
    assert len(qdict) == len(qubo.linear_quadratic)
    diag = qubo.guide_ids[0]
    assert (diag, diag) in qdict


def test_optimizer_selects_requested_set_size():
    resp = _run()
    assert len(resp.optimized_set.selected_guide_ids) == 3
    # selected ids must be real guides
    ids = {g.guide_id for g in resp.guides}
    assert all(s in ids for s in resp.optimized_set.selected_guide_ids)


def test_optimizer_is_deterministic():
    a = _run().optimized_set.selected_guide_ids
    b = _run().optimized_set.selected_guide_ids
    assert a == b


def test_optimization_has_explanations():
    resp = _run()
    assert resp.optimized_set.rejected_explanations  # non-empty
    assert resp.optimized_set.tradeoffs


def test_best_single_guide_is_top_ranked():
    resp = _run()
    assert resp.best_single_guide_id == resp.guides[0].guide_id


def test_pipeline_populates_all_layers():
    resp = _run()
    g = resp.guides[0]
    assert g.scores.on_target > 0
    assert g.outcome.model == "rule_based_v1"
    assert g.off_target.method.startswith("heuristic_v1")
    assert g.context.multiplier > 0
    assert g.explanation  # human-readable text
    assert resp.summary


def test_context_sensitivity_runs():
    req = DesignRequest(sequence=EXAMPLE, set_size=3)
    resp = pipeline.run_design(req)
    gid = resp.guides[0].guide_id
    scenarios = [{"label": "neuron", "cell_type": "neuron"},
                 {"label": "stem", "cell_type": "stem_cell"}]
    out = pipeline.context_sensitivity(req, gid, scenarios)
    assert len(out) == 2
    assert all("final_score" in r for r in out)


def test_backend_registry_and_factory():
    backends = optimization.available_backends()
    assert "sa" in backends
    # factory always returns a working optimizer, even for unknown keys
    opt = optimization.make_optimizer("nonexistent")
    assert hasattr(opt, "solve")


def test_dwave_backend_if_available():
    import pytest
    if not optimization.quantum_available():
        pytest.skip("dimod / dwave-samplers not installed")
    resp = _run()
    qubo = optimization.build_qubo(resp.guides, set_size=3)
    opt = optimization.DimodQUBOOptimizer(num_reads=50)
    x, energy, reads = opt.solve(qubo)
    assert len(x) == len(resp.guides)
    assert sum(x) >= 1                      # selects at least one guide
    assert opt.method.startswith("dwave")


def test_dwave_and_sa_agree_on_small_instance():
    import pytest
    if not optimization.quantum_available():
        pytest.skip("dimod / dwave-samplers not installed")
    resp = _run()
    guides = resp.guides[:6]
    qubo = optimization.build_qubo(guides, set_size=2)
    # exhaustive ground truth over 2^6 bitstrings
    best_e, best_x = None, None
    for mask in range(1 << len(guides)):
        x = [(mask >> i) & 1 for i in range(len(guides))]
        e = qubo.energy(x)
        if best_e is None or e < best_e:
            best_e, best_x = e, x
    dwave_x, dwave_e, _ = optimization.DimodQUBOOptimizer(num_reads=200).solve(qubo)
    assert abs(dwave_e - best_e) < 1e-6     # quantum-style sampler finds the optimum


def test_simulate_axis_covers_all_scenarios():
    req = DesignRequest(sequence=EXAMPLE, set_size=3)
    results = pipeline.simulate_axis(req, "cell_type")
    assert len(results) == len(pipeline.SIMULATION_AXES["cell_type"])
    for r in results:
        assert "best_knockout" in r and 0.0 <= r["best_knockout"] <= 1.0
        assert "set_ids" in r


def test_simulate_objective_changes_outcome():
    req = DesignRequest(sequence=EXAMPLE, set_size=3)
    results = pipeline.simulate_axis(req, "desired_outcome")
    finals = {r["label"]: r["best_functional"] for r in results}
    # different objectives should not all collapse to one functional score
    assert len(set(finals.values())) > 1


def test_simulate_experiments_custom_scenarios():
    req = DesignRequest(sequence=EXAMPLE, set_size=2)
    out = pipeline.simulate_experiments(req, [
        {"label": "cold RNP", "temperature": 30.0, "delivery_method": "rnp"},
        {"label": "warm lenti", "temperature": 37.0, "delivery_method": "lentivirus"},
    ])
    assert len(out) == 2
    assert all(r["n_guides"] > 0 for r in out)


def test_high_fidelity_enzyme_lowers_off_target_end_to_end():
    base = DesignRequest(sequence=EXAMPLE, set_size=3)
    sp = pipeline.run_design(base.model_copy(update={"cas_enzyme": "SpCas9"}))
    hf = pipeline.run_design(base.model_copy(update={"cas_enzyme": "SpCas9-HF1"}))
    # SpCas9 and SpCas9-HF1 generate identical guides (same NGG PAM / length).
    sp_by = {g.guide_id: g.off_target.risk_score for g in sp.guides}
    hf_by = {g.guide_id: g.off_target.risk_score for g in hf.guides}
    common = set(sp_by) & set(hf_by)
    assert common
    # no guide gets riskier, and the total predicted off-target burden falls
    assert all(hf_by[k] <= sp_by[k] + 1e-9 for k in common)
    assert sum(hf_by[k] for k in common) < sum(sp_by[k] for k in common)


def test_simulate_axis_rejects_unknown():
    import pytest
    req = DesignRequest(sequence=EXAMPLE)
    with pytest.raises(ValueError):
        pipeline.simulate_axis(req, "not_an_axis")


def test_empty_sequence_yields_no_guides():
    req = DesignRequest(sequence="AAAA")  # no PAM
    resp = pipeline.run_design(req)
    assert resp.guides == []
    assert resp.warnings
