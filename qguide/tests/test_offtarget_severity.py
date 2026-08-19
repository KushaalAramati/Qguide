"""Tests for the off-target SEVERITY aggregation (Part 2, item 9)."""
from qguide.app.schemas import OffTargetHit, OffTargetReport, RiskCategory
from qguide.core import off_target


def _report(hits):
    return OffTargetReport(hits=hits, genome_backed=False)


def _hit(anno, cfd, mm_positions):
    return OffTargetHit(annotation=anno, cfd_score=cfd, mismatches=len(mm_positions),
                        mismatch_positions=mm_positions, severity=RiskCategory.MODERATE)


def test_empty_hits_zero_severity():
    s = off_target.severity_profile(_report([]))
    assert s.severity_score == 0.0
    assert s.essential_gene_hits is None      # essential DB unavailable -> unknown


def test_severity_in_unit_range():
    s = off_target.severity_profile(_report([
        _hit("exon", 0.6, [3]), _hit("intergenic", 0.4, [12])]))
    assert 0.0 <= s.severity_score <= 1.0


def test_coding_hit_more_severe_than_intergenic():
    coding = off_target.severity_profile(_report([_hit("exon", 0.6, [3])]))
    inter = off_target.severity_profile(_report([_hit("intergenic", 0.6, [3])]))
    assert coding.severity_score > inter.severity_score
    assert coding.coding_hits == 1 and inter.coding_hits == 0


def test_seed_mismatch_disarms_offtarget():
    """A PAM-proximal (seed) mismatch lowers an off-target's severity vs a distal one."""
    distal = off_target.severity_profile(_report([_hit("exon", 0.6, [2])]), spacer_len=20)
    seed = off_target.severity_profile(_report([_hit("exon", 0.6, [18])]), spacer_len=20)
    assert distal.severity_score > seed.severity_score
    assert seed.seed_mismatch_hits == 1 and distal.seed_mismatch_hits == 0


def test_counts_coding_and_regulatory():
    s = off_target.severity_profile(_report([
        _hit("exon", 0.5, [3]), _hit("promoter", 0.5, [4]), _hit("enhancer", 0.5, [5]),
        _hit("intron", 0.5, [6])]))
    assert s.coding_hits == 1
    assert s.regulatory_hits == 2             # promoter + enhancer
    assert s.essential_gene_hits is None      # honest unknown


def test_engine_attaches_severity():
    from qguide.tests.test_scoring import make_guide
    g = make_guide("ATATATATATATATATATAT")
    off_target.analyze_off_target(g)
    assert g.off_target.severity is not None
    assert 0.0 <= g.off_target.severity.severity_score <= 1.0
    assert g.off_target.severity.provisional is True   # heuristic hits
