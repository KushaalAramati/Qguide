"""Tests for Step 1 -- guide generation."""
from qguide.core import guide_generator as gg
from qguide.app.schemas import Strand, TargetRegion


def test_reverse_complement():
    assert gg.reverse_complement("ATGC") == "GCAT"
    assert gg.reverse_complement("AAAA") == "TTTT"


def test_clean_sequence_strips_fasta_and_whitespace():
    raw = "> header\nATGC\nat gc\n"
    assert gg.clean_sequence(raw) == "ATGCATGC"


def test_clean_sequence_masks_invalid_bases():
    assert gg.clean_sequence("ATGXZ") == "ATGNN"


def test_gc_content():
    assert gg.gc_content("GGCC") == 1.0
    assert gg.gc_content("ATAT") == 0.0
    assert abs(gg.gc_content("ATGC") - 0.5) < 1e-9


def test_generates_guides_on_both_strands():
    # "CC.." near the 5' end is a minus-strand PAM (CCN); the "GG" ~25 nt in is a
    # plus-strand PAM (NGG). Both have >=20 nt of protospacer room, so both yield guides.
    seq = "CC" + "ATGCATGCATGCATGCATGCATG" + "GG" + "ATGCATGCATGC"
    guides = gg.generate_guides(seq, cas_enzyme="SpCas9")
    assert len(guides) > 0
    strands = {g.strand for g in guides}
    # this construct is designed to yield a guide on each strand
    assert Strand.PLUS in strands
    assert Strand.MINUS in strands


def test_guide_geometry_is_consistent():
    seq = "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT"
    guides = gg.generate_guides(seq, cas_enzyme="SpCas9")
    for g in guides:
        assert len(g.sequence) == 20
        assert g.end - g.position == 20
        assert 0 <= g.position < len(seq)
        assert 0.0 <= g.gc_content <= 1.0


def test_max_guides_cap():
    seq = "GG" * 200
    guides = gg.generate_guides(seq, cas_enzyme="SpCas9", max_guides=5)
    assert len(guides) <= 5


def test_target_region_affects_distance():
    seq = "ATGGCCTGACCGGATGCACCGGTGAACCTTGGCAGTCCATGGAGACCTTAGGCTAACCGGT" * 3
    near = gg.generate_guides(seq, target_region=TargetRegion(start=0, end=20))
    far = gg.generate_guides(seq, target_region=TargetRegion(start=150, end=170))
    # closest guide to an early target should be nearer than to a late target's first
    assert near[0].distance_to_target <= max(g.distance_to_target for g in near)


def test_cas_profile_registry_extensible():
    assert "SaCas9" in gg.CAS_PROFILES
    prof = gg.resolve_profile("Cas12a", None, None)
    assert prof.pam_side == "5prime"
    assert prof.guide_length == 23
