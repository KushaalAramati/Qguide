"""
Step 1 -- Guide RNA generation.

Scans a DNA sequence on BOTH strands, detects PAM sites for the chosen Cas system,
and emits candidate guides with their geometry (position, strand, GC content,
distance-to-target).

Extensibility: a Cas system is fully described by a `CasProfile` (PAM, guide length,
PAM orientation, cut offset). Adding SaCas9 / Cas12a / a new enzyme is a one-line
registry entry -- no changes to the scanning logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from qguide.app.schemas import Guide, Strand, TargetRegion

# IUPAC nucleotide ambiguity -> regex character classes ---------------------- #
_IUPAC = {
    "A": "A", "C": "C", "G": "G", "T": "T",
    "R": "[AG]", "Y": "[CT]", "S": "[GC]", "W": "[AT]",
    "K": "[GT]", "M": "[AC]", "B": "[CGT]", "D": "[AGT]",
    "H": "[ACT]", "V": "[ACG]", "N": "[ACGT]",
}
_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


@dataclass(frozen=True)
class CasProfile:
    """Everything the generator needs to know about a Cas enzyme."""
    name: str
    pam: str
    guide_length: int
    pam_side: str           # "3prime" (Cas9-like) or "5prime" (Cas12a-like)
    cut_offset: int         # bp from the PAM-proximal end to the DSB

    def pam_regex(self) -> str:
        return "".join(_IUPAC[b] for b in self.pam.upper())


# Registry -- extend here to support more enzymes ---------------------------- #
CAS_PROFILES: Dict[str, CasProfile] = {
    "SpCas9":    CasProfile("SpCas9",    "NGG",    20, "3prime", 3),
    "SpCas9-HF1":CasProfile("SpCas9-HF1","NGG",    20, "3prime", 3),
    "eSpCas9":   CasProfile("eSpCas9",   "NGG",    20, "3prime", 3),
    "SaCas9":    CasProfile("SaCas9",    "NNGRRT", 21, "3prime", 3),
    "Cas12a":    CasProfile("Cas12a",    "TTTV",   23, "5prime", 18),
}


def reverse_complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def clean_sequence(raw: str) -> str:
    """Strip FASTA headers, whitespace and uppercase. Non-ACGTN -> N."""
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith(">")]
    seq = re.sub(r"\s+", "", "".join(lines)).upper()
    return re.sub(r"[^ACGTN]", "N", seq)


def gc_content(seq: str) -> float:
    if not seq:
        return 0.0
    gc = sum(1 for b in seq if b in "GC")
    return gc / len(seq)


def resolve_profile(cas_enzyme: str, pam: Optional[str], guide_length: Optional[int]) -> CasProfile:
    """Pick a Cas profile, allowing the request to override PAM / guide length."""
    base = CAS_PROFILES.get(cas_enzyme, CAS_PROFILES["SpCas9"])
    return CasProfile(
        name=base.name,
        pam=(pam or base.pam),
        guide_length=(guide_length or base.guide_length),
        pam_side=base.pam_side,
        cut_offset=base.cut_offset,
    )


def _scan_strand(seq: str, profile: CasProfile) -> List[Dict]:
    """Find all (protospacer, pam) hits on a single 5'->3' string.

    Returns dicts with strand-local coordinates; the caller maps them to the
    forward reference frame for the minus strand.
    """
    glen = profile.guide_length
    pam_re = re.compile(profile.pam_regex())
    plen = len(profile.pam)
    hits: List[Dict] = []

    for m in pam_re.finditer(seq):
        p = m.start()
        if profile.pam_side == "3prime":
            # ...[ protospacer ][ PAM ]...
            proto_start, proto_end = p - glen, p
            pam_start = p
        else:  # 5prime, Cas12a-like: [ PAM ][ protospacer ]...
            proto_start, proto_end = p + plen, p + plen + glen
            pam_start = p
        if proto_start < 0 or proto_end > len(seq):
            continue
        spacer = seq[proto_start:proto_end]
        if "N" in spacer:                 # skip guides spanning unknown bases
            continue
        hits.append({
            "spacer": spacer,
            "pam": seq[pam_start:pam_start + plen],
            "proto_start": proto_start,
            "proto_end": proto_end,
        })
    return hits


def generate_guides(
    sequence: str,
    cas_enzyme: str = "SpCas9",
    pam: Optional[str] = None,
    guide_length: Optional[int] = None,
    target_region: Optional[TargetRegion] = None,
    max_guides: Optional[int] = None,
) -> List[Guide]:
    """Generate candidate guides on both strands.

    Coordinates in the returned `Guide` objects are always in the FORWARD
    reference frame so the frontend can draw a single genomic track.
    """
    seq = clean_sequence(sequence)
    profile = resolve_profile(cas_enzyme, pam, guide_length)
    n = len(seq)

    # Target centre for distance scoring (defaults to sequence midpoint).
    if target_region is not None:
        tgt_center = (target_region.start + target_region.end) / 2.0
    else:
        tgt_center = n / 2.0

    guides: List[Guide] = []
    idx = 0

    # ----- Plus strand ------------------------------------------------------ #
    for h in _scan_strand(seq, profile):
        cut = _cut_site_forward(h, profile, Strand.PLUS)
        guides.append(_make_guide(
            idx, h["spacer"], h["pam"], Strand.PLUS,
            h["proto_start"], h["proto_end"], cut, tgt_center, profile.name,
        ))
        idx += 1

    # ----- Minus strand ----------------------------------------------------- #
    rc = reverse_complement(seq)
    for h in _scan_strand(rc, profile):
        # Map strand-local (rc) coordinates back to forward coordinates.
        fwd_start = n - h["proto_end"]
        fwd_end = n - h["proto_start"]
        cut = _cut_site_forward(
            {"proto_start": fwd_start, "proto_end": fwd_end}, profile, Strand.MINUS
        )
        guides.append(_make_guide(
            idx, h["spacer"], h["pam"], Strand.MINUS,
            fwd_start, fwd_end, cut, tgt_center, profile.name,
        ))
        idx += 1

    # Closest-to-target first; deterministic tiebreak by id.
    guides.sort(key=lambda g: (g.distance_to_target, g.guide_id))
    if max_guides is not None:
        guides = guides[:max_guides]
    return guides


def _cut_site_forward(h: Dict, profile: CasProfile, strand: Strand) -> int:
    """Approximate DSB position in forward coordinates."""
    if strand == Strand.PLUS:
        if profile.pam_side == "3prime":
            return h["proto_end"] - profile.cut_offset
        return h["proto_start"] + profile.cut_offset
    # minus strand: PAM-proximal end is the low-coordinate side after remap
    if profile.pam_side == "3prime":
        return h["proto_start"] + profile.cut_offset
    return h["proto_end"] - profile.cut_offset


def _make_guide(idx, spacer, pam_seq, strand, start, end, cut, tgt_center, cas) -> Guide:
    center = (start + end) / 2.0
    return Guide(
        guide_id=f"gRNA_{idx:03d}",
        sequence=spacer,
        pam=pam_seq,
        strand=strand,
        position=start,
        end=end,
        cut_site=int(round(cut)),
        gc_content=gc_content(spacer),
        distance_to_target=int(round(abs(center - tgt_center))),
        cas_enzyme=cas,
    )
