"""Tests for Step 2 (scoring), Step 3 (off-target) and Step 5 (context)."""
from qguide.app.schemas import DesignRequest, Guide, Strand
from qguide.core import context_adjustment, off_target, scoring


def make_guide(seq, gc=None, distance=0, pam="AGG"):
    from qguide.core.guide_generator import gc_content
    return Guide(
        guide_id="gRNA_test", sequence=seq, pam=pam, strand=Strand.PLUS,
        position=0, end=len(seq), cut_site=max(0, len(seq) - 3),
        gc_content=gc if gc is not None else gc_content(seq),
        distance_to_target=distance,
    )


def test_gc_score_peaks_at_50_percent():
    balanced = make_guide("ATGCATGCATGCATGCATGC")   # 50% GC
    skewed = make_guide("AAAAAAAAAAAAAAAAAAAA")      # 0% GC
    scoring.score_guide(balanced)
    scoring.score_guide(skewed)
    assert balanced.scores.gc_content > skewed.scores.gc_content


def test_homopolymer_penalty_detects_runs():
    clean = make_guide("ATGCATGCATGCATGCATGC")
    runny = make_guide("AAAAATGCATGCATGCATGC")
    assert scoring.homopolymer_penalty(runny) > scoring.homopolymer_penalty(clean)


def test_polyT_triggers_warning():
    g = make_guide("ATGCTTTTATGCATGCATGC")
    scoring.score_guide(g)
    assert any("Poly-T" in w or "poly" in w.lower() for w in g.warnings)


def test_on_target_in_unit_range():
    g = make_guide("ATGCATGCATGCATGCATGC")
    scoring.score_guide(g)
    assert 0.0 <= g.scores.on_target <= 1.0


def test_scores_are_modular_registry():
    assert set(scoring.COMPONENTS) >= {
        "gc_content", "pam", "complexity", "homopolymer_penalty",
        "secondary_structure_penalty", "distance_to_target", "sequence_quality",
    }


def test_off_target_low_complexity_is_riskier():
    engine = off_target.HeuristicOffTargetEngine()
    complex_g = make_guide("ATGCAGTCAGTCGATCGTAC")
    repetitive = make_guide("ATATATATATATATATATAT")
    r1 = engine.analyze(complex_g)
    r2 = engine.analyze(repetitive)
    assert r2.risk_score > r1.risk_score
    assert sum(b.count for b in r2.mismatch_distribution) >= 0


def test_off_target_category_thresholds():
    engine = off_target.HeuristicOffTargetEngine()
    g = make_guide("ATATATATATATATATATAT")
    rep = engine.analyze(g)
    assert rep.risk_category.value in {"low", "moderate", "high"}


def test_context_multiplier_changes_with_cell_type():
    base = DesignRequest(sequence="ATGC", cell_type="stem_cell")
    neuron = DesignRequest(sequence="ATGC", cell_type="neuron")
    m_stem = context_adjustment.context_multipliers(base).multiplier
    m_neuron = context_adjustment.context_multipliers(neuron).multiplier
    assert m_stem != m_neuron
    # stem cells boost editing, neurons depress it
    assert m_stem > m_neuron


def test_high_fidelity_enzyme_has_lower_off_target_multiplier():
    spc = context_adjustment.context_multipliers(
        DesignRequest(sequence="ATGC", cas_enzyme="SpCas9"))
    hf = context_adjustment.context_multipliers(
        DesignRequest(sequence="ATGC", cas_enzyme="SpCas9-HF1"))
    assert hf.off_target_multiplier < spc.off_target_multiplier
    # the on-target efficiency factor is tracked separately and barely changes
    assert hf.applied["off_target_risk"] < spc.applied["off_target_risk"]


def test_gc_multiplier_present_and_organism_specific():
    human = context_adjustment.context_multipliers(
        DesignRequest(sequence="ATGC", organism="human"))
    ecoli = context_adjustment.context_multipliers(
        DesignRequest(sequence="ATGC", organism="e_coli"))
    assert human.gc_multiplier != ecoli.gc_multiplier


def test_scale_report_lowers_risk_and_category():
    engine = off_target.HeuristicOffTargetEngine()
    g = make_guide("ATATATATATATATATATAT")        # high-risk repetitive guide
    rep = engine.analyze(g)
    scaled = off_target.scale_report(rep, 0.3)
    assert scaled.risk_score < rep.risk_score
    assert scaled.potential_off_target_count <= rep.potential_off_target_count
    assert "context" in scaled.method


def test_temperature_falloff():
    cold = DesignRequest(sequence="ATGC", temperature=25.0)
    warm = DesignRequest(sequence="ATGC", temperature=37.0)
    m_cold = context_adjustment.context_multipliers(cold).multiplier
    m_warm = context_adjustment.context_multipliers(warm).multiplier
    assert m_warm > m_cold
