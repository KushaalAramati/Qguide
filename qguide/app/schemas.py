"""
Q-Guide data model and API contract.

This module defines:
  * Domain models  (Guide, ScoreBreakdown, OutcomePrediction, OffTargetReport, ...)
  * API request/response models (DesignRequest, DesignResponse, ...)

Everything is Pydantic so the same objects serialize cleanly over FastAPI and are
easy to construct in the Streamlit frontend and the test-suite. Core modules import
ONLY the domain models from here -- they never import FastAPI -- so the scientific
core stays framework-independent.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Enumerations                                                                 #
# --------------------------------------------------------------------------- #
class Strand(str, Enum):
    PLUS = "+"
    MINUS = "-"


class DesiredOutcome(str, Enum):
    KNOCKOUT = "knockout"
    PRECISE_EDIT = "precise_edit"
    BASE_EDIT = "base_edit"
    PRIME_EDIT = "prime_edit"
    CRISPRI = "crispri"            # repression
    CRISPRA = "crispra"            # activation
    SCREEN = "screen"             # screening / library design
    # legacy / general modes (kept for backward compatibility)
    GENE_DISRUPTION = "gene_disruption"
    EXON_TARGETING = "exon_targeting"
    DELETION = "deletion"
    CUSTOM = "custom"


class RiskTolerance(str, Enum):
    LOW = "low"             # therapeutic-like: heavily penalise off-target/uncertainty
    BALANCED = "balanced"
    HIGH = "high"           # exploratory: tolerate more risk for activity


class RiskCategory(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class EnsembleScore(BaseModel):
    """The spec's transparent, multi-component QGuide score.

    Every component is in 0..1. `final_qguide_score` is a *visible* weighted
    combination of them (weights depend on the user's goal + risk tolerance), not a
    black box. Components listed in `provisional` are placeholders/heuristics whose
    real (trained-model or genome-backed) implementations are not yet wired in.
    """
    on_target_score: float = 0.0
    off_target_score: float = 0.0          # SAFETY: 1 - aggregate off-target risk
    specificity_score: float = 0.0
    desired_outcome_score: float = 0.0
    repair_outcome_score: float = 0.0
    genomic_context_score: float = 0.0
    cell_context_score: float = 0.0
    model_agreement_score: float = 0.0
    uncertainty_score: float = 0.0         # 0 = confident, 1 = very uncertain
    final_qguide_score: float = 0.0
    weights: Dict[str, float] = Field(default_factory=dict)
    contributions: Dict[str, float] = Field(default_factory=dict)  # signed, per term
    provisional: List[str] = Field(default_factory=list)
    confidence_label: str = "medium"       # high | medium | low
    goal_profile: str = "knockout_balanced"
    badges: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Sub-reports attached to each guide                                           #
# --------------------------------------------------------------------------- #
class ScoreBreakdown(BaseModel):
    """All modular biological-scoring components, each normalised to 0..1."""
    gc_content: float = 0.0
    pam: float = 0.0
    complexity: float = 0.0
    homopolymer_penalty: float = 0.0          # 0 = no penalty, 1 = max penalty
    secondary_structure_penalty: float = 0.0  # 0 = no penalty, 1 = max penalty
    distance_to_target: float = 0.0
    sequence_quality: float = 0.0
    on_target: float = 0.0
    notes: Dict[str, str] = Field(default_factory=dict)


class OutcomePrediction(BaseModel):
    """Predicted *biological* outcome of a successful edit (probabilities sum ~1)."""
    frameshift_prob: float = 0.0
    in_frame_indel_prob: float = 0.0
    no_edit_prob: float = 0.0
    knockout_prob: float = 0.0
    exon_disruption_prob: float = 0.0
    functional_disruption_score: float = 0.0  # 0..1 composite
    model: str = "rule_based_v1"


class MismatchBin(BaseModel):
    mismatches: int
    count: int


class OffTargetHit(BaseModel):
    """A single predicted off-target site (genome-backed or synthetic/heuristic)."""
    locus: str = "synthetic"                   # e.g. "chr1:1,234,567" or a descriptor
    position: int = -1
    strand: str = "+"
    mismatches: int = 0
    mismatch_positions: List[int] = Field(default_factory=list)
    pam: str = ""
    cfd_score: float = 0.0                     # 0..1, CFD/MIT-style (placeholder for now)
    annotation: str = "unknown"                # exon | promoter | enhancer | intron | intergenic
    severity: RiskCategory = RiskCategory.LOW
    explanation: str = ""
    provisional: bool = True                    # True until genome-backed alignment is used


class OffTargetReport(BaseModel):
    risk_score: float = 0.0                    # 0 (safe) .. 1 (dangerous)
    risk_category: RiskCategory = RiskCategory.LOW
    potential_off_target_count: int = 0
    mismatch_distribution: List[MismatchBin] = Field(default_factory=list)
    concerning_regions: List[Dict[str, object]] = Field(default_factory=list)
    hits: List[OffTargetHit] = Field(default_factory=list)
    aggregate_burden: float = 0.0              # severity-weighted total, not just count
    genome_backed: bool = False
    warning: str = ""
    method: str = "heuristic_v1"


class ContextAdjustment(BaseModel):
    """Record of how experimental context reshaped a guide's score.

    `multiplier` is the editing-efficiency factor (organism/cell/Cas/delivery/temp/
    expression) that scales predicted outcome. `off_target_multiplier` scales the
    predicted off-target risk (enzyme fidelity + organism), and `gc_multiplier`
    tunes how strongly GC imbalance is penalised for the organism.
    """
    multiplier: float = 1.0
    off_target_multiplier: float = 1.0
    gc_multiplier: float = 1.0
    applied: Dict[str, float] = Field(default_factory=dict)   # factor -> multiplier
    notes: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# The central domain object                                                    #
# --------------------------------------------------------------------------- #
class Guide(BaseModel):
    """A candidate guide RNA and every analysis layer attached to it.

    Modules fill in successive fields as the guide flows through the pipeline:
    generator -> scoring -> off_target -> outcome -> context -> multi-objective.
    """
    guide_id: str
    sequence: str
    pam: str
    strand: Strand
    position: int                 # 0-based start of the protospacer in input coords
    end: int                      # exclusive end of the protospacer
    cut_site: int                 # approximate double-strand-break position
    gc_content: float
    distance_to_target: int       # bp from the centre of the target region
    cas_enzyme: str = "SpCas9"

    # Filled by later stages -------------------------------------------------- #
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    outcome: OutcomePrediction = Field(default_factory=OutcomePrediction)
    off_target: OffTargetReport = Field(default_factory=OffTargetReport)
    context: ContextAdjustment = Field(default_factory=ContextAdjustment)

    final_score: float = 0.0
    final_breakdown: Dict[str, float] = Field(default_factory=dict)
    ensemble: EnsembleScore = Field(default_factory=EnsembleScore)
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    explanation: str = ""


# --------------------------------------------------------------------------- #
# API request / response                                                       #
# --------------------------------------------------------------------------- #
class TargetRegion(BaseModel):
    start: int = Field(..., ge=0)
    end: int = Field(..., gt=0)


class DesignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Raw DNA (A/C/G/T/N). FASTA headers stripped by caller.")
    gene_name: Optional[str] = None
    cas_enzyme: str = "SpCas9"
    pam: Optional[str] = None                 # if None, derived from cas_enzyme config
    organism: str = "human"
    target_region: Optional[TargetRegion] = None
    desired_outcome: DesiredOutcome = DesiredOutcome.KNOCKOUT

    # Optional experimental context ------------------------------------------ #
    cell_type: Optional[str] = None
    delivery_method: Optional[str] = None
    temperature: Optional[float] = None       # Celsius
    expression_level: Optional[str] = None    # low | medium | high

    risk_tolerance: str = "balanced"           # low | balanced | high (affects weights)

    # Knobs ------------------------------------------------------------------- #
    guide_length: Optional[int] = None
    max_guides: int = 200                      # cap on candidates carried forward
    set_size: int = 3                          # N for "best N-guide set"
    selection_mode: str = "set"                # "individual" | "set"
    optimizer_mode: str = "classical"          # classical | quantum_inspired | quantum_hardware
    optimizer_backend: str = "sa"              # legacy: "sa" | "dwave"

    model_config = ConfigDict(use_enum_values=True)


class OptimizationResult(BaseModel):
    selected_guide_ids: List[str]
    objective_value: float
    method: str
    mode: str = "classical"                    # classical | quantum_inspired | quantum_hardware
    iterations: int
    rejected_explanations: Dict[str, str] = Field(default_factory=dict)
    tradeoffs: List[str] = Field(default_factory=list)
    # Top-N-by-individual-score vs the optimized set (the value of optimizing)
    top_n_individual: List[str] = Field(default_factory=list)
    expected_outcome_delta: float = 0.0        # optimized mean score - top-N mean score
    off_target_delta: float = 0.0              # optimized mean risk - top-N mean risk
    comparison_note: str = ""


class DesignResponse(BaseModel):
    request: DesignRequest
    guides: List[Guide]                       # ranked, best first
    best_single_guide_id: Optional[str]
    optimized_set: OptimizationResult
    warnings: List[str] = Field(default_factory=list)
    summary: str = ""
