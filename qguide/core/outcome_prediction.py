"""
Step 4 -- Functional outcome prediction.

This is Q-Guide's core differentiator: instead of asking "which guide cuts best?"
it predicts the *biological outcome* of an edit -- frameshift vs in-frame indel,
no-edit, knockout probability, exon disruption -- and rolls them into a single
functional-disruption score that downstream optimisation can target.

V1 uses an interpretable rule-based model grounded in published NHEJ biology:
  * Indel size distributions at SpCas9 cut sites are dominated by 1 bp insertions
    and small deletions; ~2/3 of indels are frameshifting (not multiples of 3).
  * Microhomology around the cut site biases toward predictable deletions (MMEJ).
  * Cut position relative to the coding region / target governs whether a frameshift
    actually disrupts protein function.

Extensibility: `OutcomeModel` is an interface. A trained model
(`XGBoostOutcomeModel`, `TransformerOutcomeModel`, inVivo/Lindel-style) implements
`predict(guide, context) -> OutcomePrediction` and is dropped in unchanged.
"""
from __future__ import annotations

from typing import Optional, Protocol

from qguide.app.schemas import (
    DesiredOutcome,
    Guide,
    OutcomePrediction,
)


class OutcomeModel(Protocol):
    def predict(self, guide: Guide, desired_outcome: str,
                efficiency: float = 1.0) -> OutcomePrediction: ...


def _microhomology_strength(seq: str) -> float:
    """Crude MMEJ proxy: complementary flank k-mers around the cut promote
    predictable (often in-frame) deletions. Returns 0..1."""
    if len(seq) < 8:
        return 0.0
    left, right = seq[:len(seq) // 2], seq[len(seq) // 2:]
    comp = {"A": "T", "T": "A", "G": "C", "C": "G"}
    rc_right = "".join(comp.get(b, "N") for b in right[::-1])
    matches = sum(1 for a, b in zip(left[::-1], rc_right) if a == b)
    return min(1.0, matches / (len(seq) / 2.0))


class RuleBasedOutcomeModel:
    """Default interpretable V1 model."""

    name = "rule_based_v1"

    def predict(self, guide: Guide, desired_outcome: str,
                efficiency: float = 1.0) -> OutcomePrediction:
        on_target = guide.scores.on_target
        gc = guide.gc_content

        # 1) Probability that *any* edit occurs scales with on-target efficiency
        #    AND the experimental-context efficiency factor (cell type, delivery,
        #    temperature, expression). A neuron / cold / low-expression context
        #    lowers edit probability; stem cells / RNP / high expression raise it.
        edit_prob = (0.15 + 0.80 * on_target) * efficiency
        edit_prob = max(0.02, min(0.98, edit_prob))
        no_edit = 1.0 - edit_prob

        # 2) Of the edits, how many are frameshifting vs in-frame.
        #    Base NHEJ frameshift fraction ~0.66; microhomology pulls toward
        #    in-frame predictable deletions.
        mh = _microhomology_strength(guide.sequence)
        frameshift_fraction = max(0.45, 0.66 - 0.25 * mh)
        frameshift = edit_prob * frameshift_fraction
        in_frame = edit_prob * (1.0 - frameshift_fraction)

        # 3) Knockout probability: a frameshift is the dominant KO route, but
        #    a fraction of in-frame edits still disrupt critical residues.
        knockout = frameshift + 0.20 * in_frame

        # 4) Exon disruption: proximity to target (a proxy for exon centre here)
        #    plus editing probability.
        proximity = guide.scores.distance_to_target   # already 0..1 (closer=1)
        exon_disruption = edit_prob * (0.5 + 0.5 * proximity)

        # 5) Composite functional-disruption score, biased by the user's objective.
        functional = self._objective_weighted(
            desired_outcome, knockout, frameshift, exon_disruption, edit_prob
        )

        # Light GC sanity penalty for extreme spacers.
        if gc < 0.2 or gc > 0.85:
            functional *= 0.9

        return OutcomePrediction(
            frameshift_prob=round(frameshift, 4),
            in_frame_indel_prob=round(in_frame, 4),
            no_edit_prob=round(no_edit, 4),
            knockout_prob=round(min(1.0, knockout), 4),
            exon_disruption_prob=round(min(1.0, exon_disruption), 4),
            functional_disruption_score=round(min(1.0, functional), 4),
            model=self.name,
        )

    @staticmethod
    def _objective_weighted(outcome, knockout, frameshift, exon, edit_prob) -> float:
        """Weight outcome components toward what the user actually wants."""
        if outcome == DesiredOutcome.KNOCKOUT.value:
            return 0.7 * knockout + 0.3 * frameshift
        if outcome == DesiredOutcome.GENE_DISRUPTION.value:
            return 0.5 * knockout + 0.5 * frameshift
        if outcome == DesiredOutcome.EXON_TARGETING.value:
            return 0.6 * exon + 0.4 * knockout
        if outcome == DesiredOutcome.DELETION.value:
            # deletions favour predictable cutting (edit_prob) + exon hit
            return 0.6 * edit_prob + 0.4 * exon
        # custom / fallback: balanced
        return 0.4 * knockout + 0.3 * frameshift + 0.3 * exon


DEFAULT_MODEL: OutcomeModel = RuleBasedOutcomeModel()


def predict_outcome(
    guide: Guide,
    desired_outcome: str = DesiredOutcome.KNOCKOUT.value,
    model: OutcomeModel = DEFAULT_MODEL,
    efficiency: float = 1.0,
) -> Guide:
    guide.outcome = model.predict(guide, desired_outcome, efficiency)
    if guide.outcome.no_edit_prob > 0.6:
        guide.warnings.append("High no-edit probability -- low predicted editing efficiency.")
    return guide


def predict_outcomes(guides, desired_outcome: str = DesiredOutcome.KNOCKOUT.value,
                     model: OutcomeModel = DEFAULT_MODEL, efficiency: float = 1.0):
    return [predict_outcome(g, desired_outcome, model, efficiency) for g in guides]
